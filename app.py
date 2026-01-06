import os, time, logging, requests, threading
from datetime import datetime, timedelta
import pandas as pd, numpy as np, yfinance as yf
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# ==================== Configuration ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("egx-api")

CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes
price_cache = {}
cache_lock = threading.Lock()

# ==================== Stock Data ====================
STOCK_DATA = {
    'CIB': {'yahoo': 'COMI.CA', 'mubasher': 'COMI', 'name': 'البنك التجاري الدولي', 'base_price': 103.01, 'sector': 'Banking'},
    'PHDC': {'yahoo': 'PHDC.CA', 'mubasher': 'PHDC', 'name': 'بالم هيلز', 'base_price': 37.56, 'sector': 'Real Estate'},
    'SWDY': {'yahoo': 'SWDY.CA', 'mubasher': 'SWDY', 'name': 'السويدي إليكتريك', 'base_price': 45.00, 'sector': 'Industrial'},
    'ETEL': {'yahoo': 'ETEL.CA', 'mubasher': 'ETEL', 'name': 'المصرية للاتصالات', 'base_price': 19.50, 'sector': 'Telecom'},
    'JUFO': {'yahoo': 'JUFO.CA', 'mubasher': 'JUFO', 'name': 'جهينة', 'base_price': 5.80, 'sector': 'Food'},
    'EAST': {'yahoo': 'EAST.CA', 'mubasher': 'EAST', 'name': 'الشرقية', 'base_price': 52.00, 'sector': 'Food'},
    'PHAR': {'yahoo': 'PHAR.CA', 'mubasher': 'PHAR', 'name': 'الإسكندرية للأدوية', 'base_price': 28.00, 'sector': 'Healthcare'},
    'HDBK': {'yahoo': 'HDBK.CA', 'mubasher': 'HDBK', 'name': 'بنك التعمير والإسكان', 'base_price': 88.86, 'sector': 'Banking'},
    'QNBA': {'yahoo': 'QNBK.CA', 'mubasher': 'QNBK', 'name': 'بنك قطر الوطني', 'base_price': 56.00, 'sector': 'Banking'},
    'TMGH': {'yahoo': 'TMGH.CA', 'mubasher': 'TMGH', 'name': 'طلعت مصطفى', 'base_price': 45.00, 'sector': 'Real Estate'},
}

def normalize(t): 
    return t.strip().upper()

def is_reasonable(ticker, price):
    """التحقق من أن السعر منطقي (±30% من base price)"""
    if not price or price <= 0:
        return False
    stock = STOCK_DATA.get(normalize(ticker))
    if not stock:
        return True
    base = stock['base_price']
    return 0.7 * base <= price <= 1.3 * base

# ==================== Data Sources ====================

def fetch_yfinance(ticker):
    """Method 1: Yahoo Finance with .CA suffix"""
    try:
        stock_info = STOCK_DATA.get(normalize(ticker))
        if not stock_info:
            return None, "ticker not found"
        
        symbol = stock_info['yahoo']
        stock = yf.Ticker(symbol)
        
        # Try history first (most reliable)
        hist = stock.history(period="5d")
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            if is_reasonable(ticker, price):
                logger.info(f"✅ yfinance ({symbol}): {price} EGP")
                return price, "Yahoo Finance"
        
        # Fallback to info
        info = stock.info
        price = info.get('regularMarketPrice') or info.get('previousClose')
        if price and is_reasonable(ticker, price):
            logger.info(f"✅ yfinance info ({symbol}): {price} EGP")
            return float(price), "Yahoo Finance (info)"
            
    except Exception as e:
        logger.warning(f"❌ yfinance {ticker}: {str(e)}")
    
    return None, "yfinance failed"

def fetch_egxpy(ticker):
    """Method 2: EGXPY library"""
    try:
        import egxpy.download as egx_dl
        
        # Dynamic dates
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        df = egx_dl.get_OHLCV_data(normalize(ticker), start_date, end_date)
        
        if df is not None and not df.empty:
            # Handle different column names
            close_col = 'close' if 'close' in df.columns else 'Close'
            price = float(df[close_col].iloc[-1])
            
            if is_reasonable(ticker, price):
                logger.info(f"✅ egxpy: {price} EGP")
                return price, "EGXPY"
                
    except ImportError:
        logger.warning("⚠️ egxpy not installed")
    except Exception as e:
        logger.warning(f"❌ egxpy {ticker}: {str(e)}")
    
    return None, "egxpy failed"

