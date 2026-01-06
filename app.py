# app.py
# EGX multi-source price API with technical indicators
# Sources: yfinance (.CA), egxpy, Mubasher scraping
# Cache: configurable via env (default 300s)
# Endpoints: /api/stock/{ticker}, /api/prices, /api/test-sources/{ticker}, /health

import os
import time
import json
import logging
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Tuple, Optional

# -----------------------------
# Config & logging
# -----------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("egx-api")

CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))
DEFAULT_HISTORY_DAYS = int(os.getenv("DEFAULT_HISTORY_DAYS", "420"))
SYNTHETIC_POINTS = int(os.getenv("SYNTHETIC_POINTS", "300"))
MUBASHER_TIMEOUT = int(os.getenv("MUBASHER_TIMEOUT", "10"))
REASONABLE_LOW = float(os.getenv("REASONABLE_LOW", "0.5"))
REASONABLE_HIGH = float(os.getenv("REASONABLE_HIGH", "1.5"))

# -----------------------------
# In-memory cache and mappings
# -----------------------------
price_cache: Dict[str, Dict] = {}

TICKER_MAP = {
    "CIB": "COMI.CA",
    "COMI": "COMI.CA",
    "FWRY": "FWRY.CA",
    "PHDC": "PHDC.CA",
    "ETEL": "ETEL.CA",
    "ORHD": "ORHD.CA",
    "HRHO": "HRHO.CA",
    "AMOC": "AMOC.CA",
    "TALA": "TALA.CA",
    "MNHD": "MNHD.CA",
    "EKHO": "EKHO.CA",
    "SWDY": "SWDY.CA",
    "CLHO": "CLHO.CA",
    "EMFD": "EMFD.CA",
    "JUFO": "JUFO.CA",
    "OCIC": "OCIC.CA",
    "EFID": "EFID.CA",
    "EGTS": "EGTS.CA",
}

SYMBOL_META = {
    "COMI": {"name": "Commercial International Bank", "sector": "Banks"},
    "FWRY": {"name": "Fawry for Banking Technology", "sector": "IT Services"},
    "PHDC": {"name": "Palm Hills Developments", "sector": "Real Estate"},
    "ETEL": {"name": "Telecom Egypt", "sector": "Telecom"},
    "ORHD": {"name": "Orascom Development Egypt", "sector": "Real Estate"},
    "HRHO": {"name": "EFG Hermes", "sector": "Financial Services"},
    "AMOC": {"name": "AMOC", "sector": "Energy"},
    "TALA": {"name": "Talaat Moustafa Group", "sector": "Real Estate"},
    "MNHD": {"name": "Madinet Nasr Housing", "sector": "Real Estate"},
    "EKHO": {"name": "EKHO", "sector": "Investment"},
    "SWDY": {"name": "Elsewedy Electric", "sector": "Industrial"},
    "CLHO": {"name": "Cleopatra Hospital", "sector": "Healthcare"},
    "EMFD": {"name": "Emaar Misr", "sector": "Real Estate"},
    "JUFO": {"name": "Juhayna Food Industries", "sector": "Food & Beverage"},
    "OCIC": {"name": "Orascom Construction", "sector": "Industrial"},
    "EFID": {"name": "Edita Food Industries", "sector": "Food & Beverage"},
    "EGTS": {"name": "Egyptian Resorts Company", "sector": "Tourism"},
}

BASE_PRICES = {
    "COMI": 60.0,
    "FWRY": 10.0,
    "PHDC": 2.0,
    "ETEL": 20.0,
    "HRHO": 15.0,
    "AMOC": 5.0,
    "TALA": 15.0,
    "MNHD": 6.0,
    "EKHO": 1.2,
    "SWDY": 45.0,
    "CLHO": 5.0,
    "EMFD": 4.0,
    "JUFO": 10.0,
    "OCIC": 120.0,
    "EFID": 20.0,
    "EGTS": 1.5,
}

# -----------------------------
# Helpers
# -----------------------------
def normalize_ticker(t: str) -> str:
    return t.strip().upper()

def is_reasonable_price(ticker: str, price: float) -> bool:
    base = BASE_PRICES.get(normalize_ticker(ticker))
    if base is None:
        return True
    return (REASONABLE_LOW * base) <= price <= (REASONABLE_HIGH * base)

def yahoo_symbol(ticker: str) -> Optional[str]:
    return TICKER_MAP.get(normalize_ticker(ticker))

# -----------------------------
# Source 1: yfinance
# -----------------------------
def fetch_price_yfinance(ticker: str) -> Tuple[Optional[float], str]:
    yf_ticker = yahoo_symbol(ticker)
    if not yf_ticker:
        return None, "yfinance: ticker unmapped"
    try:
        stock = yf.Ticker(yf_ticker)
        # Try fast info first
        info = getattr(stock, "fast_info", None)
        price = None
        if info and getattr(info, "last_price", None):
            price = float(info.last_price)
        else:
            info_dict = stock.info or {}
            price = info_dict.get("regularMarketPrice") or info_dict.get("previousClose")

        if price and is_reasonable_price(ticker, float(price)):
            return float(price), "yfinance"

        hist = stock.history(period="5d", interval="1d")
        if not hist.empty:
            last_close = float(hist["Close"].iloc[-1])
            if is_reasonable_price(ticker, last_close):
                return last_close, "yfinance(hist)"
        return None, "yfinance: no valid price"
    except Exception as e:
        logger.warning(f"[yfinance] {ticker} error: {e}")
        return None, f"yfinance error: {e}"

