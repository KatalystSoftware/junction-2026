"""On-call incident simulator: a seeded microservice estate with planted faults.

One class holds the whole world. Time is simulated minutes relative to the page (minute 0) and
moves only when a tool call says so. An episode is fully determined by (seed, level, action log),
so the verifier replays the signed log and recomputes the cost; nothing the agent wrote is trusted.

Model in one paragraph: every service fails a fraction of its requests because of its own faults,
and inherits failures from the services it calls (hard dependency: all of them, soft: 30%). The
cost of a minute is the revenue lost at the edge services. Mitigations take a few minutes to land
and disturb the service while they do, so a mitigation that fixes nothing still costs money.
"""

import hashlib
import hmac
import json
import math
import random

HORIZON = 120  # minutes on shift after the page; unresolved faults are charged to the end
HISTORY = 180  # minutes of telemetry that exist before the page
MAX_CALLS = 400
HEADROOM = 1.6  # capacity over normal load at the normal replica count
SOFT = 0.3  # share of a soft dependency's failures that reach the caller
REPLICA_COST = 3  # $ per extra replica-minute
ALERT_ERR, ALERT_SAT = 0.05, 0.9

# tool: (minutes until it takes effect, error fraction it adds to the service meanwhile)
MITIGATIONS = {
    "rollback": (6, 0.15), "revert_config": (2, 0.0), "restart": (3, 0.3),
    "scale": (4, 0.0), "failover": (2, 1.0),
}
DATA_RESTART = (5, 1.0)  # restarting a datastore takes it fully down

SUBMITTED = 4  # the level run.sh and eval.py play when none is named; later levels are opt-in
LEVELS = {
    # round 0: one fault, free queries
    0: dict(edges=2, apps=7, datas=3, faults=1, query_min=0, act_min=0, wasted=2000),
    # lever 1: three concurrent faults (primary, masked, late) and two loud non-causes
    1: dict(edges=3, apps=14, datas=5, faults=3, query_min=0, act_min=0, wasted=2000),
    # lever 2: the level-1 worlds, but looking and acting take clock time and mitigations hurt more.
    # SRE Workbook ch. 5 (Alerting on SLOs): the error budget burns while you investigate.
    # "Generic mitigations" (Jennifer Mace, O'Reilly): every mitigation has a cost and a risk.
    2: dict(edges=3, apps=14, datas=5, faults=3, query_min=2, act_min=1, wasted=2000, world=1,
            disrupt=dict(rollback=0.3, restart=0.5)),
    # lever 3: scale and partial views. A large estate with one rich edge, an alert list that shows
    # only the loudest, short telemetry windows, a quiet fault its own service does not report, and
    # causes that sit in a diff. Clock costs and disruption are level 2's.
    # A mitigation nobody needed costs $10,000 here: at $2,000 guessing between a rollback and a config
    # revert was cheaper than reading the diffs, and a blind cycle of mitigations scored 0.95.
    3: dict(edges=4, apps=44, datas=12, faults=3, query_min=2, act_min=1, wasted=10000,
            disrupt=dict(rollback=0.3, restart=0.5), partial=True, share=0.27, gray_share=0.45, late=(45, 75)),
}
# lever 4: the level-3 worlds with retry storms. Callers retry failed calls, so a service that runs
# hot is pushed over capacity by its own failures and stays there after the cause is gone
# (Bronson et al., "Metastable Failures in Distributed Systems", HotOS 2021; postmortems.md: AWS
# Oct 2025 DWFM, Cloudflare Nov 2025 login backlog, GitHub 19 and 21 Oct 2026). The disruption of
# a rollback or restart counts too (postmortems.md: Microsoft 365 Nov 2026, restarts that fell over).
# The rich edge earns more than at level 3 (gray_share): retries make the loud faults cost more than
# the static estimate the share is taken from, and the quiet fault must stay worth a quarter.
LEVELS[4] = dict(LEVELS[3], world=3, storms=True, gray_share=0.6)
# lever 5: the level-4 worlds, but the primary fault is a generated file that is bad on some
# generations and then on all of them, so the estate fails, recovers and fails again (postmortems.md:
# Cloudflare 18 Nov 2025; GitHub 7 Oct 2026, a recovery "which looked like a fix"). One coincidence
# points elsewhere: a status page hosted outside the estate is down (Cloudflare 18 Nov 2025).
# The rich edge earns more again (gray_share): the file's consumers and their storms cost more than
# one primary did, and the quiet fault must stay worth a quarter. Callers of the consumer that the
# file takes down retry harder (FILE_RETRIES), so the storm it leaves is worth draining.
LEVELS[5] = dict(LEVELS[4], files=True, gray_share=0.75)
FILE_RETRIES = 5
EVERY = 5  # minutes between generations of a published file
FILE_SYMPTOM = "worker panicked loading rules file: {} entries, limit 200"
FILE_DIFF = "rules_source: [features] -> [features, r0.features]"
HOT = 1.32  # capacity over normal load of a service that runs hot (cpu 0.76): 3 retries hold it down
RETRIES = 3  # times a caller retries a failed call, where callers retry
STORM_LOG = 0.2  # share of retries among incoming requests that the service logs
TOP_ALERTS = 10  # an alert storm pages the loudest, not the most costly
WINDOW = 30  # minutes of metrics per query when views are partial

# Spike-only signing constant shared by the sidecar and verifier images. Not a credential.
RECEIPT_KEY = b"aq-incident-spike-receipt-v1"

