"""MariaDB connection settings, from the environment."""

import os

import mariadb

DB = dict(
    host=os.environ.get("DB_HOST", "127.0.0.1"),
    port=int(os.environ.get("DB_PORT", 3306)),
    user=os.environ.get("DB_USER", "gapfinder"),
    password=os.environ.get("DB_PASSWORD", "gapfinder"),
    database=os.environ.get("DB_NAME", "gapfinder"),
)

LANGS = ("fi", "sv", "en")


def connect(autocommit=False):
    con = mariadb.connect(**DB, autocommit=autocommit)
    cur = con.cursor()
    cur.execute("SET time_zone = '+00:00'")
    cur.close()
    return con
