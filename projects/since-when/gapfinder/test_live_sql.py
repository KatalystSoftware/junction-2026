"""python3 -m unittest gapfinder.test_live_sql

The preset endpoint (POST /api/sql/run) takes a preset name and parameters, never SQL. The first
class needs no database. The second runs against the one in DB_HOST as DB_RO_USER and is skipped
without that user: it shows the database itself cutting off a slow statement and denying a write.
"""
import json
import os
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

import mariadb

from gapfinder import api

TOPICS = ("Q1412941", "Q736268", "Q2457646")   # Lapua Movement, Finnish War, Diet of Porvoo
HAVE_RO = api.live_enabled()


def call(server, method, path, body=None):
    """(status, JSON body) of a request to the test server."""
    req = urllib.request.Request(f"http://127.0.0.1:{server.server_port}{path}", method=method,
                                 data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


class Served(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()


class Refused(Served):
    """Everything but a known preset with valid parameters is answered 400 before any connection."""

    def setUp(self):
        # A read-only user that cannot log in: a request that got past validation would be a 502.
        env = mock.patch.dict(os.environ, {"DB_RO_USER": "nobody", "DB_RO_PASSWORD": "nothing"})
        env.start()
        self.addCleanup(env.stop)
        connect = mock.patch.object(api.mariadb, "connect", side_effect=AssertionError("connected"))
        self.connect = connect.start()
        self.addCleanup(connect.stop)

    def refused(self, body):
        status, out = call(self.server, "POST", "/api/sql/run", body)
        self.assertEqual(status, 400, out)
        self.assertIn("error", out)
        self.connect.assert_not_called()

    def test_unknown_preset(self):
        self.refused({"preset": "everything"})
        self.refused({"preset": "SELECT 1"})
        self.refused({"preset": ["asof"]})
        self.refused({})

    def test_sql_text_is_not_a_field(self):
        self.refused({"sql": "SELECT 1"})
        self.refused({"preset": "asof", "sql": "SELECT 1"})
        self.refused({"preset": "asof", "query": "UPDATE finding SET status = 'closed'"})
        self.refused({"preset": "asof", "params": {"sql": "SELECT 1"}})
        self.refused(["SELECT 1"])
        self.refused("SELECT 1")

    def test_a_write_is_not_a_preset(self):
        self.refused({"preset": "UPDATE finding SET status = 'closed'"})
        self.refused({"preset": "history", "params": {"qid": "Q1412941'; DELETE FROM finding; --"}})

    def test_parameter_carrying_sql(self):
        for params in ({"qid": "Q1412941' OR '1'='1"}, {"qid": "Q1 UNION SELECT user()"},
                       {"qid": "Q1412941\n"}, {"qid": 1412941},
                       {"date": "2026-10-22' --"}, {"date": "2026-10-22 00:00:00"},
                       {"date": "NOW()"}, {"date": "2026-13-40"}, {"date": "1999-01-01"},
                       {"date": "2999-01-01"}, {"date": None},
                       {"lang": "de"}, {"lang": "sv' OR 1=1 --"}, {"lang": ["sv"]}):
            with self.subTest(params=params):
                self.refused({"preset": "asof", "params": params})
        self.refused({"preset": "nearest", "params": {"a": "fi", "b": "en' OR 1=1 --"}})
        self.refused({"preset": "nearest", "params": {"a": "fi", "b": "fi"}})

    def test_extra_fields(self):
        self.refused({"preset": "asof", "params": {}, "limit": 100000})
        self.refused({"preset": "asof", "params": {"qid": "Q1412941", "ord": "1"}})
        self.refused({"preset": "history", "params": {"date": "2026-10-22"}})   # asof's, not history's
        self.refused({"preset": "asof", "params": "Q1412941"})

    def test_body_must_be_json(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.server.server_port}/api/sql/run",
                                     method="POST", data=b"SELECT 1")
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=30)
        self.assertEqual(e.exception.code, 400)

    def test_statements_come_from_the_templates(self):
        # Only validated values reach the text, and no template can write.
        for name, preset in api.PRESETS.items():
            _, values = api.live_params({"preset": name})
            for _, sql, binds in preset["statements"](values):
                self.assertRegex(sql.strip(), r"^(WITH|SELECT|SET SESSION system_versioning_asof = \?$)")
                self.assertNotRegex(sql, r"(?i)\b(insert|update|delete|replace|drop|alter|create|grant|call|into)\b")
                self.assertEqual(sql.count("?"), len(binds))


