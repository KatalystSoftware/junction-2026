"""Gap finder command line. Run from the repository root:

    python -m gapfinder schema                 # create the tables
    python -m gapfinder load [--only Q…]       # topics, history (fi, sv, en), page views
    python -m gapfinder embed [--threads N]    # embed passages, lowest priority first
    python -m gapfinder align [--only Q…]      # coverage and coverage findings
    python -m gapfinder pairs > pairs.jsonl    # far matched pairs for the classifier
    python -m gapfinder findings load differences.jsonl
    python -m gapfinder findings lexicon pairs.jsonl > lexicon.jsonl   # word-list rows
    python -m gapfinder measure                # index recall and query times, saved to a file
    python -m gapfinder measure --versioned-index mine_a3   # a vector index on a versioned table
    python -m gapfinder serve [--port 8077]    # the HTTP API (docs/gap-finder/api.md)
"""
import argparse
import pathlib


def main():
    ap = argparse.ArgumentParser(prog="gapfinder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("schema")
    p = sub.add_parser("load")
    p.add_argument("--only", nargs="*")
    p.add_argument("--part", choices=["topics", "fi", "sv", "en", "views"], nargs="*")
    p = sub.add_parser("embed")
    p.add_argument("--threads", type=int)
    p.add_argument("--below", type=int, help="only passages with priority below this")
    p = sub.add_parser("align")
    p.add_argument("--only", nargs="*")
    p.add_argument("--current", action="store_true", help="current text only, no history")
    p = sub.add_parser("pairs")
    p.add_argument("--only", nargs="*")
    p.add_argument("--history", action="store_true", help="also every 1 January with vectors")
    p = sub.add_parser("findings")
    p.add_argument("action", choices=["load", "lexicon"])
    p.add_argument("path")
    p = sub.add_parser("measure")
    p.add_argument("--queries", type=int, default=100)
    p.add_argument("--runs", type=int, default=3, help="times each alignment query is run")
    p.add_argument("--versioned-index", metavar="DB",
                   help="instead: the vector index on a versioned table experiment, in this private database")
    p.add_argument("--one-in", type=int, default=2, help="--versioned-index: copy one topic in this many")
    p.add_argument("--keep", action="store_true", help="--versioned-index: leave the experiment tables")
    p.add_argument("--out", default=None, help="folder for the JSON and Markdown results")
    p.add_argument("--note", help="a line for the results file, such as the server's memory limit")
    p.add_argument("--provisional", action="store_true", help="mark the times as taken on a busy machine")
    p = sub.add_parser("serve")
    p.add_argument("--port", type=int, default=8077)
    args = ap.parse_args()

    if args.cmd == "schema":
        from .db import connect
        con = connect()
        cur = con.cursor()
        sql = pathlib.Path(__file__).with_name("schema.sql").read_text()
        for stmt in "\n".join(l for l in sql.splitlines() if not l.startswith("--")).split(";"):
            if stmt.strip():
                cur.execute(stmt)
        con.commit()
    elif args.cmd == "load":
        from . import load
        only = set(args.only) if args.only else None
        parts = args.part or ["topics", "fi", "sv", "en", "views"]
        if "topics" in parts:
            load.topics()
        if "fi" in parts:
            load.load_fi(only=only)
        for lang in ("sv", "en"):
            if lang in parts:
                load.load_api_history(lang, only=only)
        if "views" in parts:
            load.pageviews()
    elif args.cmd == "embed":
        from . import embed
        embed.run(args.threads, args.below)
    elif args.cmd == "align":
        from . import align
        align.run(set(args.only) if args.only else None, history=not args.current)
    elif args.cmd == "pairs":
        from . import align
        align.pairs(set(args.only) if args.only else None, history=args.history)
    elif args.cmd == "findings":
        from . import align
        if args.action == "lexicon":
            align.lexicon_rows(args.path)
        else:
            align.load_differences(args.path)
    elif args.cmd == "measure":
        from . import measure
        save = dict(out=args.out or measure.OUT, note=args.note, provisional=args.provisional)
        if args.versioned_index:
            measure.versioned_index(args.versioned_index, args.queries, args.one_in, args.keep, **save)
        else:
            measure.run(args.queries, args.runs, **save)
    elif args.cmd == "serve":
        from . import api
        api.serve(args.port)


if __name__ == "__main__":
    main()
