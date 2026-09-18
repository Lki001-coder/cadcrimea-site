#!/usr/bin/env python3
import json, math, os, statistics, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

SYMBOLS=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','SUIUSDT','LINKUSDT','AVAXUSDT','AAVEUSDT','HYPEUSDT']
OUT=sys.argv[1] if len(sys.argv)>1 else '.'
os.makedirs(OUT,exist_ok=True)
NOW_MS=int(time.time()*1000)
UA={'User-Agent':'Mozilla/5.0 crypto-market-feed/3.0','Accept':'application/json'}

def get_json(url,timeout=8):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def f(x):
    try:
        v=float(x); return v if math.isfinite(v) else None
    except Exception:return None

def med(vals):
    vals=[x for x in vals if x is not None and x>0]
    return statistics.median(vals) if vals else None

def pct(a,b):
    if not a or not b:return None
    return (a/b-1)*100

def safe_last(seq): return seq[-1] if seq else None

raw={s:{} for s in SYMBOLS}; errors={}; gate_stats={}; technical={}

# Binance (best-effort; often geo-blocked on cloud runners)
try:
    t=get_json('https://fapi.binance.com/fapi/v1/ticker/24hr'); p=get_json('https://fapi.binance.com/fapi/v1/premiumIndex')
    pm={x.get('symbol'):x for x in p if isinstance(x,dict)}
    for x in t:
        s=x.get('symbol')
        if s not in raw:continue
        q=pm.get(s,{})
        raw[s]['binance']={'price':f(x.get('lastPrice')),'bid':f(x.get('bidPrice')),'ask':f(x.get('askPrice')),'mark':f(q.get('markPrice')),'index':f(q.get('indexPrice')),'funding':f(q.get('lastFundingRate')),'volume_24h_quote':f(x.get('quoteVolume')),'source_ts_ms':int(f(q.get('time')) or NOW_MS)}
except Exception as e: errors['binance']=repr(e)

# Bybit (best-effort)
try:
    j=get_json('https://api.bybit.com/v5/market/tickers?category=linear'); ts=int(f(j.get('time')) or NOW_MS)
    for x in j.get('result',{}).get('list',[]):
        s=x.get('symbol')
        if s not in raw:continue
        raw[s]['bybit']={'price':f(x.get('lastPrice')),'bid':f(x.get('bid1Price')),'ask':f(x.get('ask1Price')),'mark':f(x.get('markPrice')),'index':f(x.get('indexPrice')),'funding':f(x.get('fundingRate')),'open_interest_usd':f(x.get('openInterestValue')),'volume_24h_quote':f(x.get('turnover24h')),'source_ts_ms':ts}
except Exception as e: errors['bybit']=repr(e)

# OKX OI and tickers
okx_oi={}
try:
    oj=get_json('https://www.okx.com/api/v5/public/open-interest?instType=SWAP')
    for x in oj.get('data',[]):
        inst=x.get('instId','')
        if inst.endswith('-USDT-SWAP'):
            s=inst.split('-')[0]+'USDT'
            if s in raw:okx_oi[s]={'oi_base':f(x.get('oiCcy')),'ts':int(f(x.get('ts')) or NOW_MS)}
except Exception as e:errors['okx_oi']=repr(e)
try:
    j=get_json('https://www.okx.com/api/v5/market/tickers?instType=SWAP')
    for x in j.get('data',[]):
        inst=x.get('instId','')
        if not inst.endswith('-USDT-SWAP'):continue
        s=inst.split('-')[0]+'USDT'
        if s not in raw:continue
        price=f(x.get('last')); oi_base=(okx_oi.get(s) or {}).get('oi_base')
        raw[s]['okx']={'price':price,'bid':f(x.get('bidPx')),'ask':f(x.get('askPx')),'open_interest_usd':(oi_base*price if oi_base and price else None),'volume_24h_quote':f(x.get('volCcy24h')),'source_ts_ms':int(f(x.get('ts')) or NOW_MS)}
except Exception as e:errors['okx']=repr(e)

