"""The alarm: tells a person within seconds that the live desk has stopped, from its log. Run it on another machine
than the desk, the cold standby, so that it also sees the desk's machine or its network go.

    uv run python -m spreadlab.alarm --ssh <desk host> --path <checkout>/spread/data/live          # the newest world there
    uv run python -m spreadlab.alarm --path data/live/<world id>/log.jsonl                          # a log on this machine
    uv run python -m spreadlab.alarm --ssh <desk host> --path ... --notify 'curl -s -d "$ALARM_TEXT" ntfy.sh/$TOPIC'

It reads the new lines of the desk's log.jsonl every 2 seconds, over ssh when --ssh names the desk's host, and alarms:

- when the desk writes nothing for 8 seconds: it writes a heartbeat every 2 seconds while it plays;
- when a price request reaches its deadline without a quote from the desk or its fallback;
- when the log cannot be read for 8 seconds: the desk's machine or the network to it is down;
- when the desk stops for good because another desk took the world over (`fenced`), or loses its connection or
  meets an error, and when the stream shows a gig that it did not post (a second desk may be playing).

It says once when the desk is back. Each alarm prints a line with a bell and runs --notify, a shell command, with the
text in $ALARM_TEXT and $ALARM_LEVEL (alarm, warning or ok). Silence is the desk's, not the world's: the world sends
no requests at night, but the desk beats all the time, so the alarm watches the same way at every hour. It reads
nothing from Bahn and needs no key.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

POLL = 2.0  # seconds between reads of the log
SILENT = 8.0  # seconds without a line from the desk: it has stopped
UNREAD = 8.0  # seconds in which the log could not be read: the desk's machine or the network is down
QUIET = 30.0  # seconds between two notices of the same kind


@dataclass
class Watch:
    """What the log says, and what the alarm has told. `now` is the alarm's clock in seconds."""

    last_line: Optional[float] = None  # when the last new line came
    last_read: Optional[float] = None  # when the log was last read
    minute: float = -1.0  # the world minute of the desk's last heartbeat
    open: dict = field(default_factory=dict)  # request id -> respondBy, for requests with no quote yet
    quoted: set = field(default_factory=set)
    told: dict = field(default_factory=dict)  # kind of notice -> when it was last told
    down: Optional[str] = None  # the kind of the alarm that is on, until the desk is back
    ended: bool = False

    def lines(self, lines: list[dict], now: float) -> list[tuple[str, str, str]]:
        """Takes new log lines; returns the notices: (level, kind, text)."""
        out = []
        if lines:
            self.last_line = now
            if self.down:
                out.append(("ok", "back", f"The desk writes again ({self.down} is over)."))
                self.down = None
        for line in lines:
            kind = line.get("kind")
            if kind == "beat":
                self.minute = line["clock"]
            elif kind == "event" and line["event"]["kind"] == "price_request" and not line.get("replayed"):
                request = line["event"]["request"]
                if request["id"] not in self.quoted:
                    self.open[request["id"]] = request["respondBy"]
            elif (kind == "action" and line["action"]["type"] == "quote" and line["ok"]) or (kind == "fallback" and line["ok"]):
                request_id = line["action"]["requestId"] if kind == "action" else line["requestId"]
                self.quoted.add(request_id)
                self.open.pop(request_id, None)
            elif kind == "fenced":
                out.append(("alarm", "fenced", "The desk stopped for good: another desk plays the world. Check that exactly one desk runs."))
            elif kind == "foreign_gig":
                out.append(("warning", "foreign", f"The stream shows gig {line['gigId']} that this desk did not post: is a second desk running?"))
            elif kind == "lost":
                out.append(("warning", "lost", f"The desk lost its connection ({line['error'][:80]}); it joins again by itself."))
            elif kind == "error":
                out.append(("warning", "error", "The desk met an error; it goes on. See its log."))
            elif kind == "end":
                self.ended = True
                out.append(("ok", "end", f"The world has ended: margin €{line['score']['marginCents'] / 100:,.2f}, {line['score']['wonOrders']} orders."))
        missed = sorted(r for r, by in self.open.items() if 0 <= self.minute and by <= self.minute)
        for request_id in missed:
            self.open.pop(request_id)
        if missed:
            out.append(("alarm", "missed", f"{len(missed)} price requests reached their deadline with no quote in the desk's log: {', '.join(missed[:5])}."))
        return out

    def tick(self, now: float, read_ok: bool) -> list[tuple[str, str, str]]:
        """The silences, checked at each poll."""
        out = []
        if read_ok:
            self.last_read = now
        if self.ended:
            return out
        if self.last_read is not None and now - self.last_read >= UNREAD:
            out.append(("alarm", "unreadable", f"The desk's log could not be read for {now - self.last_read:.0f} s: its machine or the network to it may be down."))
            self.down = self.down or "the silence"
        elif read_ok and self.last_line is not None and now - self.last_line >= SILENT and self.minute >= 0:
            out.append(("alarm", "silent", f"The desk has written nothing for {now - self.last_line:.0f} s: it has stopped. Start it again, or the standby."))
            self.down = self.down or "the silence"
        return out

    def filter(self, notices: list[tuple[str, str, str]], now: float) -> list[tuple[str, str, str]]:
        """At most one notice of a kind in QUIET seconds, but every ok."""
        out = []
        for level, kind, text in notices:
            if level == "ok" or now - self.told.get(kind, -QUIET) >= QUIET:
                self.told[kind] = now
                out.append((level, kind, text))
        return out


