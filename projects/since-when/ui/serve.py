"""Serves the gap finder UI and its API.

    python3 ui/serve.py                     # UI with fixture data on http://localhost:8078
    python3 ui/serve.py --port 9000
    GAPFINDER_API=http://localhost:8077 python3 ui/serve.py   # proxy /api/* to the real server

Without GAPFINDER_API, /api/* answers from ui/fixtures/ in the shape of docs/gap-finder/api.md.
Finding status changes are kept in memory until the server stops.
"""
import argparse, json, os, re, urllib.error, urllib.request
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, 'fixtures')
API = os.environ.get('GAPFINDER_API', '').rstrip('/')
STATUS = {}   # finding id -> (status, date, outcome, rev_url) changed through POST


def load(*parts):
    path = os.path.join(FIX, *parts)
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return json.load(f)


def apply_status(finding):
    if finding['id'] in STATUS:
        finding['status'], changed, finding['outcome'], finding['rev_url'] = STATUS[finding['id']]
        if finding['status'] == 'closed':
            finding['closed_at'] = changed
    return finding


def all_findings():
    for name in os.listdir(os.path.join(FIX, 'topics')):
        if name.endswith('.json'):
            topic = load('topics', name)
            for f in topic['findings']:
                yield topic, f


def sql_update(fid, status):
    return {'label': 'Update finding status', 'ms': 0.3, 'rows': 1, 'query':
            f"-- The old row stays in the finding table's history\nUPDATE finding SET status = '{status}'\nWHERE id = {fid};"}


def route(method, path, query, body):
    q = {k: v[0] for k, v in parse_qs(query).items()}
    if method == 'GET' and path == '/api/queue':
        data = load('queue.json')
        items = [i for i in data['items'] if q.get('lang', 'all') in ('all', i['lang'])]
        offset, limit = int(q.get('offset', 0)), int(q.get('limit', 50))
        return 200, {**data, 'total': len(items), 'items': items[offset:offset + limit]}
    if method == 'GET' and path == '/api/search':
        words = q.get('q', '').lower().split()
        data = load('queue.json')
        items = [i for i in data['items'] if words and all(w in i['topic'].lower() for w in words)]
        return 200, {'fixture': True, 'items': items, 'sql': [{'label': 'Nearest passages to the query', 'ms': 4.2, 'rows': len(items), 'query':
                     "-- Vector index on the current passages only\nSELECT wikidata_id, lang, section,\n       VEC_DISTANCE_COSINE(embedding, VEC_FromText(@query_vector)) AS d\nFROM chunk_now\nORDER BY d\nLIMIT 20;"}]}
    m = re.fullmatch(r'/api/topics/(Q\d+)', path)
    if method == 'GET' and m:
        data = load('topics', m[1] + '.json')
        if data:
            data['findings'] = [apply_status(f) for f in data['findings']]
        return (200, data) if data else (404, {'error': 'unknown topic'})
    m = re.fullmatch(r'/api/topics/(Q\d+)/compare', path)
    if method == 'GET' and m:
        data = load('topics', m[1], f"compare-{q.get('a', 'fi')}-{q.get('b', 'en')}.json")
        if not data:
            return 404, {'error': 'no passages for this pair in the fixtures'}
        data['as_of'] = q.get('as_of') or None
        if data['as_of']:
            data['fixture_note'] = 'Fixture passages are as of today; the real API returns each edition as it stood on this date.'
            data['sql'][0]['query'] = re.sub(r"TIMESTAMP '[^']*'", f"TIMESTAMP '{data['as_of']} 00:00:00'", data['sql'][0]['query'])
        return 200, data
    m = re.fullmatch(r'/api/topics/(Q\d+)/timeline', path)
    if method == 'GET' and m:
        data = load('topics', m[1], f"timeline-{q.get('lang')}-{q.get('rich_lang')}.json")
        if not data:
            return 404, {'error': 'no timeline for this pair in the fixtures'}
        for fid, (status, changed, outcome, _) in STATUS.items():
            if any(e['finding_id'] == fid for e in data['events']):
                data['events'].append({'date': changed, 'finding_id': fid, 'kind': status, 'summary': f'Outcome recorded in the gap finder: {outcome or status}.'})
        return 200, data
    m = re.fullmatch(r'/api/findings/(\d+)/status', path)
    if method == 'POST' and m:
        fid, status = int(m[1]), body.get('status')
        if status not in ('open', 'reviewed', 'closed'):
            return 400, {'error': 'status must be open, reviewed or closed'}
        for _, f in all_findings():
            if f['id'] == fid:
                if status == 'open':
                    STATUS.pop(fid, None)   # reopening undoes the outcome instead of adding a new event
                else:
                    STATUS[fid] = (status, date.today().isoformat(), body.get('outcome'), body.get('rev_url'))
                return 200, {**apply_status(f), 'sql': [sql_update(fid, status)]}
        return 404, {'error': 'unknown finding'}
    return 404, {'error': 'not found'}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def api(self, method):
        url = urlparse(self.path)
        length = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(length) if length else b''
        if API:
            req = urllib.request.Request(API + self.path, data=raw or None, method=method,
                                         headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    code, out = r.status, r.read()
            except urllib.error.HTTPError as e:
                code, out = e.code, e.read()
            except OSError as e:
                code, out = 502, json.dumps({'error': f'backend unreachable: {e}'}).encode()
        else:
            code, data = route(method, url.path, url.query, json.loads(raw or b'{}'))
            out = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(out)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):
        if self.path.startswith('/api/'):
            return self.api('GET')
        if self.path.startswith('/fixtures/') or self.path.endswith('.py'):
            self.send_error(404)
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api/'):
            return self.api('POST')
        self.send_error(405)

    def end_headers(self):
        if not self.path.startswith('/api/'):
            self.send_header('Cache-Control', 'no-cache')
        super().end_headers()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=int(os.environ.get('PORT', 8078)))
    port = ap.parse_args().port
    print(f"gap finder UI on http://localhost:{port} ({'proxy to ' + API if API else 'fixture data'})", flush=True)
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()