# Gate tickers
try:
    j=get_json('https://api.gateio.ws/api/v4/futures/usdt/tickers')
    for x in j:
        s=x.get('contract','').replace('_','')
        if s not in raw:continue
        raw[s]['gate']={'price':f(x.get('last')),'bid':f(x.get('highest_bid')),'ask':f(x.get('lowest_ask')),'mark':f(x.get('mark_price')),'index':f(x.get('index_price')),'funding':f(x.get('funding_rate')),'volume_24h_quote':f(x.get('volume_24h_quote')),'source_ts_ms':NOW_MS}
except Exception as e:errors['gate']=repr(e)

# Gate stats (OI/liquidations/long-short)
for s in SYMBOLS:
    c=s[:-4]+'_USDT'
    try:
        url='https://api.gateio.ws/api/v4/futures/usdt/contract_stats?'+urllib.parse.urlencode({'contract':c,'interval':'5m','limit':'1'})
        arr=get_json(url)
        if arr:
            x=arr[-1]
            gate_stats[s]={'open_interest_usd':f(x.get('open_interest_usd')),'long_liq_usd':f(x.get('long_liq_usd_new') or x.get('long_liq_usd')),'short_liq_usd':f(x.get('short_liq_usd_new') or x.get('short_liq_usd')),'lsr_account':f(x.get('lsr_account')),'lsr_taker':f(x.get('lsr_taker'))}
    except Exception as e: errors.setdefault('gate_stats',{})[s]=repr(e)
    time.sleep(0.02)
for s,v in gate_stats.items():
    if 'gate' in raw[s] and v.get('open_interest_usd'):raw[s]['gate']['open_interest_usd']=v['open_interest_usd']

# KuCoin fallback
try:
    j=get_json('https://api-futures.kucoin.com/api/v1/contracts/active')
    for x in j.get('data',[]):
        base=(x.get('baseCurrency') or '').upper(); quote=(x.get('quoteCurrency') or '').upper()
        if base=='XBT':base='BTC'
        s=base+quote
        if quote!='USDT' or s not in raw:continue
        price=f(x.get('lastTradePrice')); oi=f(x.get('openInterest')); mult=f(x.get('multiplier'))
        raw[s]['kucoin']={'price':price,'bid':f(x.get('bestBidPrice')),'ask':f(x.get('bestAskPrice')),'mark':f(x.get('markPrice')),'index':f(x.get('indexPrice')),'funding':f(x.get('fundingFeeRate')),'open_interest_usd':(oi*mult*price if oi and mult and price else None),'volume_24h_quote':f(x.get('turnoverOf24h')),'source_ts_ms':NOW_MS}
except Exception as e:errors['kucoin']=repr(e)

# Bitget fallback
try:
    j=get_json('https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES')
    for x in j.get('data',[]):
        s=(x.get('symbol') or '').upper()
        if s not in raw:continue
        price=f(x.get('lastPr')); hold=f(x.get('holdingAmount'))
        raw[s]['bitget']={'price':price,'bid':f(x.get('bidPr')),'ask':f(x.get('askPr')),'mark':f(x.get('markPrice')),'index':f(x.get('indexPrice')),'funding':f(x.get('fundingRate')),'open_interest_usd':(hold*price if hold and price else None),'volume_24h_quote':f(x.get('usdtVolume') or x.get('turnover24h')),'source_ts_ms':int(f(x.get('ts')) or f(j.get('requestTime')) or NOW_MS)}
except Exception as e:errors['bitget']=repr(e)

