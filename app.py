import os, time, logging, requests
import pandas as pd, numpy as np, yfinance as yf
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# إعدادات عامة
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("egx-api")

CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))
price_cache = {}

# رموز الأسهم
TICKER_MAP = {"CIB": "COMI.CA", "FWRY": "FWRY.CA", "PHDC": "PHDC.CA", "ETEL": "ETEL.CA"}
BASE_PRICES = {"CIB": 60.0, "FWRY": 10.0, "PHDC": 2.0, "ETEL": 20.0}

def normalize(t): return t.strip().upper()
def is_reasonable(t, p): 
    base = BASE_PRICES.get(normalize(t))
    return True if not base else 0.5*base <= p <= 1.5*base

# ---------------- مصادر البيانات ----------------
def fetch_yfinance(t):
    try:
        sym = TICKER_MAP.get(normalize(t), f"{t}.CA")
        stock = yf.Ticker(sym)
        info = getattr(stock, "fast_info", None)
        if info and info.last_price and is_reasonable(t, info.last_price):
            return info.last_price, "yfinance"
        hist = stock.history(period="5d")
        if not hist.empty:
            p = float(hist["Close"].iloc[-1])
            if is_reasonable(t, p): return p, "yfinance(hist)"
    except Exception as e: logger.warning(f"yfinance {t} error {e}")
    return None, "yfinance failed"

def fetch_egxpy(t):
    try:
        import egxpy.download as egx_dl
        df = egx_dl.get_OHLCV_data(normalize(t), "2025-12-01", "2026-01-06")
        if df is not None and not df.empty:
            p = float(df["close"].iloc[-1])
            if is_reasonable(t, p): return p, "egxpy"
    except Exception as e: logger.warning(f"egxpy {t} error {e}")
    return None, "egxpy failed"

def fetch_mubasher(t):
    try:
        url = f"https://english.mubasher.info/markets/EGX/stocks/{normalize(t)}"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        if r.status_code!=200: return None,"mubasher http"
        soup = BeautifulSoup(r.text,"html.parser")
        sels=[".last-price .value",".stock-last-price","span.price-value"]
        for s in sels:
            tag=soup.select_one(s)
            if tag and tag.text.strip():
                p=float(tag.text.strip().replace(",",""))
                if is_reasonable(t,p): return p,"mubasher"
        return None,"mubasher failed"
    except Exception as e: logger.warning(f"mubasher {t} error {e}")
    return None,"mubasher error"

# ---------------- Unified ----------------
def get_live_price(t):
    t=normalize(t); now=time.time()
    c=price_cache.get(t)
    if c and now-c["ts"]<CACHE_TTL: return c["price"],c["src"]
    for f in (fetch_yfinance,fetch_egxpy,fetch_mubasher):
        p,s=f(t)
        if p: 
            price_cache[t]={"price":p,"src":s,"ts":now}
            return p,s
    fb=BASE_PRICES.get(t)
    return (fb,"fallback") if fb else (None,"not found")

# ---------------- Indicators ----------------
def compute_rsi(series,period=14):
    delta=series.diff()
    gain=delta.clip(lower=0).rolling(period).mean()
    loss=-delta.clip(upper=0).rolling(period).mean()
    rs=gain/(loss.replace(0,np.nan))
    rsi=100-(100/(1+rs))
    val=float(rsi.iloc[-1])
    sig="Overbought" if val>70 else "Oversold" if val<30 else "Neutral"
    return {"value":round(val,2),"signal":sig}

def compute_macd(series):
    ema12=series.ewm(span=12).mean(); ema26=series.ewm(span=26).mean()
    macd=ema12-ema26; sig=macd.ewm(span=9).mean(); hist=macd-sig
    return float(macd.iloc[-1]),float(sig.iloc[-1]),float(hist.iloc[-1]),("Bullish" if macd.iloc[-1]>sig.iloc[-1] else "Bearish")

def calc_indicators(df):
    close=df["close"]; rsi=compute_rsi(close)
    mval,msig,mhist,mtxt=compute_macd(close)
    ma20=close.rolling(20).mean().iloc[-1]; ma50=close.rolling(50).mean().iloc[-1]; ma200=close.rolling(200).mean().iloc[-1]
    last=close.iloc[-1]; trend="Neutral"
    if last>ma50 and last>ma200: trend="Bullish"
    elif last<ma50 and last<ma200: trend="Bearish"
    action="BUY" if rsi["signal"]=="Oversold" and mval>msig and trend=="Bullish" else "SELL" if rsi["signal"]=="Overbought" and mval<msig and trend=="Bearish" else "HOLD"
    return {"rsi":rsi,"macd":{"value":mval,"signal":msig,"histogram":mhist,"signal_text":mtxt},"moving_averages":{"ma_20":ma20,"ma_50":ma50,"ma_200":ma200,"trend":trend},"recommendation":{"action":action}}

# ---------------- API ----------------
app=FastAPI(title="EGX API",version="1.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

@app.get("/api/stock/{ticker}")
def stock(ticker:str):
    p,s=get_live_price(ticker)
    if not p: raise HTTPException(404,"Price not found")
    df=pd.DataFrame({"close":[p]*250}) # synthetic history
    ind=calc_indicators(df)
    return {"ticker":ticker.upper(),"price_data":{"current_price":p,"price_source":s},"technical_indicators":ind}

@app.get("/api/prices")
def prices():
    out=[]
    for t in TICKER_MAP.keys():
        p,s=get_live_price(t)
        out.append({"ticker":t,"price":p,"source":s})
    return out

@app.get("/api/test-sources/{ticker}")
def test_sources(ticker:str):
    out={}
    for name,func in [("yfinance",fetch_yfinance),("egxpy",fetch_egxpy),("mubasher",fetch_mubasher)]:
        p,s=func(ticker)
        out[name]={"price":p,"status":"success" if p else "failed","source":s}
    return out

@app.get("/health")
def health(): return {"status":"ok","cache_entries":len(price_cache)}
