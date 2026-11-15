"""Downloads the packed weeks of a release of this repository and unpacks them (CI only; the job's own token reads the release).
Every asset of the release is a tar of the data folder; a later asset adds to the earlier ones.

    python3 scratch/standin/fetch_data.py <tag> <folder>
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request

tag, folder = sys.argv[1], sys.argv[2]
repo, token = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"]


def get(url: str, accept: str):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}))


release = json.load(get(f"https://api.github.com/repos/{repo}/releases/tags/{tag}", "application/vnd.github+json"))
os.makedirs(folder, exist_ok=True)
for asset in release["assets"]:
    path = os.path.join(folder, asset["name"])
    with get(asset["url"], "application/octet-stream") as response, open(path, "wb") as f:
        while chunk := response.read(1 << 20):
            f.write(chunk)
    subprocess.run(["tar", "-xf", path, "-C", folder], check=True)
    os.remove(path)
    print(f"{asset['name']}: {asset['size'] >> 20} MB", flush=True)