class NoLog(Exception):
    """No world's log yet: the desk waits for the final to be set, or has not started."""


class Source:
    """The desk's log: a local file, or one on the desk's host, read from where the last read ended."""

    def __init__(self, path: str, ssh: Optional[str] = None):
        self.path, self.ssh, self.offset, self.rest, self.file = path, ssh, 0, b"", None

    def resolve(self) -> str:
        """A folder of worlds stands for the log of the world that was written last."""
        if self.path.endswith(".jsonl"):
            return self.path
        command = f"ls -t {shlex.quote(self.path)}/*/log.jsonl | head -1"
        found = self.run(command) if self.ssh else subprocess.run(["sh", "-c", command], capture_output=True, timeout=5).stdout
        if not found.strip():
            raise NoLog(f"no log.jsonl under {self.path} yet")
        return found.decode().strip()

    def run(self, command: str) -> bytes:
        done = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4", self.ssh, command], capture_output=True, timeout=6)
        if done.returncode != 0:
            raise OSError(done.stderr.decode(errors="replace").strip()[:200] or f"ssh exit {done.returncode}")
        return done.stdout

    def read(self) -> list[dict]:
        log = self.resolve()
        if log != self.file:  # a new world: start at its beginning
            self.file, self.offset, self.rest = log, 0, b""
        if self.ssh:
            data = self.run(f"tail -c +{self.offset + 1} {shlex.quote(log)} | head -c 4000000")
        else:
            with open(log, "rb") as f:
                f.seek(self.offset)
                data = f.read(4_000_000)
        self.offset += len(data)
        data, lines = self.rest + data, []
        *whole, self.rest = data.split(b"\n")
        for raw in whole:
            try:
                lines.append(json.loads(raw))
            except ValueError:
                pass
        return lines


def tell(level: str, text: str, notify: Optional[str]) -> None:
    stamp, bell = time.strftime("%H:%M:%S"), "\a" if level == "alarm" else ""
    print(f"{bell}{stamp} {level.upper():7} {text}", flush=True)
    if notify:
        try:
            subprocess.run(["sh", "-c", notify], env={**os.environ, "ALARM_TEXT": text, "ALARM_LEVEL": level}, timeout=10)
        except Exception as error:  # the alarm goes on without its channel
            print(f"{stamp} the notify command failed: {error!r}", flush=True)


def watch_log(source: Source, notify: Optional[str], clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
              polls: Optional[int] = None) -> None:
    """Watches until Ctrl-C. A world that has ended stays quiet; the log of a newer world, the next test final or the
    final, is watched from its first line."""
    state, n, log = Watch(), 0, None
    tell("ok", f"Watching {source.ssh + ':' if source.ssh else ''}{source.path}.", notify)
    while polls is None or n < polls:
        n += 1
        now = clock()
        first = False
        try:
            lines, read_ok = source.read(), True
            if source.file != log:
                if log is not None:
                    tell("ok", f"Watching a new world's log: {source.file}.", notify)
                state, log, first = Watch(last_read=now, last_line=now), source.file, True
        except NoLog:
            lines, read_ok = [], True  # nothing to watch yet: no alarm
        except (OSError, subprocess.TimeoutExpired) as error:
            lines, read_ok = [], False
            state.last_read = now if state.last_read is None else state.last_read  # the first read failed: count from now
            print(f"{time.strftime('%H:%M:%S')} read failed: {error}", flush=True)
        notices = state.lines(lines, now) + state.tick(now, read_ok)
        if first:  # what the log held before the alarm watched it is the past: the alarm tells what happens from now
            notices = [("ok", "end", text) for _, kind, text in notices if kind == "end"]
        for level, _, text in state.filter(notices, now):
            tell(level, text, notify)
        sleep(max(0.0, POLL - (clock() - now)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", required=True, help="the desk's log.jsonl, or its data/live folder for the world written last")
    parser.add_argument("--ssh", help="the desk's host, as ssh knows it; without it the path is on this machine")
    parser.add_argument("--notify", default=os.environ.get("ALARM_NOTIFY"), help="a shell command run for each notice, with $ALARM_TEXT and $ALARM_LEVEL")
    args = parser.parse_args()
    try:
        watch_log(Source(args.path, args.ssh), args.notify)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
