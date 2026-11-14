"""Embed passages with bge-m3, lowest priority first, until none is left.

Several workers can run at once, on different machines: each takes a 15-minute lease on a batch
(SELECT … FOR UPDATE SKIP LOCKED, then commit), so no passage is embedded twice and no row stays
locked while the model runs. A crashed worker's lease simply runs out.

    python -m gapfinder embed [--threads N]
"""

import os
import struct
import time

import mariadb

from .db import connect

MODEL = "BAAI/bge-m3"
CLAIM, BATCH = 64, 16


def vec_bytes(v):
    """A vector as MariaDB's binary VECTOR value: little-endian float32."""
    return struct.pack(f"<{len(v)}f", *v)


class Embedder:
    def __init__(self, threads=None):
        import torch
        from transformers import AutoModel, AutoTokenizer

        torch.set_num_threads(threads or os.cpu_count())
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(MODEL)
        self.model = AutoModel.from_pretrained(MODEL).eval()

    def __call__(self, texts):
        """Normalised dense vectors (CLS token), as bge-m3 defines them."""
        out = []
        with self.torch.inference_mode():
            for i in range(0, len(texts), BATCH):
                b = self.tok(texts[i : i + BATCH], padding=True, truncation=True, max_length=1024, return_tensors="pt")
                v = self.model(**b).last_hidden_state[:, 0]
                out += self.torch.nn.functional.normalize(v, dim=-1).tolist()
        return out


def run(threads=None, stop_priority=None):
    embed = Embedder(threads)
    con = None
    done, words, started = 0, 0, time.monotonic()
    while True:
        try:
            if con is None:
                con = connect()
                cur = con.cursor()
            cur.execute(
                "SELECT sha, text, words FROM passage WHERE embedding_done = 0 "
                "AND (claimed_until IS NULL OR claimed_until < UTC_TIMESTAMP()) "
                + ("AND priority < ? " if stop_priority is not None else "")
                + "ORDER BY embedding_done, priority LIMIT ? FOR UPDATE SKIP LOCKED",
                ((stop_priority,) if stop_priority is not None else ()) + (CLAIM,),
            )
            rows = cur.fetchall()
            if rows:
                cur.executemany(
                    "UPDATE passage SET claimed_until = UTC_TIMESTAMP() + INTERVAL 15 MINUTE WHERE sha = ?",
                    [(r[0],) for r in rows],
                )
            con.commit()
            if not rows:
                print(f"nothing left: {done} passages, {words} words; waiting for more", flush=True)
                time.sleep(60)  # the loader may still be adding passages
                continue
            rows.sort(key=lambda r: r[2])  # similar lengths in a batch: less padding
            vecs = embed([r[1] for r in rows])
            cur.executemany(
                "UPDATE passage SET embedding = ? WHERE sha = ?", [(vec_bytes(v), r[0]) for v, r in zip(vecs, rows)]
            )
            con.commit()
        except mariadb.Error as e:
            # A worker on another machine reaches the database through a tunnel that drops now
            # and then: reconnect and keep the loaded model. The lost batch's lease runs out.
            print(f"database error, reconnecting in 10 s: {e}", flush=True)
            con = None
            time.sleep(10)
            continue
        done += len(rows)
        words += sum(r[2] for r in rows)
        rate = words / (time.monotonic() - started)
        print(f"{done} passages, {words} words, {rate:.0f} words/s", flush=True)
