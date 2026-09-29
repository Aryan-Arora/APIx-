"""Read-only deployment smoke checks; credentials are read from environment."""
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

base = os.environ['API_BASE'].rstrip('/')
key = os.environ['API_KEY']


def get(path, authenticated=True):
    request = Request(base + path, headers={'X-API-Key': key} if authenticated else {})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


health = get('/health', False)
assert health['data_mode'] == 'database' and health['db'] == 'connected', 'Database health failed'
try:
    get('/index', False)
except HTTPError as error:
    assert error.code == 401, 'Expected unauthenticated 401'
else:
    raise AssertionError('Unauthenticated index was accepted')
for path in ['/routes', '/index', '/heatmap', '/carriers', '/scrape-runs']:
    assert isinstance(get(path), list), 'Unexpected list response: ' + path
live = get('/index?include_synthetic=false')
assert all(row['includes_synthetic'] is False for row in live), 'Synthetic index leaked'
assert isinstance(get('/quotes?limit=1')['items'], list)
assert 'summary' in get('/backtest')
assert 'steps' in get('/methodology', False)
print('PASS: database health, auth, API shapes and live-only index provenance')
print(f'Live-only index points: {len(live)} (zero does not satisfy live-data readiness)')