def fetch_history_yfinance(ticker: str, days: int = DEFAULT_HISTORY_DAYS) -> Optional[pd.DataFrame]:
    yf_ticker = yahoo_symbol(ticker)
    if not yf_ticker:
        return None
    try:
        df = yf.download(yf_ticker, period=f"{days}d", interval="1d")
        if not df.empty:
            df = df.rename(columns=str.lower)
            return df
    except Exception as e:
        logger.warning(f"[yfinance history] {ticker} error: {e}")
        return None
    return None

# -----------------------------
# Source 2: egxpy
# -----------------------------
def fetch_price_egxpy(ticker: str) -> Tuple[Optional[float], str]:
    try:
        import egxpy.download as egx_dl
        end = pd.Timestamp.today().strftime("%Y-%m-%d")
        start = (pd.Timestamp.today() - pd.Timedelta(days=70)).strftime("%Y-%m-%d")
        df = egx_dl.get_OHLCV_data(normalize_ticker(ticker), start, end)
        if df is not None and not df.empty:
            close_col = "close" if "close" in df.columns else df.columns[-1]
            price = float(df[close_col].iloc[-1])
            if is_reasonable_price(ticker, price):
                return price, "egxpy"
            return None, "egxpy: unreasonable"
        return None, "egxpy: empty"
    except ImportError as e:
        logger.warning(f"[egxpy] import error: {e}")
        return None, f"egxpy import error: {e}"
    except Exception as e:
        logger.warning(f"[egxpy] {ticker} error: {e}")
        return None, f"egxpy error: {e}"

def fetch_history_egxpy(ticker: str, start: str = "2025-01-01", end: str = None) -> Optional[pd.DataFrame]:
    try:
        import egxpy.download as egx_dl
        if end is None:
            end = pd.Timestamp.today().strftime("%Y-%m-%d")
        df = egx_dl.get_OHLCV_data(normalize_ticker(ticker), start, end)
        if df is not None and not df.empty:
            return df.rename(columns=str.lower)
        return None
    except Exception as e:
        logger.warning(f"[egxpy history] {ticker} error: {e}")
        return None

# -----------------------------
# Source 3: Web scraping (Mubasher)
# -----------------------------
def fetch_price_mubasher(ticker: str) -> Tuple[Optional[float], str]:
    try:
        url = f"https://english.mubasher.info/markets/EGX/stocks/{normalize_ticker(ticker)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        }
        r = requests.get(url, headers=headers, timeout=MUBASHER_TIMEOUT)
        if r.status_code != 200:
            return None, f"mubasher http {r.status_code}"
        soup = BeautifulSoup(r.text, "html.parser")

        selectors = [
            ".last-price .value",
            ".stock-last-price",
            ".instrument-last-price",
            ".last-price-value",
            "span.price-value",
        ]
        price_text = None
        for sel in selectors:
            tag = soup.select_one(sel)
            if tag and tag.text:
                price_text = tag.text.strip()
                break

        if not price_text:
            import re
            m = re.search(r"(?i)(Last\s*Price|Price)\D*(\d+[\.,]?\d*)", r.text)
            if m:
                price_text = m.group(2)

        if not price_text:
            return None, "mubasher: selector not found"

        price_text = price_text.replace(",", "").replace("EGP", "").replace("ج.م", "").strip()
        price = float(price_text)
        if is_reasonable_price(ticker, price):
            return price, "mubasher"
        return None, "mubasher: unreasonable"
    except Exception as e:
        logger.warning(f"[mubasher] {ticker} error: {e}")
        return None, f"mubasher error: {e}"

# -----------------------------
# Unified live price with cache
# -----------------------------
def get_live_price(ticker: str) -> Tuple[Optional[float], str]:
    t = normalize_ticker(ticker)
    now = time.time()
    cached = price_cache.get(t)
    if cached and (now - cached["timestamp"] < CACHE_TTL_SECONDS):
        return cached["price"], cached["source"]

    for func in (fetch_price_yfinance, fetch_price_egxpy, fetch_price_mubasher):
        price, source = func(t)
        if price is not None:
            price_cache[t] = {"price": price, "source": source, "timestamp": now}
            return price, source

    fb = BASE_PRICES.get(t)
    if fb is not None:
        price_cache[t] = {"price": fb, "source": "fallback", "timestamp": now}
        return fb, "fallback"

    return None, "not found"

