#!/usr/bin/env python3
import json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
os.makedirs(OUT, exist_ok=True)
BASE = 'https://api.toobit.com'
SYMBOLS = ['BTC','ETH','SOL','XRP','DOGE','SUI','LINK','AVAX','BNB','AAVE']
UA = {'User-Agent':'Mozilla/5.0 toobit-feed/1.0','Accept':'application/json'}

def get_json(path, params=None, timeout=10):
    url = BASE + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def num(x):
    try: return float(x)
    except Exception: return None

def first(x):
    if isinstance(x, list): return x[0] if x else {}
    return x if isinstance(x, dict) else {}

started_ms = int(time.time()*1000)
errors = {}
try:
    server = get_json('/api/v1/time')
    server_ms = int(server.get('serverTime', started_ms))
except Exception as e:
    errors['server_time'] = repr(e)
    server_ms = started_ms

market = {}
for base in SYMBOLS:
    sym = f'{base}-SWAP-USDT'
    try:
        ticker = first(get_json('/quote/v1/contract/ticker/24hr', {'symbol':sym}))
        mark = get_json('/quote/v1/markPrice', {'symbol':sym})
        funding = first(get_json('/api/v1/futures/fundingRate', {'symbol':sym}))
        oi = get_json('/quote/v1/openInterest', {'symbol':sym})
        lsr = get_json('/quote/v1/globalLongShortAccountRatio', {'symbol':sym,'period':'15m','limit':12})
        k15 = get_json('/quote/v1/klines', {'symbol':sym,'interval':'15m','limit':24})
        k1h = get_json('/quote/v1/klines', {'symbol':sym,'interval':'1h','limit':24})
        oi_item = first(oi.get('openInterestList', []) if isinstance(oi, dict) else oi)
        last_lsr = lsr[-1] if isinstance(lsr, list) and lsr else {}
        last = num(ticker.get('c'))
        mark_price = num(mark.get('price')) if isinstance(mark, dict) else None
        market[base+'USDT'] = {
            'symbol': sym,
            'last_price': last,
            'mark_price': mark_price,
            'bid': num(ticker.get('b')),
            'ask': num(ticker.get('a')),
            'high_24h': num(ticker.get('h')),
            'low_24h': num(ticker.get('l')),
            'open_24h': num(ticker.get('o')),
            'change_24h_pct': (num(ticker.get('pcp'))*100 if num(ticker.get('pcp')) is not None else None),
            'volume_24h_quote': num(ticker.get('qv')),
            'funding_rate': num(funding.get('rate')),
            'next_funding_time': int(funding.get('nextFundingTime')) if funding.get('nextFundingTime') else None,
            'open_interest_base': num(oi_item.get('size')),
            'open_interest_usd_est': (num(oi_item.get('size'))*mark_price if num(oi_item.get('size')) is not None and mark_price is not None else None),
            'long_short_ratio': num(last_lsr.get('longShortRatio')),
            'long_account': num(last_lsr.get('longAccount')),
            'short_account': num(last_lsr.get('shortAccount')),
            'long_short_series_15m': lsr[-12:] if isinstance(lsr, list) else [],
            'klines_15m': k15[-24:] if isinstance(k15, list) else [],
            'klines_1h': k1h[-24:] if isinstance(k1h, list) else [],
            'ticker_ts_ms': int(ticker.get('t')) if ticker.get('t') else server_ms,
            'mark_ts_ms': int(mark.get('time')) if isinstance(mark,dict) and mark.get('time') else server_ms,
        }
    except Exception as e:
        errors[sym] = repr(e)

out = {
    'generated_at': datetime.now(timezone.utc).isoformat(),
    'generated_ms': int(time.time()*1000),
    'toobit_server_ms': server_ms,
    'refresh_target_seconds': 300,
    'primary_execution_venue': 'TOOBIT',
    'errors': errors,
    'market': market,
}
with open(os.path.join(OUT,'toobit.json'),'w',encoding='utf-8') as fh:
    json.dump(out, fh, ensure_ascii=False, separators=(',',':'))
print(json.dumps({'symbols':len(market),'errors':errors,'server_ms':server_ms}, ensure_ascii=False))