EDGE_NAMES = ["web-storefront", "mobile-api", "partner-api", "admin-portal", "kiosk-api", "b2b-gateway"]
APP_WORDS = [
    "checkout", "cart", "catalog", "search", "pricing", "inventory", "auth", "payments", "shipping",
    "recommendations", "notifications", "profile", "promotions", "reviews", "tax", "fraud", "ledger",
    "wishlist", "geo", "media", "returns", "loyalty", "invoicing", "subscriptions", "currency",
    "address", "sessions", "quotes", "bundles", "giftcards", "vouchers", "stock", "couriers",
    "labels", "tracking", "emails", "sms", "push", "consent", "audit", "export", "import", "feeds",
    "ranking", "suggest", "images", "thumbnails", "translations", "seo", "sitemap", "banners",
    "experiments", "flags", "identity", "tokens", "risk", "limits", "refunds", "disputes", "payouts",
]
DATA_WORDS = [
    "orders-db", "users-db", "catalog-db", "sessions-cache", "events-queue", "search-index",
    "payments-db", "inventory-db", "pricing-cache", "ledger-db", "media-store", "audit-log",
    "profile-db", "promo-cache", "shipping-db", "risk-db",
]
DEPLOY_NOTES = [
    "weekly release", "dependency bump", "refactor request handlers", "add tracing spans",
    "logging cleanup", "new endpoint behind a flag", "library security patch", "query tuning",
]
CONFIG_NOTES = [
    "raise log level", "rotate credentials", "enable beta cohort 1%", "adjust cache ttl",
    "update allowlist", "tune connection pool", "change rate limit",
]
# SRE book ch. 12 (examine what changed, test the hypothesis): the log shows a symptom, the diff
# shows the cause. (symptom, harmful deploy hunk, harmful config line)
FLAVOURS = [
    ("TimeoutError: pool.acquire() exceeded 200ms",
     "db/client.py\n- pool = Pool(size=settings.db_pool_size)\n+ pool = Pool(size=4)", "db_pool_size: 40 -> 4"),
    ("TLS handshake failed: protocol version",
     "net/tls.py\n- ctx.minimum_version = TLSv1_2\n+ ctx.minimum_version = TLSv1_3", 'tls_min_version: "1.2" -> "1.3"'),
    ("KeyError: 'currency' in price formatter",
     'format/price.py\n- cur = row.get("currency", "EUR")\n+ cur = row["currency"]',
     "price_fields: [amount, currency, vat] -> [amount, vat]"),
    ("429 Too Many Requests: rate limiter bucket empty",
     "limits/bucket.py\n- refill = rate * elapsed\n+ refill = rate * elapsed / 1000", "rate_limit_per_s: 5000 -> 50"),
    ("DeadlineExceeded: rpc budget 50ms spent",
     "rpc/call.py\n- deadline = budget_ms / 1000\n+ deadline = budget_ms / 10000", "rpc_budget_ms: 500 -> 50"),
    ("StaleEntry: ttl elapsed before first read",
     "store/keys.py\n- expires = now + ttl_s\n+ expires = now + ttl_s // 600", "entry_ttl_s: 600 -> 1"),
    ("DecodeError: unknown wire schema 'v3'",
     'codec/wire.py\n- schema = "v2"\n+ schema = "v3"', "wire_schema: v2 -> v3"),
    ("PermissionDenied: scope 'orders.write' missing",
     'auth/scopes.py\n- SCOPES = ["orders.read", "orders.write"]\n+ SCOPES = ["orders.read"]',
     "token_scope: [orders.read, orders.write] -> [orders.read]"),
]
# what each change note really did; a harmful change carries its hunk after these lines
ORDINARY_DIFFS = {
    "weekly release": 'ui/strings.py\n- TITLE = "Add to basket"\n+ TITLE = "Add to bag"',
    "dependency bump": "requirements.txt\n- httpx==0.27.0\n+ httpx==0.27.2",
    "refactor request handlers": "handlers/base.py\n- tmp = load(req)\n+ payload = load(req)",
    "add tracing spans": 'handlers/base.py\n+ with tracer.span("handle"):',
    "logging cleanup": 'handlers/base.py\n- log.info("got request %s", req)\n+ log.debug("request %s", req.id)',
    "new endpoint behind a flag": 'routes.py\n+ if flags.on("preview"): app.add("/v2/preview", preview)',
    "library security patch": "requirements.txt\n- urllib3==2.2.1\n+ urllib3==2.2.2",
    "query tuning": "queries.sql\n- SELECT * FROM items WHERE sku = ?\n+ SELECT id, sku, qty FROM items WHERE sku = ?",
    "raise log level": "log_level: info -> warn",
    "rotate credentials": "db_password_ref: vault:v41 -> vault:v42",
    "enable beta cohort 1%": "beta_cohort_pct: 0 -> 1",
    "adjust cache ttl": "page_cache_seconds: 300 -> 360",
    "update allowlist": "ip_allowlist: + 10.4.0.0/16",
    "tune connection pool": "conn_idle_seconds: 300 -> 240",
    "change rate limit": "burst_allowance: 200 -> 220",
}
NOISE_LINES = [
    ("WARN", "deprecated config key 'legacy.mode' is ignored"),
    ("WARN", "slow query took 800 ms"),
    ("INFO", "cache refresh completed"),
    ("WARN", "retrying idempotent call after timeout"),
    ("INFO", "scheduled compaction finished"),
    ("WARN", "client sent malformed header, request rejected (400)"),
]