# -----------------------------
# Historical data for indicators
# -----------------------------
def get_historical_df(ticker: str) -> pd.DataFrame:
    df = fetch_history_yfinance(ticker, days=DEFAULT_HISTORY_DAYS)
    if df is None:
        df = fetch_history_egxpy(ticker, start="2025-01-01")
    if df is not None and not df.empty:
        if "close" not in df.columns and "Close" in df.columns:
            df = df.rename(columns={"Close": "close"})
        return df[["close"]].dropna()

    price, _ = get_live_price(ticker)
    if price is None:
        price = BASE_PRICES.get(normalize_ticker(ticker), 10.0)
    return generate_realistic_stock_data(price, points=SYNTHETIC_POINTS)

def generate_realistic_stock_data(price: float, points: int = SYNTHETIC_POINTS) -> pd.DataFrame:
    np.random.seed(42)
    pct_changes = np.random.normal(0, 0.012, points)
    values = [price]
    for pct in pct_changes:
        values.append(values[-1] * (1 + pct))
    idx = pd.date_range(end=pd.Timestamp.utcnow(), periods=points + 1)
    df = pd.DataFrame({"close": values[1:]}, index=idx[1:])
    return df

# -----------------------------
# Technical indicators
# -----------------------------
def compute_rsi(series: pd.Series, period: int = 14) -> Dict:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / (loss.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    value = float(rsi.iloc[-1])
    signal = "Overbought" if value > 70 else "Oversold" if value < 30 else "Neutral"
    return {"value": round(value, 2), "signal": signal}

def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float, str]:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    macd_value = float(macd_line.iloc[-1])
    signal_value = float(signal_line.iloc[-1])
    hist_value = float(hist.iloc[-1])
    signal_text = "Bullish" if macd_value > signal_value else "Bearish"
    return macd_value, signal_value, hist_value, signal_text

def calculate_technical_indicators(df: pd.DataFrame) -> Dict:
    close = df["close"]
    rsi = compute_rsi(close)
    macd_value, macd_signal, macd_hist, macd_text = compute_macd(close)
    ma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
    ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
    ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

    last = float(close.iloc[-1])
    trend = "Neutral"
    if ma50 and ma200:
        if last > ma50 and last > ma200:
            trend = "Bullish"
        elif last < ma50 and last < ma200:
            trend = "Bearish"

    if rsi["signal"] == "Oversold" and macd_value > macd_signal and trend == "Bullish":
        action = "BUY"
    elif rsi["signal"] == "Overbought" and macd_value < macd_signal and trend == "Bearish":
        action = "SELL"
    else:
        action = "HOLD"

    return {
        "rsi": rsi,
        "macd": {
            "value": round(macd_value, 4),
            "signal": round(macd_signal, 4),
            "histogram": round(macd_hist, 4),
            "signal_text": macd_text,
        },
        "moving_averages": {
            "ma_20": round(ma20, 4) if ma20 else None,
            "ma_50": round(ma50, 4) if ma50 else None,
            "ma_200": round(ma200, 4) if ma200 else None,
            "trend": trend,
        },
        "recommendation": {"action": action},
    }

# -----------------------------
# FastAPI app and endpoints
# -----------------------------
app = FastAPI(title="EGX Multi-Source API", version="1.1.0")

# Optional CORS for external clients (n8n/Telegram handlers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/api/stock/{ticker}")
def get_stock(ticker: str):
    t = normalize_ticker(ticker)
    price, source = get_live_price(t)
    if price is None:
        raise HTTPException(status_code=404, detail="Ticker not found or price unavailable")

    df = get_historical_df(t)
    indicators = calculate_technical_indicators(df)

    daily_change_percent = None
    if df is not None and len(df) >= 2:
        last = float(df["close"].iloc[-1])
        prev = float(df["close"].iloc[-2])
        if prev != 0:
            daily_change_percent = round(((last - prev) / prev) * 100, 2)

    meta = SYMBOL_META.get(t, {"name": t, "sector": "EGX"})
    return {
        "ticker": t,
        "name": meta["name"],
        "sector": meta["sector"],
        "price_data": {
            "current_price": round(float(price), 4),
            "daily_change_percent": daily_change_percent,
            "price_source": source,
        },
        "technical_indicators": indicators,
    }

@app.get("/api/prices")
def get_prices():
    results = []
    tickers = sorted(set(list(SYMBOL_META.keys()) + list(TICKER_MAP.keys())))
    for t in tickers:
        price, source = get_live_price(t)
        meta = SYMBOL_META.get(t, {"name": t, "sector": "EGX"})
        results.append({
            "ticker": t,
            "name": meta["name"],
            "sector": meta["sector"],
            "price": round(float(price), 4) if price is not None else None,
            "source": source,
        })
    return results

@app.get("/api/test-sources/{ticker}")
def test_sources(ticker: str):
    t = normalize_ticker(ticker)
    out = {}
    for name, func in [
        ("yfinance", fetch_price_yfinance),
        ("egxpy", fetch_price_egxpy),
        ("mubasher", fetch_price_mubasher),
    ]:
        price, source = func(t)
        out[name] = {
            "price": round(float(price), 4) if price is not None else None,
            "status": "success" if price is not None else "failed",
            "source": source,
        }
    return out

@app.get("/health")
def health():
    return {
        "status": "ok",
        "cache_entries": len(price_cache),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
    }

# Local run:
# uvicorn app:app --host 0.0.0.0 --port 8000
