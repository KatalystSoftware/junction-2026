"""Verda (ex-DataCrunch) REST helper for the training GPU. Credentials come only from the env:

    sops exec-env secrets/secrets.yaml 'python3 spikes/aq-incident/rl/verda.py balance'

Subcommands: balance | types | avail | images | list | keys | delete <id> | volumes | delete-volume <id>
            | create <type> <location> <ssh-key-id> <image> [spot].
It never touches the CPU runner from infra/verda: create and delete act on hostnames starting
with "aq-rl-" only.
"""

import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("VERDA_API", "https://api.verda.com/v1")
PREFIX = "aq-rl-"


def token():
    body = json.dumps({"grant_type": "client_credentials", "client_id": os.environ["VERDA_CLIENT_ID"],
                       "client_secret": os.environ["VERDA_CLIENT_SECRET"]}).encode()
    req = urllib.request.Request(f"{API}/oauth2/token", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def api(method, path, body=None, tok=None):
    req = urllib.request.Request(f"{API}{path}", None if body is None else json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": f"Bearer {tok or token()}"},
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            text = r.read().decode()
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path}: {e.code} {e.read().decode()[:500]}")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def main(cmd, *args):
    tok = token()
    if cmd == "balance":
        print(api("GET", "/balance", tok=tok))
    elif cmd == "types":
        for t in api("GET", "/instance-types", tok=tok):
            if t.get("gpu", {}).get("number_of_gpus"):
                print(t["instance_type"], t.get("price_per_hour"), t.get("spot_price"), t["gpu"].get("description"),
                      t.get("gpu_memory", {}).get("size_in_gigabytes"))
    elif cmd == "avail":
        for loc in api("GET", "/instance-availability", tok=tok):
            print(loc["location_code"], " ".join(x for x in loc["availabilities"] if not x.startswith("CPU")))
    elif cmd == "images":
        for im in api("GET", "/images", tok=tok):
            print(im.get("image_type"), im.get("name"))
    elif cmd == "list":
        for i in api("GET", "/instances", tok=tok):
            print(i["id"], i["hostname"], i["instance_type"], i["status"], i.get("ip"), i.get("price_per_hour"))
    elif cmd == "keys":
        for k in api("GET", "/ssh-keys", tok=tok):
            print(k["id"], k["name"])
    elif cmd == "create":
        itype, loc, key, image, spot = args[0], args[1], args[2], args[3], len(args) > 4 and args[4] == "spot"
        print(api("POST", "/instances", dict(
            instance_type=itype, image=image, ssh_key_ids=[key], hostname=f"{PREFIX}{itype.lower().replace('.', '-')}",
            description="aq-incident RL training (temporary)", location_code=loc, is_spot=spot,
            os_volume=dict(name=f"{PREFIX}os", size=150)), tok=tok))
    elif cmd == "delete":
        inst = {i["id"]: i for i in api("GET", "/instances", tok=tok)}
        target = inst.get(args[0])
        if not target or not target["hostname"].startswith(PREFIX):
            sys.exit(f"refusing: {args[0]} is not an {PREFIX}* instance")
        print(api("PUT", "/instances", dict(action="delete", id=args[0], delete_permanently=True), tok=tok))
    elif cmd == "volumes":
        for v in api("GET", "/volumes", tok=tok):
            print(v["id"], v["name"], v["status"], v.get("instance_id"), v.get("size"))
    elif cmd == "delete-volume":
        vol = {v["id"]: v for v in api("GET", "/volumes", tok=tok)}.get(args[0])
        if not vol or not vol["name"].startswith(PREFIX) or vol.get("instance_id"):
            sys.exit(f"refusing: {args[0]} is not a detached {PREFIX}* volume")
        print(api("PUT", "/volumes", dict(action="delete", id=args[0], is_permanent=True), tok=tok))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(*sys.argv[1:])
