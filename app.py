from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import yfinance as yf
import os
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

# قائمة الأسهم المصرية
STOCK_BASE_DATA = {
    # البنوك
    'CIB': {'name': 'البنك التجاري الدولي', 'base_price': 103.01, 'sector': 'Banking', 'isin': 'EGS60121C018', 'mubasher_id': 'COMI', 'yahoo_symbol': 'COMI.CA'},
    'COMI': {'name': 'المصرف المتحد', 'base_price': 14.59, 'sector': 'Banking', 'isin': 'EGS60131C016', 'mubasher_id': 'COMI', 'yahoo_symbol': 'COMI.CA'},
    'HDBK': {'name': 'بنك التعمير والإسكان', 'base_price': 88.86, 'sector': 'Banking', 'isin': 'EGS60041C011', 'mubasher_id': 'HDBK', 'yahoo_symbol': 'HDBK.CA'},
    'QNBA': {'name': 'بنك قطر الوطني الأهلي', 'base_price': 56.00, 'sector': 'Banking', 'isin': 'EGS60061C017', 'mubasher_id': 'QNBK', 'yahoo_symbol': 'QNBK.CA'},
    'CIEB': {'name': 'كريدي أجريكول', 'base_price': 127.00, 'sector': 'Banking', 'isin': 'EGS60151C014', 'mubasher_id': 'CIEB', 'yahoo_symbol': 'CIEB.CA'},
    
    # العقارات
    'PHDC': {'name': 'بالم هيلز للتعمير', 'base_price': 37.56, 'sector': 'Real Estate', 'isin': 'EGS673L1C015', 'mubasher_id': 'PHDC', 'yahoo_symbol': 'PHDC.CA'},
    'OCDI': {'name': 'أوراسكوم للتنمية', 'base_price': 88.02, 'sector': 'Real Estate', 'isin': 'EGS383S1C011', 'mubasher_id': 'OCDI', 'yahoo_symbol': 'OCDI.CA'},
    'TMGH': {'name': 'طلعت مصطفى القابضة', 'base_price': 45.00, 'sector': 'Real Estate', 'isin': 'EGS65401C011', 'mubasher_id': 'TMGH', 'yahoo_symbol': 'TMGH.CA'},
    
    # الصناعة
    'SWDY': {'name': 'السويدي إليكتريك', 'base_price': 45.00, 'sector': 'Industrial', 'isin': 'EGS65451C019', 'mubasher_id': 'SWDY', 'yahoo_symbol': 'SWDY.CA'},
    'ORAS': {'name': 'أوراسكوم كونستراكشون', 'base_price': 380.00, 'sector': 'Industrial', 'isin': 'EGS383S1C011', 'mubasher_id': 'ORAS', 'yahoo_symbol': 'ORAS.CA'},
    
    # الأغذية
    'JUFO': {'name': 'جهينة للصناعات الغذائية', 'base_price': 5.80, 'sector': 'Food & Beverage', 'isin': 'EGS65611C015', 'mubasher_id': 'JUFO', 'yahoo_symbol': 'JUFO.CA'},
    'EAST': {'name': 'الشرقية ايسترن كومباني', 'base_price': 52.00, 'sector': 'Food & Beverage', 'isin': 'EGS60181C016', 'mubasher_id': 'EAST', 'yahoo_symbol': 'EAST.CA'},
    
    # الأدوية
    'PHAR': {'name': 'الإسكندرية للأدوية', 'base_price': 28.00, 'sector': 'Healthcare', 'isin': 'EGS60282C012', 'mubasher_id': 'PHAR', 'yahoo_symbol': 'PHAR.CA'},
    
    # الاتصالات
    'ETEL': {'name': 'المصرية للاتصالات', 'base_price': 19.50, 'sector': 'Telecommunications', 'isin': 'EGS68101C013', 'mubasher_id': 'ETEL', 'yahoo_symbol': 'ETEL.CA'},
}

# Cache
price_cache = {}
cache_timestamp = {}
price_source = {}
CACHE_DURATION = 300  # 5 دقائق