# Immediate momentum, ATR and volume spike from OKX candles.
# 5m response is newest-first. We use verified closes so anomaly metrics work from run #1.
for s in SYMBOLS:
    inst=s[:-4]+'-USDT-SWAP'
    try:
        c5=get_json('https://www.okx.com/api/v5/market/candles?'+urllib.parse.urlencode({'instId':inst,'bar':'5m','limit':'60'})).get('data',[])
        c1h=get_json('https://www.okx.com/api/v5/market/candles?'+urllib.parse.urlencode({'instId':inst,'bar':'1H','limit':'20'})).get('data',[])
        closes=[f(r[4]) for r in c5 if len(r)>4 and f(r[4])]
        cur=raw[s].get('okx',{}).get('price') or safe_last(closes)
        # c5 newest-first; close at index N approximates N*5m ago.
        def ago(n): return closes[n] if len(closes)>n else None
        v5=[f(r[7]) if len(r)>7 else f(r[6]) if len(r)>6 else f(r[5]) for r in c5]
        latest_vol=v5[0] if v5 else None; baseline=med([x for x in v5[1:21] if x])
        vol_ratio=(latest_vol/baseline if latest_vol and baseline else None)
        trs=[]
        rows=list(reversed(c1h))
        prev_close=None
        for r in rows:
            if len(r)<5:continue
            hi,lo,cl=f(r[2]),f(r[3]),f(r[4])
            if not hi or not lo or not cl:continue
            tr=hi-lo if prev_close is None else max(hi-lo,abs(hi-prev_close),abs(lo-prev_close))
            trs.append(tr); prev_close=cl
        atr=statistics.mean(trs[-14:]) if trs else None
        technical[s]={'change_5m_pct':pct(cur,ago(1)),'change_15m_pct':pct(cur,ago(3)),'change_1h_pct':pct(cur,ago(12)),'change_4h_pct':pct(cur,ago(48)),'volume_spike_5m':vol_ratio,'atr_1h':atr,'atr_1h_pct':(atr/cur*100 if atr and cur else None)}
    except Exception as e:errors.setdefault('okx_candles',{})[s]=repr(e)
    time.sleep(0.02)

# Retain history for OI deltas and auditing.
history_path=os.path.join(OUT,'history.json'); history=[]
if os.path.exists(history_path):
    try:
        with open(history_path,'r',encoding='utf-8') as fh:history=json.load(fh)
        if not isinstance(history,list):history=[]
    except Exception:history=[]

def prior(symbol,minutes,field):
    target=NOW_MS-minutes*60*1000
    c=[h for h in history if h.get('ts_ms',0)<=target and symbol in h.get('market',{})]
    if not c:return None
    h=max(c,key=lambda z:z.get('ts_ms',0)); return h['market'][symbol].get(field)

market={}
for s,sources in raw.items():
    p0=med([v.get('price') for v in sources.values()])
    if not p0:
        market[s]={'data_quality':'LOW','source_count':0,'sources':sources};continue
    good={k:v for k,v in sources.items() if v.get('price') and abs(v['price']/p0-1)<=0.01}
    prices=[v['price'] for v in good.values()]; mp=med(prices)
    disp=(max(prices)-min(prices))/mp*100 if len(prices)>=2 else None
    ages=[max(0,(NOW_MS-int(v.get('source_ts_ms',NOW_MS)))/1000) for v in good.values()]; max_age=max(ages) if ages else 9999
    quality='HIGH' if len(good)>=3 and (disp or 0)<=0.25 and max_age<=90 else ('MEDIUM' if len(good)>=2 and (disp or 0)<=0.75 and max_age<=120 else 'LOW')
    bid=med([v.get('bid') for v in good.values()]); ask=med([v.get('ask') for v in good.values()]); spread=((ask-bid)/mp*100) if ask and bid and ask>=bid else None
    mark=med([v.get('mark') for v in good.values()]); index=med([v.get('index') for v in good.values()]); funding=med([v.get('funding') for v in good.values()]); oi=med([v.get('open_interest_usd') for v in good.values()]); volume=sum(v.get('volume_24h_quote') or 0 for v in good.values()) or None
    oi_ch=pct(oi,prior(s,60,'open_interest_usd')); gs=gate_stats.get(s,{}); tech=technical.get(s,{})
    liq=(gs.get('long_liq_usd') or 0)+(gs.get('short_liq_usd') or 0); vr=tech.get('volume_spike_5m')
    score=0.0
    score+=min(25,abs(tech.get('change_5m_pct') or 0)*12)+min(25,abs(tech.get('change_1h_pct') or 0)*7)+min(15,abs(tech.get('change_4h_pct') or 0)*2.5)+min(15,abs(oi_ch or 0)*3)
    if funding is not None:score+=min(8,abs(funding)*10000*1.2)
    if vr and vr>1:score+=min(10,(vr-1)*4)
    if liq:score+=min(8,math.log10(max(1,liq))*1.1)
    if disp is not None and disp>0.25:score+=min(8,(disp-0.25)*16)
    market[s]={'median_price':mp,'mark_price':mark,'index_price':index,'bid':bid,'ask':ask,'spread_pct':spread,'funding_rate':funding,'open_interest_usd':oi,'oi_change_1h_pct':oi_ch,'long_liq_usd_5m':gs.get('long_liq_usd'),'short_liq_usd_5m':gs.get('short_liq_usd'),'long_short_account_ratio':gs.get('lsr_account'),'long_short_taker_ratio':gs.get('lsr_taker'),'volume_24h_quote_sum':volume,'volume_spike_5m':tech.get('volume_spike_5m'),'atr_1h':tech.get('atr_1h'),'atr_1h_pct':tech.get('atr_1h_pct'),'change_5m_pct':tech.get('change_5m_pct'),'change_15m_pct':tech.get('change_15m_pct'),'change_1h_pct':tech.get('change_1h_pct'),'change_4h_pct':tech.get('change_4h_pct'),'anomaly_score':round(min(100,score),1),'source_count':len(good),'price_dispersion_pct':disp,'data_age_seconds':max_age,'data_quality':quality,'sources':good}

