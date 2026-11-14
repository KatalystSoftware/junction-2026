"""Is the low recall of spikes/mariadb-wikipedia/svt_vector_recall.py about versioning, or about
an index that does not fit mhnsw_max_cache_size?

The same 48,000 random 64-dim vectors as that spike (3,000 ids, 16 versions each), in a plain
table without versioning, searched with the index and compared with exact search (IGNORE INDEX):
all rows, and one version in 16 picked by an ordinary WHERE, which is what AS OF does to a
versioned table. Run it on a throwaway server, see ../demo/measurements.md:

    python cache_check.py      # DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME; takes 1-4 min
"""

import os
import random

import mariadb

D, N, VERSIONS = 64, 3000, 16
random.seed(1)


def vec():
    return "[" + ",".join(f"{random.gauss(0, 1):.4f}" for _ in range(D)) + "]"


def recall(cur, where=""):
    hits, rows = [], []
    for _ in range(30):
        q = vec()
        cur.execute(
            f"SELECT id, ver FROM cache_check {where} ORDER BY VEC_DISTANCE_COSINE(v, VEC_FromText(?)) LIMIT 10", (q,)
        )
        approx = set(cur.fetchall())
        cur.execute(
            f"SELECT id, ver FROM cache_check IGNORE INDEX (v) {where} ORDER BY VEC_DISTANCE_COSINE(v, VEC_FromText(?)) LIMIT 10",
            (q,),
        )
        hits.append(len(approx & set(cur.fetchall())) / 10)
        rows.append(len(approx))
    return f"{sum(hits) / len(hits):.2f}  ({sum(rows) / len(rows):.1f} of 10 rows returned)"


def main():
    con = mariadb.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        autocommit=True,
    )
    cur = con.cursor()
    cur.execute("SELECT VERSION(), @@mhnsw_max_cache_size DIV 1048576")
    print("MariaDB {}, mhnsw_max_cache_size {} MB".format(*cur.fetchone()))
    cur.execute("DROP TABLE IF EXISTS cache_check")
    cur.execute(
        f"CREATE TABLE cache_check (id INT, ver INT, v VECTOR({D}) NOT NULL, PRIMARY KEY (id, ver), "
        "VECTOR INDEX (v) M=16 DISTANCE=cosine)"
    )
    for i in range(N):
        cur.executemany(
            "INSERT INTO cache_check VALUES (?, ?, VEC_FromText(?))", [(i, k, vec()) for k in range(VERSIONS)]
        )
    for ef in (80, 1000):
        cur.execute(f"SET mhnsw_ef_search = {ef}")
        print(f"ef_search {ef:4d}, plain table, all {N * VERSIONS} rows        ", recall(cur))
        print(f"ef_search {ef:4d}, plain table, WHERE ver = 2 ({N} rows)", recall(cur, "WHERE ver = 2"))
    cur.execute("DROP TABLE cache_check")


if __name__ == "__main__":
    main()