# ==================== METHOD 1: yfinance (Yahoo Finance) ====================
def get_price_yfinance(ticker):
    """الطريقة 1: yfinance مع .CA suffix"""
    try:
        stock_info = STOCK_BASE_DATA.get(ticker)
        if not stock_info:
            return None
        
        yahoo_symbol = stock_info.get('yahoo_symbol', f"{ticker}.CA")
        
        # جرب download (أسرع)
        stock = yf.Ticker(yahoo_symbol)
        hist = stock.history(period='1d')
        
        if not hist.empty:
            price = float(hist['Close'].iloc[-1])
            if price > 0:
                print(f"✅ yfinance ({yahoo_symbol}): {price} EGP")
                return {'price': price, 'source': 'Yahoo Finance', 'method': 'yfinance'}
        
        return None
        
    except Exception as e:
        print(f"❌ yfinance error: {str(e)}")
        return None

# ==================== METHOD 2: egxpy ====================
def get_price_egxpy(ticker):
    """الطريقة 2: egxpy - المكتبة المتخصصة"""
    try:
        from egxpy.download import get_EGXdata
        
        # استخدام ticker المحلي بدون suffix
        data = get_EGXdata([ticker], interval='1D', period='5d')
        
        if data is not None and not data.empty:
            if ticker in data.columns or ticker in data:
                price_data = data[ticker] if ticker in data else data
                
                if isinstance(price_data, pd.DataFrame):
                    price = float(price_data['Close'].iloc[-1]) if 'Close' in price_data.columns else float(price_data.iloc[-1].values[0])
                else:
                    price = float(price_data.iloc[-1])
                
                if price > 0:
                    print(f"✅ egxpy: {price} EGP")
                    return {'price': price, 'source': 'EGXPY', 'method': 'egxpy'}
        
        return None
        
    except ImportError:
        print(f"⚠️ egxpy not installed")
        return None
    except Exception as e:
        print(f"❌ egxpy error: {str(e)}")
        return None

# ==================== METHOD 3: Web Scraping - Mubasher ====================
def get_price_mubasher(ticker):
    """الطريقة 3: Web Scraping من Mubasher"""
    try:
        stock_info = STOCK_BASE_DATA.get(ticker)
        if not stock_info:
            return None
        
        mubasher_id = stock_info.get('mubasher_id', ticker)
        url = f"https://english.mubasher.info/markets/EGX/stocks/{mubasher_id}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # جرب selectors مختلفة
            price_selectors = [
                {'class': 'last-price'},
                {'class': 'lastPrice'},
                {'class': 'price'},
                {'data-field': 'lastPrice'},
            ]
            
            for selector in price_selectors:
                price_element = soup.find(class_=selector.get('class')) if 'class' in selector else soup.find(attrs=selector)
                
                if price_element:
                    price_text = price_element.get_text().strip()
                    # Clean the price
                    price_text = price_text.replace(',', '').replace('EGP', '').replace('ج.م', '').strip()
                    
                    try:
                        price = float(price_text)
                        if price > 0:
                            print(f"✅ Mubasher scraping: {price} EGP")
                            return {'price': price, 'source': 'Mubasher (Scraped)', 'method': 'scraping'}
                    except ValueError:
                        continue
        
        return None
        
    except Exception as e:
        print(f"❌ Mubasher scraping error: {str(e)}")
        return None

# ==================== HYBRID: Multi-Source Price Fetcher ====================
def get_live_price(ticker):
    """
    Multi-Source Hybrid Price Fetcher
    الأولوية: yfinance → egxpy → Mubasher Scraping → Base Price
    """
    global price_cache, cache_timestamp, price_source
    
    # 1. Check cache first
    if ticker in price_cache and ticker in cache_timestamp:
        time_diff = (datetime.now() - cache_timestamp[ticker]).seconds
        if time_diff < CACHE_DURATION:
            return price_cache[ticker]
    
    print(f"\n🔍 Fetching {ticker}...")
    
    result = None
    
    # 2. Try yfinance (Most stable)
    print(f"  [1/3] Trying yfinance... ", end='')
    result = get_price_yfinance(ticker)
    
    # 3. Try egxpy (EGX specialist)
    if not result:
        print(f"  [2/3] Trying egxpy... ", end='')
        result = get_price_egxpy(ticker)
    
    # 4. Try Mubasher scraping (Live data)
    if not result:
        print(f"  [3/3] Trying Mubasher scraping... ", end='')
        result = get_price_mubasher(ticker)
        time.sleep(1)  # Rate limiting
    
    # 5. Save to cache if successful
    if result and result.get('price'):
        price = result['price']
        source = result['source']
        
        price_cache[ticker] = price
        cache_timestamp[ticker] = datetime.now()
        price_source[ticker] = source
        STOCK_BASE_DATA[ticker]['base_price'] = price
        
        print(f"✅ Success!")
        return price
    
    # 6. Fallback to base price
    print(f"⚠️ All methods failed, using base price")
    price = STOCK_BASE_DATA[ticker]['base_price']
    price_source[ticker] = 'Base Price (Fallback)'
    return price

