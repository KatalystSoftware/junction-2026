"""Packs scans and played weeks into the archive, and unpacks them again.

A week file repeats most of what its seed's scan and the other variants' weeks of that seed hold. A
bundle therefore keeps them together: one tar of the plain JSON, ordered by seed and compressed as
a whole with zstd, about a seventh of the size of the same files gzipped one by one.

A bundle is never changed, because Git LFS stores a changed file again in full. Each pack writes a
new bundle with the files that no bundle holds yet. A week that was played again goes into the new
bundle, and unpack takes each file from the newest bundle that holds it.

    python -m spreadlab.archive pack      data folder -> archive/bundles/<UTC time>.tar.zst and .sha256
    python -m spreadlab.archive unpack    archive/bundles -> data folder; keeps the files it has

Needs the `zstd` command. The .sha256 file lists each file of the bundle with the hash of its plain content.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import subprocess
import tarfile
import time
from pathlib import Path
from typing import Iterator

from .server import PROJECT, data_dir

BUNDLES = PROJECT / "archive" / "bundles"
WINDOW = "--long=27"  # 128 MB: zstd finds the same seed's earlier weeks, and unpacking needs no more memory than its default


def packed(bundles: Path) -> dict[str, tuple[str, Path]]:
    """Each packed file, with the hash of its content and the newest bundle that holds it."""
    held: dict[str, tuple[str, Path]] = {}
    for listing in sorted(bundles.glob("*.sha256")):
        for line in listing.read_text().splitlines():
            digest, name = line.split("  ", 1)
            if name.startswith("/") or ".." in name.split("/"):
                raise ValueError(f"{listing}: {name} points outside the data folder")
            held[name] = (digest, listing.with_suffix(".tar.zst"))
    return held


def members(bundle: Path) -> Iterator[tuple[str, bytes]]:
    """The files of a bundle with their plain content, in the order they were packed."""
    with bundle.open("rb", buffering=0) as f:  # unbuffered: zstd reads the same file descriptor from its start
        if f.read(7) == b"version":
            raise SystemExit(f"{bundle} is a Git LFS pointer. Run `git lfs pull` first.")
        f.seek(0)
        zstd = subprocess.Popen(["zstd", "-d", "-q", "-c", WINDOW], stdin=f, stdout=subprocess.PIPE)
        with tarfile.open(fileobj=zstd.stdout, mode="r|") as tar:
            for info in tar:
                yield info.name, tar.extractfile(info).read()
        if zstd.wait():
            raise RuntimeError(f"zstd could not read {bundle}")


def by_seed(path: Path) -> tuple[str, bool, str]:
    """Sorts a seed's scan first and its weeks after it, so each week sits next to the files it repeats."""
    return path.name.split(".")[0], path.parent.name != "scans", path.as_posix()


def pack(source: Path, bundles: Path, name: str) -> tuple[Path, int] | None:
    """Writes the scans, weeks and map of `source` that no bundle holds into a new bundle. Returns it with its file count."""
    held = packed(bundles)
    files = [p for pattern in ("map.json", "scans/*.json.gz", "runs/*/*.json*") for p in source.glob(pattern) if p.suffix != ".part"]
    bundles.mkdir(parents=True, exist_ok=True)
    bundle = bundles / f"{name}.tar.zst"
    partial = bundle.with_name(bundle.name + ".part")
    lines = []
    with partial.open("wb") as out:
        zstd = subprocess.Popen(["zstd", "-19", WINDOW, "-T0", "-q", "-c"], stdin=subprocess.PIPE, stdout=out)
        with tarfile.open(fileobj=zstd.stdin, mode="w|") as tar:
            for path in sorted(files, key=by_seed):
                member = path.relative_to(source).as_posix()
                content = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
                digest = hashlib.sha256(content).hexdigest()
                if held.get(member, ("",))[0] == digest:
                    continue
                info = tarfile.TarInfo(member)  # no time or owner: the same files give the same bundle
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
                lines.append(f"{digest}  {member}")
        zstd.stdin.close()
        if zstd.wait():
            raise RuntimeError("zstd failed")
    if not lines:
        partial.unlink()
        return None
    read_back = [f"{hashlib.sha256(content).hexdigest()}  {member}" for member, content in members(partial)]
    if read_back != lines:
        raise RuntimeError(f"{partial} does not hold what was packed into it")
    partial.replace(bundle)
    bundle.with_suffix("").with_suffix(".sha256").write_text("\n".join(lines) + "\n")
    return bundle, len(lines)


def unpack(bundles: Path, target: Path, force: bool = False) -> int:
    """Writes the packed files that `target` lacks, or all of them with `force`. Returns how many it wrote."""
    wanted: dict[Path, set[str]] = {}
    for member, (_, bundle) in packed(bundles).items():
        if force or not (target / member).exists():
            wanted.setdefault(bundle, set()).add(member)
    for bundle, names in sorted(wanted.items()):
        for member, content in members(bundle):
            if member not in names:
                continue
            path = target / member
            path.parent.mkdir(parents=True, exist_ok=True)
            partial = path.with_suffix(path.suffix + ".part")
            partial.write_bytes(gzip.compress(content, 6, mtime=0) if path.suffix == ".gz" else content)
            partial.replace(path)  # a reader never sees half a file
    return sum(len(names) for names in wanted.values())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["pack", "unpack"])
    parser.add_argument("--data", type=Path, default=data_dir(), help="folder with runs/, scans/ and map.json; default: the data folder")
    parser.add_argument("--name", default=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), help="pack: name of the new bundle; bundles are read in name order")
    parser.add_argument("--force", action="store_true", help="unpack: overwrite the files the data folder has")
    args = parser.parse_args()
    started = time.time()
    if args.action == "pack":
        made = pack(args.data, BUNDLES, args.name)
        print(f"{made[0].relative_to(PROJECT)}: {made[1]} files, {made[0].stat().st_size / 1e6:.1f} MB" if made else "Nothing new to pack.", end="")
    else:
        print(f"{unpack(BUNDLES, args.data, args.force)} files written to {args.data}", end="")
    print(f" ({time.time() - started:.0f} s)")


if __name__ == "__main__":
    main()