class Off(Served):
    """Without a read-only user the endpoint is off and says so; nothing else changes."""

    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("DB_RO_USER", None)
        os.environ.pop("DB_RO_PASSWORD", None)

    def test_presets_say_disabled(self):
        status, out = call(self.server, "GET", "/api/sql/presets")
        self.assertEqual(status, 200)
        self.assertFalse(out["enabled"])

    def test_run_is_503_even_with_a_valid_preset(self):
        status, out = call(self.server, "POST", "/api/sql/run", {"preset": "asof"})
        self.assertEqual(status, 503, out)


@unittest.skipUnless(HAVE_RO, "DB_RO_USER and DB_RO_PASSWORD are not set")
class OnTheDatabase(Served):
    def setUp(self):
        self.con = api.live_connect()
        self.addCleanup(self.con.close)
        self.cur = self.con.cursor()

    def test_slow_statement_is_cut_off(self):
        t0 = time.perf_counter()
        with self.assertRaises(mariadb.Error) as e:
            self.cur.execute("SELECT SLEEP(20)")
            self.cur.fetchall()
        took = time.perf_counter() - t0
        self.assertEqual(e.exception.errno, 1969, e.exception)   # max_statement_time exceeded
        self.assertLess(took, api.LIVE_SECONDS + 2)
        self.assertGreater(took, api.LIVE_SECONDS - 1)

    def test_slow_statement_is_a_504(self):
        slow = {"title": "", "description": "", "params": [],
                "statements": lambda v: [("slow", "SELECT SLEEP(20)", ())]}
        with mock.patch.dict(api.PRESETS, {"slow": slow}):
            status, out = call(self.server, "POST", "/api/sql/run", {"preset": "slow"})
        self.assertEqual(status, 504, out)

    def test_writes_are_denied_by_the_database(self):
        for sql, errno in (("UPDATE finding SET status = status WHERE id = 0", 1142),
                           ("DELETE FROM finding WHERE id = 0", 1142),
                           ("INSERT INTO topic (wikidata_id) VALUES ('Q0')", 1142),
                           ("CREATE TABLE live_sql_test (id int)", 1142),
                           ("DROP TABLE finding", 1142)):
            with self.subTest(sql=sql):
                with self.assertRaises(mariadb.Error) as e:
                    self.cur.execute(sql)
                self.assertEqual(e.exception.errno, errno, e.exception)

    def test_rows_are_capped(self):
        self.cur.execute("SELECT seq FROM seq_1_to_100000")
        self.assertEqual(len(self.cur.fetchall()), api.LIVE_ROWS)

    def test_every_preset_returns_rows_for_the_demo_topics(self):
        for qid in TOPICS:
            for body in ({"preset": "nearest", "params": {"qid": qid, "date": "2026-10-24", "a": "fi", "b": "en"}},
                         {"preset": "asof", "params": {"qid": qid, "date": "2026-10-22", "lang": "sv"}},
                         {"preset": "history", "params": {"qid": qid, "lang": "en"}}):
                with self.subTest(body=body):
                    status, out = call(self.server, "POST", "/api/sql/run", body)
                    self.assertEqual(status, 200, out)
                    self.assertGreater(len(out["rows"]), 0)
                    self.assertEqual(len(out["rows"][0]), len(out["columns"]))
                    self.assertGreater(out["ms"], 0)
                    self.assertEqual(out["sql"][-1]["rows"], len(out["rows"]))

    def test_asof_is_the_same_statement_on_another_date(self):
        runs = [call(self.server, "POST", "/api/sql/run",
                     {"preset": "asof", "params": {"date": d}})[1] for d in ("2012-01-01", "2026-10-22")]
        self.assertEqual(runs[0]["sql"][1]["query"], runs[1]["sql"][1]["query"])
        self.assertNotIn("SYSTEM_TIME", runs[0]["sql"][1]["query"])
        self.assertNotEqual(runs[0]["rows"][0][1], runs[1]["rows"][0][1])   # another revision


if __name__ == "__main__":
    unittest.main()