def get_current_price(ticker):
    """Get current price"""
    return get_live_price(ticker)

def generate_realistic_stock_data(ticker, days=365):
    """Generate historical data"""
    current_price = get_live_price(ticker)
    
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    seed = hash(ticker + dates[0].strftime('%Y%m%d')) % 100000
    np.random.seed(seed)
    
    returns = np.random.normal(0.0001, 0.015, days)
    cumulative_return = (1 + returns).cumprod()
    starting_price = current_price / cumulative_return[-1]
    
    price_series = pd.Series(starting_price * cumulative_return, index=dates)
    price_series.iloc[-1] = current_price
    
    high = price_series * (1 + np.abs(np.random.normal(0, 0.008, days)))
    low = price_series * (1 - np.abs(np.random.normal(0, 0.008, days)))
    volume = np.random.randint(500000, 8000000, days)
    
    df = pd.DataFrame({
        'Open': price_series * (1 + np.random.normal(0, 0.003, days)),
        'High': high,
        'Low': low,
        'Close': price_series,
        'Volume': volume
    }, index=dates)
    
    return df

def calculate_technical_indicators(data):
    """Calculate technical indicators"""
    current_price = float(data['Close'].iloc[-1])
    prev_close = float(data['Close'].iloc[-2])
    daily_change = ((current_price - prev_close) / prev_close) * 100
    
    # Moving Averages
    ma_20 = float(data['Close'].tail(20).mean()) if len(data) >= 20 else None
    ma_50 = float(data['Close'].tail(50).mean()) if len(data) >= 50 else None
    ma_200 = float(data['Close'].tail(200).mean()) if len(data) >= 200 else None
    
    # RSI
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    rsi_value = rs.iloc[-1]
    rsi = float(100 - (100 / (1 + rsi_value))) if rsi_value > 0 and not pd.isna(rsi_value) else 50.0
    
    # MACD
    ema_12 = data['Close'].ewm(span=12, adjust=False).mean()
    ema_26 = data['Close'].ewm(span=26, adjust=False).mean()
    macd = float(ema_12.iloc[-1] - ema_26.iloc[-1])
    signal_line = float((ema_12 - ema_26).ewm(span=9, adjust=False).mean().iloc[-1])
    
    # Trend
    trend = 'Bullish' if ma_50 and current_price > ma_50 else 'Bearish' if ma_50 else 'Neutral'
    
    # Recommendation
    signals = []
    if rsi < 30:
        signals.append('oversold')
    if rsi > 70:
        signals.append('overbought')
    if macd > signal_line:
        signals.append('bullish_macd')
    if trend == 'Bullish':
        signals.append('bullish_trend')
    
    if 'oversold' in signals or (len(signals) >= 2 and 'bullish_macd' in signals and 'bullish_trend' in signals):
        recommendation = 'BUY'
    elif 'overbought' in signals:
        recommendation = 'SELL'
    else:
        recommendation = 'HOLD'
    
    return {
        'current_price': current_price,
        'daily_change': daily_change,
        'ma_20': ma_20,
        'ma_50': ma_50,
        'ma_200': ma_200,
        'rsi': rsi,
        'macd': macd,
        'signal_line': signal_line,
        'trend': trend,
        'recommendation': recommendation
    }

# ==================== API ENDPOINTS ====================

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'message': '🚀 Egyptian Stock Analyzer API',
        'status': 'healthy',
        'version': '6.0 - Multi-Source Production',
        'total_stocks': len(STOCK_BASE_DATA),
        'data_sources': {
            'primary': 'Yahoo Finance (yfinance with .CA suffix)',
            'secondary': 'EGXPY (EGX specialist library)',
            'tertiary': 'Mubasher (Web scraping)',
            'fallback': 'Base prices'
        },
        'cache_duration': f'{CACHE_DURATION}s',
        'methods': ['yfinance', 'egxpy', 'scraping'],
        'endpoints': {
            '/': 'API Info',
            '/health': 'Health check',
            '/api/stock/<ticker>': 'Stock analysis',
            '/api/prices': 'All prices',
            '/api/refresh/<ticker>': 'Refresh price',
            '/api/test-sources/<ticker>': 'Test all data sources'
        }
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'uptime': 'running',
        'stocks_loaded': len(STOCK_BASE_DATA),
        'cache_size': len(price_cache),
        'version': '6.0'
    }), 200