def scenario(seed, level):
    """The hidden estate and its faults. One RNG per purpose so adding a draw never shifts another."""
    cfg = LEVELS[level]

    def rng(purpose):
        return random.Random(f"{seed}:{cfg.get('world', level)}:{purpose}")

    datas = rng("data-names").sample(DATA_WORDS, cfg["datas"])
    apps = [f"{w}-svc" for w in rng("app-names").sample(APP_WORDS, cfg["apps"])]
    edges = EDGE_NAMES[: cfg["edges"]]
    svc = {}
    r = rng("topology")
    for name in datas:
        svc[name] = dict(tier="data", deps=[])
    for i in reversed(range(len(apps))):  # later apps are deeper, so the graph has no cycles
        deeper = apps[i + 1:]
        deps = r.sample(deeper, min(len(deeper), r.choice([0, 1, 1, 2])))
        deps += r.sample(datas, r.choice([1, 1, 2]) if not deps else r.choice([0, 1]))
        svc[apps[i]] = dict(tier="app", deps=[[d, 1.0 if r.random() < 0.7 else SOFT] for d in deps])
    front = apps[: max(3, len(apps) // 2)]
    for name in edges:
        svc[name] = dict(tier="edge", deps=[[d, 1.0] for d in r.sample(front, min(len(front), r.choice([3, 4])))])
    r = rng("shape")
    for name, s in svc.items():
        s.update(
            revenue=r.randrange(300, 900, 50) if s["tier"] == "edge" else 0,
            rps=r.randrange(200, 2000, 50), replicas=r.choice([3, 4, 6, 8]), p99=r.randrange(40, 240, 10),
            noise=r.sample(NOISE_LINES, r.choice([1, 2, 2])), changes=[],
        )

    # how much revenue a service can take down
    order = datas + apps[::-1] + edges
    top = rng("rich").choice(edges) if cfg.get("partial") else None  # the edge that earns most

    def errs(own):
        err = {}
        for name in order:
            ok = 1 - own.get(name, 0)
            for dep, w in svc[name]["deps"]:
                ok *= 1 - w * err[dep]
            err[name] = 1 - ok
        return err

    def lost(own):
        """Revenue lost per minute when each service in `own` fails that share of its requests."""
        err = errs(own)
        return sum(svc[e]["revenue"] * err[e] for e in edges)

    impact = {target: lost({target: 1.0}) for target in order}

    def kinds_of(name):
        return ["bad_deploy", "bad_config", "leak", "overload"] if svc[name]["tier"] == "app" else [
            "primary_down", "overload", "bad_config"]

    def make(name, kinds):
        kind = r.choice(kinds)
        f = dict(kind=kind, service=name, start=r.randint(-25, -8), sev=round(r.uniform(0.4, 0.9), 2),
                 end=None, change=None)
        if kind == "leak":  # a deploy hours ago; memory fills up shortly before the page
            f["grow"] = r.randint(70, 130)
            f["start"] = r.randint(-20, -8) - f["grow"]
        if kind == "overload":
            f["load"] = round(r.uniform(2.0, 3.0), 2)
        return f

    def hard_callers(target):
        out = []
        for name in order:
            if any(w == 1.0 and (d == target or d in out) for d, w in svc[name]["deps"]):
                out.append(name)
        return out

    r = rng("faults")
    pool = [n for n in apps + datas if impact[n] >= 200]
    faults, batch, benign, blamed = [], None, None, None
    files, quiet_pubs = {}, {}
    if top:
        # SRE Workbook ch. 5: alert on budget burn, not raw error rate. Loud is not costly: the
        # loud faults stay off the richest edge where the estate allows it.
        cheap = [n for n in pool if not errs({n: 1.0})[top]]
        pool = cheap if len(cheap) >= 3 else pool
    if cfg["faults"] == 1:
        for name in r.sample(pool, cfg["faults"]):
            faults.append(make(name, kinds_of(name)))
    else:
        # OpenRCA 2.0 (arXiv 2606.27154): 20.7% exact root-cause set vs 76.0% single service, so the
        # score needs all three causes. Redraw until each one is worth a real share of the shift.
        high = sorted(pool, key=lambda n: -impact[n])[: max(2, len(pool) // 2)]
        best = None
        for _ in range(300):
            p = r.choice(high)
            m = r.choice([n for n in hard_callers(p) if n in pool] or [n for n in pool if n != p])
            late = r.choice([n for n in pool if n not in (p, m)])
            fp = make(p, kinds_of(p))
            # masked: fails for its own reasons, but looks like one more victim of the primary
            fm = make(m, [k for k in kinds_of(m) if k != fp["kind"]])
            fm["sev"] = round(r.uniform(0.3, 0.6), 2)
            # SRE book ch. 1: about 70% of outages come from changes to a live system; this one
            # lands mid-shift, after the first fixes
            fl = make(late, [k for k in kinds_of(late) if k in ("bad_deploy", "bad_config")
                             and k not in (fp["kind"], fm["kind"])] or ["bad_config"])
            fl["start"] = r.randint(*cfg.get("late", (20, 50)))
            sev = {f["service"]: 1 - HEADROOM / f["load"] if f["kind"] == "overload" else f["sev"]
                   for f in (fp, fm, fl)}
            both = {p: sev[p], m: sev[m]}
            shares = [(lost(both) - lost({m: sev[m]})) * HORIZON, lost({m: sev[m]}) * HORIZON,
                      lost({late: sev[late]}) * (HORIZON - fl["start"])]
            total = lost(both) * fl["start"] + lost(sev) * (HORIZON - fl["start"])
            if best is None or min(shares) / total > best[0]:
                best = (min(shares) / total, [fp, fm, fl], total)
            if best[0] >= cfg.get("share", 0.2):
                break
        faults = best[1]
        taken = [f["service"] for f in faults]
        r = rng("decoys")
        # Google SRE book ch. 12 (Effective Troubleshooting): correlation is not causation. A victim
        # of the primary got an ordinary change a few minutes before its symptoms began.
        onset = faults[0]["start"] + faults[0].get("grow", 0)
        victims = [n for n in hard_callers(faults[0]["service"]) if n not in taken]
        if victims:
            benign = dict(service=r.choice(victims), type=r.choice(["deploy", "config"]),
                          minute=onset - r.randint(3, 10))
            taken.append(benign["service"])
        # ORCA-bench (arXiv 2607.28545): models lock onto the loudest symptom. A scheduled batch job
        # saturates a healthy service shortly before the page and fails nothing.
        batch = dict(service=r.choice([n for n in apps if n not in taken]), start=-r.randint(4, 12),
                     end=r.randint(50, 100))
        if top:
            # Gray failure (Huang et al., HotOS 2017), differential observability: the callers see
            # the failure, the component's own telemetry does not. Small enough to trip no alert,
            # on a hard path of the richest edge.
            r = rng("gray")
            taken.append(batch["service"])
            sev = round(r.uniform(0.03, 0.045), 3)

            def quiet(n):
                err = errs({n: sev})
                return err[top] >= sev - 1e-9 and max(err.values()) <= sev + 1e-9

            def callers(n):
                return [c for c in order if [n, 1.0] in svc[c]["deps"] and c not in taken
                        and (c == top or top in hard_callers(c))]

            cands = [n for n in apps + datas if n not in taken and quiet(n) and callers(n)]
            x = r.choice([n for n in cands if any(svc[c]["tier"] == "app" for c in callers(n))] or cands)
            gray = dict(kind=r.choice(["bad_deploy", "bad_config"]) if x in apps else "bad_config", service=x,
                        start=r.randint(-45, -12), sev=sev, end=None, change=None, gray=True)
            if cfg.get("storms"):  # GitHub 21 Oct 2026 (postmortems.md): the fix itself must be staged
                gray["kind"] = rng("gray-kind").choice(["bad_deploy", "bad_config"]) if cfg.get("files") else "bad_deploy"
            if gray["kind"] == "bad_deploy":  # a rollback disturbs the rich edge, so it must pay
                gray["sev"] = sev = max(sev, 0.04)
            # the tempting wrong rollback: a caller of X changed a few minutes before X broke
            blamed = dict(service=r.choice([c for c in callers(x) if svc[c]["tier"] == "app"] or callers(x)),
                          type=r.choice(["deploy", "config"]), minute=gray["start"] - r.randint(3, 8))
            # worth a set share of the loud faults, net of what undoing it disturbs
            net = sev * HORIZON - (MITIGATIONS["rollback"][0] * cfg["disrupt"]["rollback"]
                                   if gray["kind"] == "bad_deploy" else 0)
            svc[top]["revenue"] = int(max(4 * max(svc[e]["revenue"] for e in edges),
                                          round(cfg["gray_share"] * best[2] / net, -2)))
            faults.append(gray)
            if cfg.get("files"):
                # Cloudflare 18 Nov 2025 (postmortems.md): a file "generated every five minutes" was bad
                # only on some runs, so "the entire system would recover and then fail again", until
                # "the fluctuation stabilized in the failing state". The primary's service becomes a
                # consumer of the file; the fault sits at the publisher, which stays healthy.
                r, old = rng("files"), faults[0]
                hit, used = old["service"], set(taken) | {x, blamed["service"]}
                pub = r.choice([n for n in apps if n not in used and n not in dict(svc[hit]["deps"])])
                rest = [n for n in apps + datas if n not in used and n != pub and pub not in dict(svc[n]["deps"])
                        and not errs({n: 1.0})[top]]
                apart = [n for n in rest if impact[n] >= 200 and not errs({hit: 1.0})[n] and not errs({n: 1.0})[hit]]
                flap = r.choice(apart or [n for n in rest if impact[n]] or rest)  # not hot: it visibly flaps
                fed = [hit, flap] + r.sample([n for n in rest if n != flap], r.choice([0, 1, 2]))
                files = {c: pub for c in fed}
                others = r.sample([n for n in apps if n not in used and n != pub and n not in fed], r.choice([2, 3]))
                for q in others:  # publishers whose file is fine, so a file relation gives nothing away
                    open_ = [n for n in apps + datas if n not in files and n != pub and n not in others
                             and q not in dict(svc[n]["deps"])]
                    files.update({c: q for c in r.sample(open_, r.choice([2, 3, 4]))})
                    quiet_pubs[q] = -r.randint(20, 200)
                for q in [pub] + others:
                    svc[q]["file"] = r.randint(120, 190)  # entries in a good file; a bad one has twice as many
                start = old["start"] + old.get("grow", 0)
                first, stuck = EVERY * math.ceil(start / EVERY), r.randint(15, 40)
                faults[0] = dict(kind="bad_file", service=pub, start=start, sev=0.0, end=None, change=None, stuck=stuck,
                                 hits={c: round(r.uniform(0.5, 0.85), 2) for c in fed},
                                 bad=[first] + [t for t in range(first + EVERY, stuck, EVERY) if r.random() < 0.5])

    planted = {f["service"]: ("deploy" if f["kind"] in ("bad_deploy", "leak") else "config", f["start"], f)
               for f in faults if f["kind"] in ("bad_deploy", "bad_config", "leak", "bad_file")}
    # every publisher has a deploy and a config change that landed together a few minutes before the
    # page, so neither the pair nor its timing says which file is bad: the diffs do
    rp, drawn = rng("pub-twins"), dict(quiet_pubs)
    planted.update({q: ("config", rp.randint(-25, -8), None) for q in quiet_pubs})
    for b in (benign, blamed):
        if b:
            planted[b["service"]] = (b["type"], b["minute"], None)
    r, r2 = rng("changes"), rng("twins")
    for name in order:
        plant = planted.get(name)
        latest = min(drawn.get(name, plant[1]) - 10, -18) if plant else -30
        times = sorted(r.randint(-1440, latest) for _ in range(r.choice([0, 1, 1, 2, 3])))
        for t in times:
            kind = r.choice(["deploy", "deploy", "config"])
            svc[name]["changes"].append(dict(type=kind, minute=t, summary=r.choice(
                DEPLOY_NOTES if kind == "deploy" else CONFIG_NOTES), live=True))
        if name in quiet_pubs:  # nothing else close to the pair, as at the faulty publisher
            svc[name]["changes"] = [c for c in svc[name]["changes"] if c["minute"] <= plant[1] - 10]
        if plant:
            kind = plant[0]
            cause = dict(type=kind, minute=plant[1], summary=r.choice(
                DEPLOY_NOTES if kind == "deploy" else CONFIG_NOTES), live=True)
            svc[name]["changes"].append(cause)
            if top and plant[2] and plant[2]["kind"] != "leak":
                # an ordinary change of the other type lands in the same minute (one release train),
                # listed before or after it, so neither timing nor old logs settle which to undo
                svc[name]["changes"].append(dict(
                    type="config" if kind == "deploy" else "deploy", minute=plant[1], rank=r2.choice([-2, -1, 1, 2]),
                    summary=r2.choice(CONFIG_NOTES if kind == "deploy" else DEPLOY_NOTES), live=True))
                svc[name]["changes"].sort(key=lambda c: (c["minute"], c.get("rank", 0)))
            elif name in quiet_pubs:
                svc[name]["changes"].append(dict(type="deploy", minute=plant[1], rank=rp.choice([-2, -1, 1, 2]),
                                                 summary=rp.choice(DEPLOY_NOTES), live=True))
                svc[name]["changes"].sort(key=lambda c: (c["minute"], c.get("rank", 0)))
        n_dep, n_cfg = r.randint(11, 180), r.randint(3, 60)
        for c in svc[name]["changes"]:
            if c["type"] == "deploy":
                n_dep += 1
                c["id"] = f"v{n_dep}"
            else:
                n_cfg += 1
                c["id"] = f"cfg-{n_cfg}"
        if plant and plant[2]:
            plant[2]["change"] = cause["id"]
    if top:
        named = [f for f in faults if f["kind"] in ("bad_deploy", "bad_config")]
        for f, i in zip(named, rng("flavours").sample(range(len(FLAVOURS)), len(named))):
            f["flavour"] = i
    if cfg.get("storms"):
        # the primary's and the quiet fault's services run hot with retrying callers, and so does
        # a quarter of the rest, so neither property gives a fault away
        r, sure = rng("hot"), (next(iter(files), faults[0]["service"]), faults[-1]["service"])
        for name in order:
            roll = 0.0 if name in sure else r.random()
            tier = svc[name]["tier"] != "edge"
            svc[name].update(cap=HOT if tier and roll < 0.35 else HEADROOM,
                             retry=RETRIES if tier and (roll < 0.25 or roll >= 0.7) else 0)
    if files:
        svc[list(files)[0]].update(retry=FILE_RETRIES)
        svc[list(files)[1]].update(cap=HEADROOM, retry=0)
        # one consumer of every publisher has callers that retry as hard, so the count names no file
        r, own = rng("file-retries"), {f["service"] for f in faults} | {batch["service"]}
        for q in quiet_pubs:
            mine = [c for c in files if files[c] == q]
            svc[r.choice([c for c in mine if c not in own] or mine)]["retry"] = FILE_RETRIES
        # Cloudflare 18 Nov 2025 (postmortems.md): the status page, hosted elsewhere, went down at the
        # same time; "it turned out to be a coincidence"
        r = rng("status")
        svc["status-page"] = dict(tier="external", deps=[], revenue=0, rps=r.randrange(50, 300, 50), replicas=2,
                                  p99=r.randrange(40, 240, 10), noise=[], changes=[], cap=HEADROOM, retry=0,
                                  down=(-r.randint(2, 9), r.randint(85, 110)))
        order.insert(0, "status-page")
    return dict(svc=svc, order=order, edges=edges, faults=faults, batch=batch, files=files)


class Estate:
    TOOLS = {
        "get_status": (), "get_topology": (), "list_alerts": (),
        "get_metrics": ("service",), "get_logs": ("service",), "get_changes": ("service",),
        "rollback": ("service",), "revert_config": ("service",), "restart": ("service",),
        "scale": ("service", "replicas"), "failover": ("service",),
        "wait": ("minutes",), "finish": (),
    }
    QUERIES = {"list_alerts", "get_metrics", "get_logs", "get_changes", "get_diff"}
    OPTIONAL = {"list_alerts": ("tier",), "get_metrics": ("until_minute",), "get_logs": ("until_minute",)}

    def __init__(self, seed, level=0):
        sc = scenario(seed, level)
        self.seed, self.cfg = seed, LEVELS[level]
        self.svc, self.order, self.edges, self.faults = sc["svc"], sc["order"], sc["edges"], sc["faults"]
        self.batch, self.files = sc["batch"], sc["files"]
        self.partial = bool(self.cfg.get("partial"))
        if self.partial:
            self.TOOLS = dict(self.TOOLS, get_diff=("service", "change_id"))
        self.storms = bool(self.cfg.get("storms"))
        if self.storms:
            self.TOOLS = dict(self.TOOLS, throttle=("service", "percent"))
        self.throttles = {}  # service -> [(effective minute, share rejected up front)]
        self._states = []  # per minute from -HISTORY: service -> (own failures, retries per request, utilisation)
        self.now = 0
        self.done = False
        self.actions = []
        self.disrupt = []  # (service, from, to, error fraction)
        self.scales = {}  # service -> [(effective minute, replicas)]
        self.resets = {}  # service -> [minute the process restarted]
        self.ops = []  # (service, tool, completes at)
        self.wasted = 0
        self._memo = {}

    # --- the model ------------------------------------------------------------------

    def _noise(self, *key):
        digest = hashlib.blake2b(f"{self.seed}:{key}".encode(), digest_size=2).digest()
        return int.from_bytes(digest, "big") / 65535

    def _replicas(self, name, t):
        reps = self.svc[name]["replicas"]
        for at, n in self.scales.get(name, ()):
            if at <= t:
                reps = n
        return reps

    def _load(self, name, t):
        load = 1.0
        for f in self.faults:
            if f["service"] == name and f["kind"] == "overload" and f["start"] <= t:
                load *= f["load"]
        return load

    def _bad_file(self, f, t):
        """Whether the generation of the file that is current at minute t is a bad one."""
        made = EVERY * (t // EVERY)
        return (f["end"] is None or made < f["end"]) and (made >= f["stuck"] or made in f["bad"])

    def _leak_fill(self, f, t):
        """0..1+ share of memory a leaking process has filled at minute t."""
        if t < f["start"] or (f["end"] is not None and t >= f["end"]):
            return 0.0
        last = max([f["start"]] + [r for r in self.resets.get(f["service"], ()) if r <= t])
        return (t - last) / f["grow"]

    def _fault_sev(self, f, t):
        if t < f["start"] or (f["end"] is not None and t >= f["end"]):
            return 0.0
        if f["kind"] == "overload":
            return 0.0  # handled by capacity below
        if f["kind"] == "leak":
            return f["sev"] if self._leak_fill(f, t) >= 1 else 0.0
        return f["sev"]

    def _throttle(self, name, t):
        share = 0.0
        for at, p in self.throttles.get(name, ()):
            if at <= t:
                share = p
        return share

    def _state(self, t):
        """Retry storms: each minute's load carries the retries of last minute's own failures
        (Bronson et al., HotOS 2021), so the estate is stepped forward from the start of history."""
        while len(self._states) <= t + HISTORY:
            m, prev, cur = len(self._states) - HISTORY, self._states[-1] if self._states else {}, {}
            for name in self.order:
                s = self.svc[name]
                back = s["retry"] * prev[name][0] if prev else 0.0
                util = (self._load(name, m) * (1 + back) * (1 - self._throttle(name, m)) * s["replicas"]
                        / (self._replicas(name, m) * s["cap"]))
                ok = min(1.0, 1 / util)
                for f in self.faults:
                    if f["service"] == name:
                        ok *= 1 - self._fault_sev(f, m)
                    if name in f.get("hits", ()) and self._bad_file(f, m):
                        ok *= 1 - f["hits"][name]
                for n, t0, t1, sev in self.disrupt:
                    if n == name and t0 <= m < t1:
                        ok *= 1 - sev
                if "down" in s and s["down"][0] <= m < s["down"][1]:
                    ok = 0.0
                cur[name] = (1 - ok, back, util)
            self._states.append(cur)
        return self._states[t + HISTORY]

    def _forget(self):
        """An action at minute `now` changes nothing before it: keep the past, recompute the rest."""
        self._memo = {t: err for t, err in self._memo.items() if t < self.now} if self.storms else {}
        del self._states[max(0, self.now + HISTORY):]

    def _own(self, name, t):
        """Share of requests this service fails for its own reasons at minute t."""
        if self.storms:
            return self._state(t)[name][0]
        util = self._load(name, t) * self.svc[name]["replicas"] / (self._replicas(name, t) * HEADROOM)
        ok = min(1.0, 1 / util)
        for f in self.faults:
            if f["service"] == name:
                ok *= 1 - self._fault_sev(f, t)
        for s, t0, t1, sev in self.disrupt:
            if s == name and t0 <= t < t1:
                ok *= 1 - sev
        return 1 - ok

    def _err(self, t):
        """Error fraction of every service at minute t."""
        if t not in self._memo:
            err = {}
            for name in self.order:
                ok = (1 - self._own(name, t)) * (1 - self._throttle(name, t))
                for dep, w in self.svc[name]["deps"]:
                    ok *= 1 - w * err[dep]
                err[name] = 1 - ok
            self._memo[t] = err
        return self._memo[t]

    def _batch(self, name, t):
        b = self.batch
        return bool(b) and b["service"] == name and b["start"] <= t < b["end"]

    def _retry_share(self, name, t, back):
        """Share of incoming requests that are retries. A calm service shows a little background
        retry traffic too, so a nonzero share alone gives nothing away."""
        share = back / (1 + back)
        return round(share if share >= 0.005 else 0.02 * self._noise(name, "retry", t), 2)

    def _metrics(self, name, t):
        s = self.svc[name]
        err, own = self._err(t)[name], self._own(name, t)
        for f in self.faults:  # a gray fault under-reports: only what its dependencies explain
            if f["service"] == name and f.get("gray") and self._fault_sev(f, t):
                err, own = 1 - (1 - err) / (1 - f["sev"]), 1 - (1 - own) / (1 - f["sev"])
        load, reps = self._load(name, t), self._replicas(name, t)
        fill = max([self._leak_fill(f, t) for f in self.faults if f["service"] == name and f["kind"] == "leak"] or [0])
        crashes = sum(
            1 for f in self.faults if f["service"] == name and f["kind"] == "leak"
            for m in range(t - 29, t + 1, 3) if self._leak_fill(f, m) >= 1)
        crashes += sum(1 for r in self.resets.get(name, ()) if t - 30 < r <= t)
        p99 = s["p99"] * (1 + 5 * own + 2.5 * (err - own)) * (0.95 + 0.1 * self._noise(name, "p99", t))
        busy = load * s["replicas"] / (reps * HEADROOM)
        if self.storms:  # rps is what arrives, retries included; cpu is what was let in
            _, back, busy = self._state(t)[name]
            load *= 1 + back
        cpu = min(0.99, busy + 0.03 * self._noise(name, "cpu", t))
        if self._batch(name, t):
            p99, cpu = 3 * p99, max(cpu, 0.97 + 0.02 * self._noise(name, "cpu", t))
        return dict(
            minute=t,
            error_rate=round(min(1.0, err + 0.004 * self._noise(name, "err", t)), 4),
            p99_ms=round(p99),
            rps=round(s["rps"] * load * (1 + 0.05 * math.sin(t / 37 + len(name)))),
            cpu=round(cpu, 2),
            mem=round(min(0.99, 0.42 + 0.56 * min(1.0, fill) + 0.03 * self._noise(name, "mem", t)), 2),
            replicas=reps, restarts_30m=crashes, **({"retry_share": self._retry_share(name, t, back)} if self.storms else {}),
        )

    def _cost(self):
        outage = sum(self.svc[e]["revenue"] * self._err(t)[e] for t in range(HORIZON) for e in self.edges)
        extra = sum(
            max(0, self._replicas(n, t) - self.svc[n]["replicas"]) for n in self.scales for t in range(HORIZON))
        return dict(outage=round(outage, 2), replicas=extra * REPLICA_COST, wasted=self.wasted)

    def total_cost(self):
        return round(sum(self._cost().values()), 2)

    # --- queries --------------------------------------------------------------------

    def get_status(self):
        err = self._err(self.now)
        return dict(
            ok=True, minute=self.now, minutes_left=HORIZON - self.now, shift_over=self.done,
            edge=[dict(service=e, error_rate=round(err[e], 4), revenue_per_min=self.svc[e]["revenue"])
                  for e in self.edges],
            operations_in_progress=[dict(service=s, action=a, completes_at_minute=at)
                                    for s, a, at in self.ops if at > self.now],
            **({"throttles": [dict(service=s, percent=round(100 * ps[-1][1])) for s, ps in self.throttles.items()
                              if ps[-1][1]]} if self.storms else {}),
        )

    def get_topology(self):
        return dict(ok=True, services=[
            dict(name=n, tier=self.svc[n]["tier"], normal_replicas=self.svc[n]["replicas"],
                 revenue_per_min=self.svc[n]["revenue"], **({"callers_retry": self.svc[n]["retry"]} if self.storms else {}),
                 **({"file_from": self.files[n]} if n in self.files else {}),
                 depends_on=[dict(service=d, kind="hard" if w == 1.0 else "soft") for d, w in self.svc[n]["deps"]])
            for n in reversed(self.order)])

    def _since(self, test):
        t = self.now
        while t > -HISTORY and test(t - 1):
            t -= 1
        return t

    def list_alerts(self, tier=None):
        alerts = []
        for name in self.order:
            if tier and self.svc[name]["tier"] != tier:
                continue
            m = self._metrics(name, self.now)
            for signal, limit in (("error_rate", ALERT_ERR), ("cpu", ALERT_SAT), ("mem", ALERT_SAT)):
                if m[signal] >= limit:
                    alerts.append(dict(
                        service=name, signal=signal, value=m[signal],
                        firing_since_minute=self._since(lambda t: self._metrics(name, t)[signal] >= limit)))
        alerts.sort(key=lambda a: (-a["value"], a["service"]))
        if self.partial:
            return dict(ok=True, minute=self.now, total=len(alerts), alerts=alerts[:TOP_ALERTS])
        return dict(ok=True, minute=self.now, alerts=alerts)

    def get_metrics(self, service, until_minute=None):
        if self.partial:
            t = self.now if until_minute is None else until_minute
            return dict(ok=True, service=service,
                        series=[self._metrics(service, m) for m in range(t - WINDOW, t + 1, 5)])
        return dict(ok=True, service=service,
                    series=[self._metrics(service, t) for t in range(self.now - 60, self.now + 1, 10)])

    def get_logs(self, service, until_minute=None):
        s, t = self.svc[service], self.now if until_minute is None else until_minute
        err = self._err(t)
        volume = s["rps"] * 600
        lines = [dict(level=lv, message=msg, count=20 + int(200 * self._noise(service, msg))) for lv, msg in s["noise"]]
        for dep, w in s["deps"]:
            if w * err[dep] >= 0.01:
                why = next((FLAVOURS[f["flavour"]][0] for f in self.faults
                            if f["service"] == dep and "flavour" in f and self._fault_sev(f, t)), "503 or timeout")
                lines.append(dict(level="ERROR", message=f"upstream call to {dep} failed ({why})",
                                  count=int(volume * w * err[dep])))
        for f in self.faults:
            sev = self._fault_sev(f, t)
            if f["service"] != service:
                continue
            if "flavour" in f:  # the log names a symptom, not the change; a gray fault logs nothing
                if sev and not f.get("gray"):
                    lines.append(dict(level="ERROR", count=int(volume * sev), message=FLAVOURS[f["flavour"]][0]))
            elif f["kind"] == "bad_deploy" and sev:
                lines.append(dict(level="ERROR", count=int(volume * sev), message=(
                    f"unhandled exception in request handler (first seen in build {f['change']})")))
            elif f["kind"] == "bad_config" and sev:
                lines.append(dict(level="ERROR", count=int(volume * sev), message=(
                    f"request rejected: setting loaded from {f['change']} is invalid")))
            if f["kind"] == "primary_down" and sev:
                lines.append(dict(level="ERROR", count=int(volume * sev),
                                  message="primary node unreachable, write rejected"))
            if f["kind"] == "leak" and self._leak_fill(f, t) >= 0.9:
                lines.append(dict(level="WARN", count=40, message="heap above 95%, long GC pause"))
                if sev:
                    lines.append(dict(level="FATAL", count=self._metrics(service, t)["restarts_30m"],
                                      message="out of memory: container killed and restarted"))
        for f in self.faults:
            if service in f.get("hits", ()) and self._bad_file(f, t):
                lines.append(dict(level="ERROR", count=int(volume * f["hits"][service]),
                                  message=FILE_SYMPTOM.format(2 * self.svc[f["service"]]["file"])))
        if "file" in s:  # a publisher logs each generation: two in ten minutes
            bad = any(f["service"] == service and f["kind"] == "bad_file" and self._bad_file(f, t) for f in self.faults)
            lines.append(dict(level="INFO", count=2, message=f"rules file generated: {s['file'] * (2 if bad else 1)} entries"))
        if "down" in s and s["down"][0] <= t < s["down"][1]:
            lines.append(dict(level="ERROR", count=volume, message="connection refused by hosting provider"))
        util = self._load(service, t) * s["replicas"] / (self._replicas(service, t) * HEADROOM)
        if self.storms:
            _, back, util = self._state(t)[service]
            if back / (1 + back) > STORM_LOG:  # Cloudflare Nov 2025 (postmortems.md): backlog plus retries
                lines.append(dict(level="WARN", count=int(volume * back), message=(
                    f"retry storm: {back / (1 + back):.0%} of incoming requests are retries of failed calls")))
            if self._throttle(service, t):
                lines.append(dict(level="WARN", count=int(volume * (1 + back) * self._throttle(service, t)),
                                  message="throttle active: request rejected up front (429)"))
        if util > 1:
            lines.append(dict(level="WARN", count=int(volume * (1 - 1 / util)),
                              message="request queue full, shedding load (503)"))
        if self._batch(service, t):
            lines.append(dict(level="WARN", count=int(volume * 0.2),
                              message="scheduled job nightly-rollup is running: worker threads busy, slow response"))
        if any(n == service and t0 <= t < t1 for n, t0, t1, _ in self.disrupt):
            lines.append(dict(level="INFO", count=s["replicas"], message="instance restarting"))
        lines.sort(key=lambda line: -line["count"])
        if self.partial:
            return dict(ok=True, service=service, window=f"rates at minute {t}, as counts per 10 minutes", lines=lines)
        return dict(ok=True, service=service, window="rates now, as counts per 10 minutes", lines=lines)

    def get_changes(self, service):
        return dict(ok=True, service=service, window="last 24 hours", changes=[
            dict(id=c["id"], type=c["type"], minute=c["minute"], summary=c["summary"],
                 status="live" if c["live"] else "reverted")
            for c in self.svc[service]["changes"] if c["minute"] <= self.now])

    def get_diff(self, service, change_id):
        for c in self.svc[service]["changes"]:
            if c["id"] == change_id and c["minute"] <= self.now:
                # every change is two hunks, in either order, so the shape of a diff says nothing
                notes = [n for n in (DEPLOY_NOTES if c["type"] == "deploy" else CONFIG_NOTES) if n != c["summary"]]
                pick = int(self._noise(service, "diff:" + change_id) * 1000)
                parts = [ORDINARY_DIFFS[c["summary"]], ORDINARY_DIFFS[notes[pick % len(notes)]]]
                for f in self.faults:
                    if f["service"] == service and f["change"] == change_id and "flavour" in f:
                        parts[1] = FLAVOURS[f["flavour"]][1 if c["type"] == "deploy" else 2]
                    if f["service"] == service and f["change"] == change_id and f["kind"] == "bad_file":
                        parts[1] = FILE_DIFF
                if pick % 2:
                    parts.reverse()
                return dict(ok=True, service=service, id=change_id, type=c["type"], diff="\n".join(parts))
        return dict(ok=False, error=f"{service} has no such change in the last 24 hours")

    # --- mitigations ----------------------------------------------------------------

    def _start(self, service, tool, timing=None):
        minutes, sev = timing or MITIGATIONS[tool]
        if not timing:
            sev = self.cfg.get("disrupt", {}).get(tool, sev)
        done_at = self.now + minutes
        if sev:
            self.disrupt.append((service, self.now, done_at, sev))
        self.ops.append((service, tool, done_at))
        self._forget()
        return done_at

    def _end_faults(self, service, at, kinds, change=None):
        ended = 0
        for f in self.faults:
            if f["service"] == service and f["kind"] in kinds and f["end"] is None and f["start"] <= self.now:
                if change is None or f["change"] == change:
                    f["end"] = at
                    ended += 1
        if not ended:
            self.wasted += self.cfg["wasted"]
        return ended

    def _revert(self, service, tool, kind, kinds):
        live = [c for c in self.svc[service]["changes"] if c["type"] == kind and c["live"] and c["minute"] <= self.now]
        if not live:
            return dict(ok=False, error=f"{service} has no live {kind} from the last 24 hours to revert")
        at = self._start(service, tool)
        live[-1]["live"] = False
        self._end_faults(service, at, kinds, live[-1]["id"])
        if kind == "deploy":
            self.resets.setdefault(service, []).append(at)
        return dict(ok=True, service=service, reverted=live[-1]["id"], completes_at_minute=at)

    def rollback(self, service):
        return self._revert(service, "rollback", "deploy", ("bad_deploy", "leak"))

    def revert_config(self, service):
        # a bad file already loaded stays until the publisher's next generation (Cloudflare 18 Nov 2025)
        return self._revert(service, "revert_config", "config", ("bad_config", "bad_file"))

    def restart(self, service):
        at = self._start(service, "restart", DATA_RESTART if self.svc[service]["tier"] == "data" else None)
        self.resets.setdefault(service, []).append(at)
        if not any(f["service"] == service and f["kind"] == "leak" and f["end"] is None for f in self.faults):
            self.wasted += self.cfg["wasted"]
        return dict(ok=True, service=service, completes_at_minute=at)

    def scale(self, service, replicas):
        normal = self.svc[service]["replicas"]
        if not 1 <= replicas <= 4 * normal:
            return dict(ok=False, error=f"replicas must be between 1 and {4 * normal}")
        at = self._start(service, "scale")
        self.scales.setdefault(service, []).append((at, replicas))
        # going back to the normal count undoes a scale-up; charging it would punish the correction.
        # GitHub 5 Oct 2026 (postmortems.md): "failed over ... one service at a time, and added
        # capacity". Where retries can hold a service down, capacity before a risky change is the
        # expert move: it costs its replicas and its minute, never the fine.
        if replicas != normal and not self.storms and not any(
                f["service"] == service and f["kind"] == "overload" and f["start"] <= self.now for f in self.faults):
            self.wasted += self.cfg["wasted"]
        return dict(ok=True, service=service, replicas=replicas, completes_at_minute=at)

    def failover(self, service):
        if self.svc[service]["tier"] != "data":
            return dict(ok=False, error="failover only applies to data-tier services")
        at = self._start(service, "failover")
        self._end_faults(service, at, ("primary_down",))
        return dict(ok=True, service=service, completes_at_minute=at)

    def throttle(self, service, percent):
        # AWS Oct 2025 (postmortems.md): throttles drained the backlog and stayed until lifted by hand
        if not 0 <= percent <= 90:
            return dict(ok=False, error="percent must be between 0 and 90")
        self.throttles.setdefault(service, []).append((self.now + 1, percent / 100))
        self._forget()
        return dict(ok=True, service=service, percent=percent, effective_at_minute=self.now + 1)

    def wait(self, minutes):
        if not 1 <= minutes <= HORIZON:
            return dict(ok=False, error=f"minutes must be between 1 and {HORIZON}")
        return dict(ok=True)

    def finish(self):
        self.now, self.done = HORIZON, True
        return dict(ok=True, shift_over=True)

    # --- dispatch, receipt, replay --------------------------------------------------

    def call(self, tool, args=None):
        args = dict(args or {})
        need = set(self.TOOLS.get(tool, ()))
        if tool not in self.TOOLS or not need <= set(args) <= need | set(self.OPTIONAL.get(tool, ()) * self.partial):
            return dict(ok=False, error="unknown tool or wrong arguments")
        if tool == "get_status":
            return self.get_status()
        if self.done:
            return dict(ok=False, error="the shift is over")
        if len(self.actions) >= MAX_CALLS and tool != "finish":
            return dict(ok=False, error="call budget exhausted; call finish")
        if "service" in args and (not isinstance(args["service"], str) or args["service"] not in self.svc):
            return dict(ok=False, error="unknown service")
        if (tool in MITIGATIONS or tool == "throttle") and self.svc[args["service"]]["tier"] == "external":
            return dict(ok=False, error=f"{args['service']} is hosted outside this estate: nothing here can act on it")
        for key in ("replicas", "minutes", "until_minute", "percent"):
            if key in args and type(args[key]) is not int:
                return dict(ok=False, error=f"{key} must be an integer")
        if "until_minute" in args and not WINDOW - HISTORY <= args["until_minute"] <= self.now:
            return dict(ok=False, error=f"until_minute must be between {WINDOW - HISTORY} and now")
        if "tier" in args and args["tier"] not in ("edge", "app", "data"):
            return dict(ok=False, error="tier must be edge, app or data")
        if tool in MITIGATIONS and any(s == args["service"] and at > self.now for s, _, at in self.ops):
            return dict(ok=False, error="another operation is still in progress on this service")
        result = getattr(self, tool)(**args)
        if result["ok"]:
            self.actions.append([tool, args])
            cfg = self.cfg
            step = args["minutes"] if tool == "wait" else cfg["query_min"] if tool in self.QUERIES else (
                cfg["act_min"] if tool in MITIGATIONS or tool == "throttle" else 0)
            self.now = min(HORIZON, self.now + step)
            if self.now >= HORIZON:
                self.done = True
            result["minute"] = self.now
        return result

    def receipt(self):
        return dict(actions=self.actions, sig=sign(self.actions))


def briefing(level):
    """The level's rules as markdown for the task instruction: time, mitigations, costs."""
    cfg = LEVELS[level]
    took = {tool: m[0] for tool, m in MITIGATIONS.items()}
    fail = {tool: cfg.get("disrupt", {}).get(tool, m[1]) for tool, m in MITIGATIONS.items()}

    def hurt(sev):
        return "no impact" if not sev else "fully down" if sev >= 1 else f"{sev:.0%} of requests fail"

    if cfg["query_min"] or cfg["act_min"]:
        queries = ", ".join(f"`{t}`" for t in sorted(Estate.QUERIES) if t != "get_diff" or cfg.get("partial"))
        clock = (f"- Looking and acting take time. {queries} take {cfg['query_min']} minutes each, and "
                 f"starting a mitigation takes {cfg['act_min']} minute. `get_status` and `get_topology` are "
                 "free, `wait` passes the minutes you ask for, and thinking is free. A result shows the "
                 "estate as it was when you called; its `minute` is the clock after the call.")
    else:
        clock = "- The clock moves only when you call `wait`. Every other tool and thinking are free."
    views = "" if not cfg.get("partial") else f"""
## What you can see

- Alerts fire only above their thresholds. `list_alerts` shows the {TOP_ALERTS} loudest (highest value) and
  the `total` that are firing; pass `tier` (`edge`, `app` or `data`) to list one tier.
- A service's own metrics and logs can look healthy while its callers see it failing. `get_status`
  is what customers actually see.
- `get_metrics` returns {WINDOW} minutes and `get_logs` 10 minutes, ending now or at the `until_minute`
  you pass (not in the future). Looking further back is another call.
- Logs show symptoms and do not name the change behind them. `get_diff` shows what a change did.
"""
    storms = "" if not cfg.get("storms") else f"""
## Retries and overload

- Callers retry a failed call to some services: `callers_retry` in `get_topology` is how many times
  (0: they do not). Only a service's own failures are retried (its fault, the requests a running
  mitigation fails, the load it sheds when over capacity), not failures passed up from what it calls.
- Retries are extra load the next minute. `get_metrics` shows `rps` with retries included, and
  `retry_share`, the share of incoming requests that are retries. `cpu` is load over capacity.
- A service close to capacity can be pushed over it by retries when a fault or a mitigation fails
  part of its requests. It then sheds load, the shed requests are retried, and it stays overloaded
  after the cause is gone, until load is shed or capacity is added. A service with enough headroom
  recovers by itself.
- `throttle(service, percent)` makes the service reject that share of requests (0 to {90}) up front,
  from the next minute. Callers see rejected requests fail, but they are not retried. It does not
  disturb the service and is never a wasted mitigation: its cost is the traffic it rejects. It
  stays on until you set it to 0, and `get_status` lists the throttles that are on. Starting or
  changing one takes {cfg['act_min']} minute.
- `scale` is never charged as a wasted mitigation here, whatever the table above says: its cost is
  the extra replicas, for as long as they stay, and the minute it takes to start.
"""
    files = "" if not cfg.get("files") else f"""
## Generated files

- Some services load a generated file from another service every {EVERY} minutes, on the minutes
  divisible by {EVERY}: `file_from` in `get_topology` names the publisher. This is not a call: the
  publisher is not in `depends_on`.
- A bad file makes the services that loaded it fail until the next good one arrives. A fault can
  therefore come and go, so one healthy reading does not prove that a mitigation worked.
- The cause is fixed at the publisher, and the fix takes effect with its next generation: what was
  already loaded stays until then.
- Not every alert belongs to this estate's services, or to a fault.
"""
    return f"""## How time works

{clock}
- A mitigation takes effect a few minutes after you start it and can disturb the service while it
  runs. Only one operation can run on a service at a time. Check that the mitigation worked.
- `finish` ends the shift early. The rest of the {HORIZON} minutes is still simulated and charged, so
  anything left broken keeps costing money, and a fault that starts or comes back after you leave
  is yours.

## Mitigations

| Tool | Fits | Takes | While it runs |
| --- | --- | --- | --- |
| `rollback` | a bad or leaking build: reverts the latest live deploy | {took["rollback"]} min | {hurt(fail["rollback"])} |
| `revert_config` | a bad config change: reverts the latest live config change | {took["revert_config"]} min | {hurt(fail["revert_config"])} |
| `restart` | a stuck or bloated process; it does not remove the cause | {took["restart"]} min | {hurt(fail["restart"])} (data tier: {hurt(DATA_RESTART[1])}, {DATA_RESTART[0]} min) |
| `scale` | more traffic than the replicas can serve | {took["scale"]} min | {hurt(fail["scale"])} |
| `failover` | a data service whose primary node is gone | {took["failover"]} min | {hurt(fail["failover"])} |

## What is scored

Only the total cost of the shift, computed by replaying your actions in the simulator. Lower is
better.

| Cost | Amount |
| --- | --- |
| Lost revenue | each edge service's revenue per minute × its error rate, every minute of the shift |
| Extra replicas | ${REPLICA_COST} per replica above normal per minute, from when the scale lands to the end of the shift |
| Wasted mitigation | ${cfg["wasted"]:,} for each mitigation applied to a service that did not need it (setting a service back to its normal replica count is free) |
{views}{storms}{files}"""


def sign(actions):
    body = json.dumps(actions, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(RECEIPT_KEY, body, hashlib.sha256).hexdigest()


def replay(seed, level, actions):
    """Re-run an action log and settle. Raises if any logged action is not accepted again."""
    estate = Estate(seed, level)
    for tool, args in actions:
        if not estate.call(tool, args)["ok"]:
            raise ValueError(f"action rejected on replay: {tool} {args}")
    estate.finish()
    return estate


def score(cost, cost_null, cost_ref):
    return max(0.0, min(1.0, (cost_null - cost) / (cost_null - cost_ref)))
