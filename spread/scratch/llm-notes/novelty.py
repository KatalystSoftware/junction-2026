import sys, json, collections, re, random, statistics
from spreadlab import notes as N
from spreadlab.server import data_dir
D = str(data_dir() / "llm-notes") + "/"  # the extracts: large, in the data folder, not committed
notes = [json.loads(l) for l in open(D + "notes.jsonl")]
by_seed = collections.defaultdict(list)
for n in notes: by_seed[n["seed"]].append(n["note"]["text"])
seeds = sorted(by_seed); random.seed(1); random.shuffle(seeds)
def sentences(t):
    t = re.sub(r"\d", "0", t.lower())
    return [s.strip() for s in re.split(r"[.!?;/|]+\s+|\n", t) if s.strip()]
def words(t): return set(re.findall(r"[a-zåäö]+", t.lower()))
test = seeds[:60]
for k in (25, 50, 100, 200, 400):
    train = seeds[60:60 + k]
    S, W, T = set(), set(), set()
    for s in train:
        for t in by_seed[s]:
            S.update(sentences(t)); W.update(words(t)); T.add(t)
    fs, fw, ft, fn = [], [], [], []
    for s in test:
        ts = by_seed[s]
        sent = [x for t in ts for x in sentences(t)]
        fs.append(sum(x not in S for x in sent) / len(sent))
        fn.append(sum(any(x not in S for x in sentences(t)) for t in ts) / len(ts))
        fw.append(sum(bool(words(t) - W) for t in ts) / len(ts))
        ft.append(sum(t not in T for t in ts) / len(ts))
    print(f"known weeks {k:3d}: unseen exact note {statistics.mean(ft):.1%}, note with an unseen sentence (digits masked) {statistics.mean(fn):.1%}, unseen sentence {statistics.mean(fs):.1%}, note with an unseen word {statistics.mean(fw):.1%}; distinct sentences {len(S)}, words {len(W)}")
# unseen words: are they typos of known words?
train = seeds[60:]
W = collections.Counter(w for s in train for t in by_seed[s] for w in words(t))
new = collections.Counter(w for s in test for t in by_seed[s] for w in words(t) if w not in W)
print("unseen word types in 60 test weeks:", len(new), "per week", sum(new.values()) / 60)
common = [w for w, c in W.items() if c >= 50 and len(w) >= 5]
typo = sum(1 for w in new if any(N.near(w, k) for k in common))
print("of them one edit from a common known word:", typo, "sample:", random.sample(sorted(new), 40))