@app.route('/api/test-sources/<ticker>', methods=['GET'])
def test_sources(ticker):
    """Test all data sources for a ticker"""
    ticker = ticker.upper()
    
    if ticker not in STOCK_BASE_DATA:
        return jsonify({'success': False, 'error': f'Ticker {ticker} not found'}), 404
    
    results = {}
    
    # Test yfinance
    print(f"\n🧪 Testing yfinance for {ticker}...")
    yf_result = get_price_yfinance(ticker)
    results['yfinance'] = yf_result if yf_result else {'status': 'failed'}
    
    # Test egxpy
    print(f"\n🧪 Testing egxpy for {ticker}...")
    egxpy_result = get_price_egxpy(ticker)
    results['egxpy'] = egxpy_result if egxpy_result else {'status': 'failed'}
    
    # Test Mubasher scraping
    print(f"\n🧪 Testing Mubasher scraping for {ticker}...")
    mubasher_result = get_price_mubasher(ticker)
    results['mubasher'] = mubasher_result if mubasher_result else {'status': 'failed'}
    
    # Base price
    results['base_price'] = {
        'price': STOCK_BASE_DATA[ticker]['base_price'],
        'source': 'Fallback',
        'method': 'hardcoded'
    }
    
    return jsonify({
        'success': True,
        'ticker': ticker,
        'name': STOCK_BASE_DATA[ticker]['name'],
        'test_results': results,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/stock/<ticker>', methods=['GET'])
def analyze_stock(ticker):
    """Full stock analysis"""
    try:
        ticker = ticker.upper()
        
        if ticker not in STOCK_BASE_DATA:
            return jsonify({
                'success': False,
                'error': f'Ticker {ticker} not found'
            }), 404
        
        days = int(request.args.get('days', 365))
        data = generate_realistic_stock_data(ticker, days)
        indicators = calculate_technical_indicators(data)
        stock_info = STOCK_BASE_DATA[ticker]
        
        return jsonify({
            'success': True,
            'ticker': ticker,
            'name': stock_info['name'],
            'sector': stock_info['sector'],
            'price_source': price_source.get(ticker, 'Not fetched yet'),
            'price_data': {
                'current_price': round(indicators['current_price'], 2),
                'daily_change_percent': round(indicators['daily_change'], 2),
            },
            'technical_indicators': {
                'rsi': {'value': round(indicators['rsi'], 2)},
                'macd': {'signal_text': 'Bullish' if indicators['macd'] > indicators['signal_line'] else 'Bearish'},
                'moving_averages': {'trend': indicators['trend']}
            },
            'recommendation': {'action': indicators['recommendation']}
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/prices', methods=['GET'])
def current_prices():
    """Get all current prices"""
    prices = {}
    
    for ticker in list(STOCK_BASE_DATA.keys())[:5]:  # Test مع 5 أسهم فقط
        current = get_current_price(ticker)
        prices[ticker] = {
            'name': STOCK_BASE_DATA[ticker]['name'],
            'price': round(current, 2),
            'source': price_source.get(ticker, 'Not fetched')
        }
    
    return jsonify({
        'success': True,
        'total': len(prices),
        'prices': prices
    })

@app.route('/api/refresh/<ticker>', methods=['GET'])
def refresh_price(ticker):
    """Force refresh price"""
    ticker = ticker.upper()
    
    if ticker not in STOCK_BASE_DATA:
        return jsonify({'success': False, 'error': 'Ticker not found'}), 404
    
    # Clear cache
    if ticker in price_cache:
        del price_cache[ticker]
    if ticker in cache_timestamp:
        del cache_timestamp[ticker]
    
    new_price = get_live_price(ticker)
    
    return jsonify({
        'success': True,
        'ticker': ticker,
        'price': round(new_price, 2),
        'source': price_source.get(ticker, 'Unknown'),
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 80)
    print("🚀 Egyptian Stock Analyzer API v6.0 - Multi-Source Production")
    print("=" * 80)
    print(f"📊 Stocks: {len(STOCK_BASE_DATA)}")
    print(f"🔄 Data Sources: yfinance → egxpy → Mubasher Scraping → Base Prices")
    print(f"⏱️  Cache: {CACHE_DURATION}s")
    print(f"🌐 Port: {port}")
    print("=" * 80)
    app.run(host='0.0.0.0', port=port, debug=False)
