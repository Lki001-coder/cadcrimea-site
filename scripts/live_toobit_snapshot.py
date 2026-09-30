#!/usr/bin/env python3
import json, os, sys, time, urllib.request
from datetime import datetime, timezone

URL = os.getenv('LIVE_TOOBIT_FEED_URL', 'https://cadcrimea.ru/crypto-feed/snapshot')
OUT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/toobit.json'
UA = {'User-Agent': 'github-toobit-snapshot/1.0', 'Accept': 'application/json'}

req = urllib.request.Request(URL, headers=UA)
with urllib.request.urlopen(req, timeout=10) as r:
    src = json.loads(r.read().decode('utf-8'))

fast_age = src.get('fast_age_ms')
slow_age = src.get('slow_age_ms')
market = src.get('market') or {}
if fast_age is None or fast_age > 10000:
    raise SystemExit(f'live feed fast data stale: {fast_age}ms')
if slow_age is None or slow_age > 60000:
    raise SystemExit(f'live feed slow data stale: {slow_age}ms')
if len(market) < 8:
    raise SystemExit(f'live feed has too few symbols: {len(market)}')

required = ('last_price','mark_price','bid','ask','high_24h','low_24h','funding_rate','open_interest_base','long_short_ratio','klines_15m','klines_1h')
complete = 0
for symbol, item in market.items():
    if all(item.get(k) not in (None, [], {}) for k in required):
        complete += 1
    oi = item.get('open_interest_base')
    mark = item.get('mark_price')
    if oi is not None and mark is not None:
        item['open_interest_usd_est'] = oi * mark
if complete < 8:
    raise SystemExit(f'live feed incomplete symbols: {complete}')

now_ms = int(time.time() * 1000)
out = {
    'generated_at': datetime.now(timezone.utc).isoformat(),
    'generated_ms': now_ms,
    'toobit_server_ms': src.get('toobit_server_ms'),
    'refresh_target_seconds': 300,
    'primary_execution_venue': 'TOOBIT',
    'source': 'always-on-server-live-feed',
    'source_fast_age_ms': fast_age,
    'source_slow_age_ms': slow_age,
    'errors': src.get('errors') or {},
    'market': market,
}
os.makedirs(os.path.dirname(OUT) or '.', exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as fh:
    json.dump(out, fh, ensure_ascii=False, separators=(',', ':'))
print(json.dumps({'ok': True, 'symbols': len(market), 'complete': complete, 'fast_age_ms': fast_age, 'slow_age_ms': slow_age}))