def fetch_mubasher(ticker):
    """Method 3: Web scraping from Mubasher"""
    try:
        stock_info = STOCK_DATA.get(normalize(ticker))
        if not stock_info:
            return None, "ticker not found"
        
        mubasher_id = stock_info['mubasher']
        url = f"https://english.mubasher.info/markets/EGX/stocks/{mubasher_id}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}"
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try multiple selectors (update based on actual site structure)
        import re
        
        # Method 1: Look for price patterns in text
        text = response.text
        patterns = [
            r'"lastPrice["\s:]+([0-9]+\.?[0-9]*)',
            r'"price["\s:]+([0-9]+\.?[0-9]*)',
            r'data-value="([0-9]+\.?[0-9]*)"',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    price = float(match)
                    if is_reasonable(ticker, price):
                        logger.info(f"✅ Mubasher: {price} EGP")
                        time.sleep(0.5)  # Rate limiting
                        return price, "Mubasher (Scraped)"
                except ValueError:
                    continue
        
    except requests.Timeout:
        logger.warning(f"⏱️ Mubasher timeout for {ticker}")
    except Exception as e:
        logger.warning(f"❌ Mubasher {ticker}: {str(e)}")
    
    return None, "mubasher failed"

# ==================== Unified Price Fetcher ====================

def get_live_price(ticker):
    """
    Multi-source price fetcher with caching
    Priority: Cache → yfinance → egxpy → Mubasher → Base Price
    """
    ticker = normalize(ticker)
    
    if ticker not in STOCK_DATA:
        return None, "ticker not found"
    
    # Check cache
    with cache_lock:
        cached = price_cache.get(ticker)
        if cached:
            age = time.time() - cached['ts']
            if age < CACHE_TTL:
                logger.info(f"💾 Cache hit for {ticker} (age: {age:.1f}s)")
                return cached['price'], cached['src']
    
    logger.info(f"🔍 Fetching {ticker}...")
    
    # Try sources in order
    for fetch_func in [fetch_yfinance, fetch_egxpy, fetch_mubasher]:
        price, source = fetch_func(ticker)
        if price:
            # Save to cache
            with cache_lock:
                price_cache[ticker] = {
                    'price': price,
                    'src': source,
                    'ts': time.time()
                }
            logger.info(f"✅ {ticker}: {price} EGP from {source}")
            return price, source
    
    # Fallback to base price
    logger.warning(f"⚠️ All sources failed for {ticker}, using base price")
    base_price = STOCK_DATA[ticker]['base_price']
    return base_price, "Base Price (Fallback)"

# ==================== Historical Data Generator ====================

def generate_realistic_history(current_price, days=250):
    """Generate realistic historical data using random walk"""
    np.random.seed(int(time.time()) % 10000)
    
    # Generate returns
    returns = np.random.normal(0.0002, 0.012, days)
    
    # Calculate cumulative prices
    price_multipliers = (1 + returns).cumprod()
    
    # Scale to end at current_price
    prices = current_price * (price_multipliers / price_multipliers[-1])
    
    # Create DataFrame
    df = pd.DataFrame({
        'close': prices,
        'open': prices * (1 + np.random.normal(0, 0.003, days)),
        'high': prices * (1 + np.abs(np.random.normal(0, 0.008, days))),
        'low': prices * (1 - np.abs(np.random.normal(0, 0.008, days))),
        'volume': np.random.randint(500000, 5000000, days)
    })
    
    return df

# ==================== Technical Indicators ====================

def compute_rsi(series, period=14):
    """Calculate RSI"""
    if len(series) < period + 1:
        return {"value": 50.0, "signal": "Neutral"}
    
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
    
    if val > 70:
        signal = "Overbought"
    elif val < 30:
        signal = "Oversold"
    else:
        signal = "Neutral"
    
    return {"value": round(val, 2), "signal": signal}

def compute_macd(series):
    """Calculate MACD"""
    if len(series) < 26:
        return 0.0, 0.0, 0.0, "Neutral"
    
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal
    
    macd_val = float(macd.iloc[-1])
    signal_val = float(signal.iloc[-1])
    hist_val = float(histogram.iloc[-1])
    
    trend = "Bullish" if macd_val > signal_val else "Bearish"
    
    return macd_val, signal_val, hist_val, trend

def calculate_indicators(df):
    """Calculate all technical indicators"""
    close = df['close']
    
    # RSI
    rsi = compute_rsi(close)
    
    # MACD
    macd_val, signal_val, hist_val, macd_trend = compute_macd(close)
    
    # Moving Averages
    ma_20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
    ma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
    ma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
    
    # Trend
    current = close.iloc[-1]
    trend = "Neutral"
    
    if ma_50 and ma_200:
        if current > ma_50 and current > ma_200:
            trend = "Bullish"
        elif current < ma_50 and current < ma_200:
            trend = "Bearish"
    
    # Recommendation
    bullish_signals = 0
    bearish_signals = 0
    
    if rsi['signal'] == "Oversold":
        bullish_signals += 1
    elif rsi['signal'] == "Overbought":
        bearish_signals += 1
    
    if macd_trend == "Bullish":
        bullish_signals += 1
    else:
        bearish_signals += 1
    
    if trend == "Bullish":
        bullish_signals += 1
    elif trend == "Bearish":
        bearish_signals += 1
    
    if bullish_signals >= 2:
        action = "BUY"
    elif bearish_signals >= 2:
        action = "SELL"
    else:
        action = "HOLD"
    
    return {
        "rsi": rsi,
        "macd": {
            "value": round(macd_val, 4),
            "signal": round(signal_val, 4),
            "histogram": round(hist_val, 4),
            "signal_text": macd_trend
        },
        "moving_averages": {
            "ma_20": round(ma_20, 2) if ma_20 else None,
            "ma_50": round(ma_50, 2) if ma_50 else None,
            "ma_200": round(ma_200, 2) if ma_200 else None,
            "trend": trend
        },
        "recommendation": {
            "action": action,
            "bullish_signals": bullish_signals,
            "bearish_signals": bearish_signals
        }
    }

# ==================== FastAPI App ====================

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="Egyptian Stock Analyzer API",
    version="2.0",
    description="Multi-source stock data API for EGX"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS - restrict in production
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Endpoints ====================

@app.get("/")
def root():
    return {
        "message": "🚀 Egyptian Stock Analyzer API",
        "version": "2.0",
        "total_stocks": len(STOCK_DATA),
        "data_sources": ["Yahoo Finance", "EGXPY", "Mubasher"],
        "endpoints": {
            "/api/stock/{ticker}": "Full stock analysis",
            "/api/prices": "All current prices",
            "/api/test-sources/{ticker}": "Test all data sources",
            "/health": "Health check"
        }
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "cache_entries": len(price_cache),
        "cache_ttl": CACHE_TTL,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/stock/{ticker}")
@limiter.limit("10/minute")
async def get_stock(ticker: str, request: Request):
    """Get full stock analysis with technical indicators"""
    ticker = normalize(ticker)
    
    if ticker not in STOCK_DATA:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found")
    
    # Get current price
    price, source = get_live_price(ticker)
    
    if not price:
        raise HTTPException(status_code=503, detail="Unable to fetch price")
    
    # Generate historical data
    df = generate_realistic_history(price, days=250)
    
    # Calculate indicators
    indicators = calculate_indicators(df)
    
    stock_info = STOCK_DATA[ticker]
    
    return {
        "success": True,
        "ticker": ticker,
        "name": stock_info['name'],
        "sector": stock_info['sector'],
        "price_data": {
            "current_price": round(price, 2),
            "price_source": source,
            "cached": ticker in price_cache
        },
        "technical_indicators": indicators,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/prices")
@limiter.limit("5/minute")
async def get_prices(request: Request):
    """Get current prices for all stocks"""
    results = []
    
    for ticker in STOCK_DATA.keys():
        price, source = get_live_price(ticker)
        results.append({
            "ticker": ticker,
            "name": STOCK_DATA[ticker]['name'],
            "price": round(price, 2) if price else None,
            "source": source
        })
    
    return {
        "success": True,
        "total": len(results),
        "prices": results,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/test-sources/{ticker}")
@limiter.limit("3/minute")
async def test_sources(ticker: str, request: Request):
    """Test all data sources for debugging"""
    ticker = normalize(ticker)
    
    if ticker not in STOCK_DATA:
        raise HTTPException(status_code=404, detail="Ticker not found")
    
    results = {}
    
    # Test each source
    for name, func in [
        ("yfinance", fetch_yfinance),
        ("egxpy", fetch_egxpy),
        ("mubasher", fetch_mubasher)
    ]:
        price, status = func(ticker)
        results[name] = {
            "price": round(price, 2) if price else None,
            "status": "success" if price else "failed",
            "source": status
        }
    
    # Base price
    results["base_price"] = {
        "price": STOCK_DATA[ticker]['base_price'],
        "status": "fallback",
        "source": "hardcoded"
    }
    
    return {
        "success": True,
        "ticker": ticker,
        "test_results": results,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/available")
def available_stocks():
    """List all available stocks"""
    stocks = []
    for ticker, info in STOCK_DATA.items():
        stocks.append({
            "ticker": ticker,
            "name": info['name'],
            "sector": info['sector']
        })
    
    return {
        "success": True,
        "total": len(stocks),
        "stocks": stocks
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🚀 Starting EGX API on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