qc={q:sum(1 for v in market.values() if v.get('data_quality')==q) for q in ['HIGH','MEDIUM','LOW']}
out={'generated_at':datetime.now(timezone.utc).isoformat(),'ts_ms':NOW_MS,'refresh_target_seconds':300,'quality_counts':qc,'source_errors':errors,'market':market}
with open(os.path.join(OUT,'latest.json'),'w',encoding='utf-8') as fh:json.dump(out,fh,ensure_ascii=False,separators=(',',':'))
an=[{'symbol':s,'score':v.get('anomaly_score'),'price':v.get('median_price'),'change_5m_pct':v.get('change_5m_pct'),'change_15m_pct':v.get('change_15m_pct'),'change_1h_pct':v.get('change_1h_pct'),'change_4h_pct':v.get('change_4h_pct'),'volume_spike_5m':v.get('volume_spike_5m'),'oi_change_1h_pct':v.get('oi_change_1h_pct'),'funding_rate':v.get('funding_rate'),'long_liq_usd_5m':v.get('long_liq_usd_5m'),'short_liq_usd_5m':v.get('short_liq_usd_5m'),'data_quality':v.get('data_quality')} for s,v in market.items()]
an.sort(key=lambda x:x.get('score') or 0,reverse=True)
with open(os.path.join(OUT,'anomalies.json'),'w',encoding='utf-8') as fh:json.dump({'ts_ms':NOW_MS,'items':an},fh,ensure_ascii=False,separators=(',',':'))
compact={'ts_ms':NOW_MS,'market':{s:{'median_price':v.get('median_price'),'open_interest_usd':v.get('open_interest_usd')} for s,v in market.items()}}
history.append(compact); history=[h for h in history if h.get('ts_ms',0)>=NOW_MS-48*3600*1000][-650:]
with open(history_path,'w',encoding='utf-8') as fh:json.dump(history,fh,separators=(',',':'))
health={'generated_at':out['generated_at'],'ts_ms':NOW_MS,'source_errors':errors,'symbols':len(market),'high_quality':qc['HIGH'],'medium_quality':qc['MEDIUM'],'low_quality':qc['LOW']}
with open(os.path.join(OUT,'health.json'),'w',encoding='utf-8') as fh:json.dump(health,fh,separators=(',',':'))
print(json.dumps(health,indent=2))
