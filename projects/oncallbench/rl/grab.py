"""Poll Verda until one GPU that fits the job is free, and create it (cheapest first, spot first).

    sops exec-env secrets/secrets.yaml 'python3 spikes/aq-incident/rl/grab.py <ssh-key-id>'
"""

import sys
import time

import verda

# (type, image) by preference: >= 80 GB so vLLM and full-parameter training share one GPU
PREFER = ["1A100.22V", "1RTXPRO6000.30V", "1H100.80S.30V", "1H100.80S.32V", "1H200.141S.44V", "1B200.30V"]
IMAGE = "24.04.cuda13.4"


def main(key, max_minutes=240):
    for _ in range(max_minutes * 2):
        tok = verda.token()
        options = []
        for spot in (True, False):
            q = "?is_spot=true" if spot else ""
            for loc in verda.api("GET", f"/instance-availability{q}", tok=tok):
                for t in loc["availabilities"]:
                    if t in PREFER:
                        options.append((not spot, PREFER.index(t), t, loc["location_code"], spot))
        for _, _, itype, loc, spot in sorted(options):
            body = dict(instance_type=itype, image=IMAGE, ssh_key_ids=[key], hostname=f"{verda.PREFIX}gpu",
                        description="aq-incident RL training (temporary)", location_code=loc, is_spot=spot,
                        os_volume=dict(name=f"{verda.PREFIX}os", size=150))
            try:
                print(time.strftime("%H:%M:%S"), "created", itype, loc, "spot" if spot else "on-demand",
                      verda.api("POST", "/instances", body, tok=tok), flush=True)
                return
            except SystemExit as e:
                print(time.strftime("%H:%M:%S"), "failed", itype, loc, spot, str(e)[:120], flush=True)
        time.sleep(30)
    sys.exit("no GPU became free")


if __name__ == "__main__":
    main(sys.argv[1])
