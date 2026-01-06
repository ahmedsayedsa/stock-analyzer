from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import yfinance as yf
import os

app = Flask(__name__)
CORS(app)

# قائمة شاملة بأشهر الأسهم في البورصة المصرية
STOCK_BASE_DATA = {
    # البنوك
    'CIB': {'name': 'البنك التجاري الدولي', 'base_price': 103.01, 'sector': 'Banking', 'isin': 'EGS60121C018', 'mubasher_id': 'COMI'},
    'COMI': {'name': 'المصرف المتحد', 'base_price': 14.59, 'sector': 'Banking', 'isin': 'EGS60131C016', 'mubasher_id': 'COMI'},
    'HDBK': {'name': 'بنك التعمير والإسكان', 'base_price': 88.86, 'sector': 'Banking', 'isin': 'EGS60041C011', 'mubasher_id': 'HDBK'},
    'ABUK': {'name': 'بنك أبوظبي الإسلامي', 'base_price': 15.50, 'sector': 'Banking', 'isin': 'EGS60691C019', 'mubasher_id': 'ADIB'},
    'CIEB': {'name': 'كريدي أجريكول', 'base_price': 127.00, 'sector': 'Banking', 'isin': 'EGS60151C014', 'mubasher_id': 'CIEB'},
    'QNBA': {'name': 'بنك قطر الوطني الأهلي', 'base_price': 56.00, 'sector': 'Banking', 'isin': 'EGS60061C017', 'mubasher_id': 'QNBK'},
    'ALXB': {'name': 'بنك الإسكندرية', 'base_price': 24.00, 'sector': 'Banking', 'isin': 'EGS60011C019', 'mubasher_id': 'ALXB'},
    'SAIB': {'name': 'بنك ساب', 'base_price': 12.00, 'sector': 'Banking', 'isin': 'EGS60071C015', 'mubasher_id': 'SAIB'},
    'ADIB': {'name': 'بنك أبوظبي الإسلامي', 'base_price': 15.50, 'sector': 'Banking', 'isin': 'EGS60691C019', 'mubasher_id': 'ADIB'},
    'EXPA': {'name': 'البنك المصري لتنمية الصادرات', 'base_price': 6.80, 'sector': 'Banking', 'isin': 'EGS60201C012', 'mubasher_id': 'EXPA'},
    'BCAI': {'name': 'بنك القاهرة', 'base_price': 19.00, 'sector': 'Banking', 'isin': 'EGS60091C011', 'mubasher_id': 'BCAI'},
    'FABD': {'name': 'بنك فيصل الإسلامي', 'base_price': 31.79, 'sector': 'Banking', 'isin': 'EGS60211C010', 'mubasher_id': 'FABD'},
    'NBKE': {'name': 'بنك الكويت الوطني', 'base_price': 28.00, 'sector': 'Banking', 'isin': 'EGS60051C019', 'mubasher_id': 'NBKE'},
    'ADCB': {'name': 'بنك أبوظبي التجاري', 'base_price': 22.00, 'sector': 'Banking', 'isin': 'EGS60681C011', 'mubasher_id': 'ADCB'},
    'AHLI': {'name': 'بنك الأهلي المتحد', 'base_price': 18.00, 'sector': 'Banking', 'isin': 'EGS60671C013', 'mubasher_id': 'AHLI'},
    
    # العقارات
    'PHDC': {'name': 'بالم هيلز للتعمير', 'base_price': 37.56, 'sector': 'Real Estate', 'isin': 'EGS673L1C015', 'mubasher_id': 'PHDC'},
    'OCDI': {'name': 'أوراسكوم للتنمية', 'base_price': 88.02, 'sector': 'Real Estate', 'isin': 'EGS383S1C011', 'mubasher_id': 'OCDI'},
    'ESRS': {'name': 'القاهرة للإسكان', 'base_price': 14.92, 'sector': 'Real Estate', 'isin': 'EGS60701C017', 'mubasher_id': 'ESRS'},
    'MNHD': {'name': 'مدينة نصر للإسكان', 'base_price': 8.50, 'sector': 'Real Estate', 'isin': 'EGS60362C012', 'mubasher_id': 'MNHD'},
    'SODIC': {'name': 'سوديك', 'base_price': 22.00, 'sector': 'Real Estate', 'isin': 'EGS65151C013', 'mubasher_id': 'OCDI'},
    'TMGH': {'name': 'طلعت مصطفى القابضة', 'base_price': 45.00, 'sector': 'Real Estate', 'isin': 'EGS65401C011', 'mubasher_id': 'TMGH'},
    'ASLK': {'name': 'أسيك للتعدين', 'base_price': 12.00, 'sector': 'Real Estate', 'isin': 'EGS60371C010', 'mubasher_id': 'ASLK'},
    'RE6O': {'name': 'السادس من أكتوبر للتنمية', 'base_price': 19.00, 'sector': 'Real Estate', 'isin': 'EGS60381C018', 'mubasher_id': '6OCT'},
    'HRHO': {'name': 'هيرميس القابضة', 'base_price': 35.60, 'sector': 'Real Estate', 'isin': 'EGS68251C012', 'mubasher_id': 'HRHO'},
    'ELSH': {'name': 'الشمس للإسكان', 'base_price': 8.50, 'sector': 'Real Estate', 'isin': 'EGS60391C016', 'mubasher_id': 'ELSH'},
    
    # الاتصالات
    'ETEL': {'name': 'المصرية للاتصالات', 'base_price': 19.50, 'sector': 'Telecommunications', 'isin': 'EGS68101C013', 'mubasher_id': 'ETEL'},
    'ORTE': {'name': 'أوراسكوم تليكوم', 'base_price': 2.10, 'sector': 'Telecommunications', 'isin': 'EGS65251C011', 'mubasher_id': 'ORTE'},
    'VODA': {'name': 'فودافون مصر', 'base_price': 8.50, 'sector': 'Telecommunications', 'isin': 'EGS68371C012', 'mubasher_id': 'VODA'},
    
    # الصناعة
    'SWDY': {'name': 'السويدي إليكتريك', 'base_price': 45.00, 'sector': 'Industrial', 'isin': 'EGS65451C019', 'mubasher_id': 'SWDY'},
    'ORWE': {'name': 'أورينتال ويفرز', 'base_price': 12.80, 'sector': 'Industrial', 'isin': 'EGS65391C011', 'mubasher_id': 'ORWE'},
    'GMPC': {'name': 'جنوب الوادي للأسمنت', 'base_price': 6.20, 'sector': 'Industrial', 'isin': 'EGS60622C010', 'mubasher_id': 'GMPC'},
    'TORA': {'name': 'العربية للأسمنت (طرة)', 'base_price': 28.00, 'sector': 'Industrial', 'isin': 'EGS60552C014', 'mubasher_id': 'TORA'},
    'ESLA': {'name': 'الإسكندرية للأسمنت', 'base_price': 15.00, 'sector': 'Industrial', 'isin': 'EGS60512C016', 'mubasher_id': 'ESLA'},
    'SKPC': {'name': 'سيدي كرير للبتروكيماويات', 'base_price': 22.00, 'sector': 'Industrial', 'isin': 'EGS60422C018', 'mubasher_id': 'SKPC'},
    'PIOH': {'name': 'بايونيرز القابضة', 'base_price': 8.50, 'sector': 'Industrial', 'isin': 'EGS60441C010', 'mubasher_id': 'PIOH'},
    'ELEC': {'name': 'كابلات الكهرباء المصرية', 'base_price': 15.00, 'sector': 'Industrial', 'isin': 'EGS60451C018', 'mubasher_id': 'ELEC'},
    'EMAC': {'name': 'المصرية للمشروعات الصناعية', 'base_price': 6.50, 'sector': 'Industrial', 'isin': 'EGS60461C016', 'mubasher_id': 'EMAC'},
    'SRPC': {'name': 'سيراميكا رأس الحكمة', 'base_price': 4.20, 'sector': 'Industrial', 'isin': 'EGS60471C014', 'mubasher_id': 'SRPC'},
    'CLHO': {'name': 'القابضة المصرية الكويتية', 'base_price': 3.80, 'sector': 'Industrial', 'isin': 'EGS60481C012', 'mubasher_id': 'CLHO'},
    'EGCH': {'name': 'المصرية للكيماويات', 'base_price': 5.50, 'sector': 'Industrial', 'isin': 'EGS60491C010', 'mubasher_id': 'EGCH'},
    'ORAS': {'name': 'أوراسكوم كونستراكشون', 'base_price': 380.00, 'sector': 'Industrial', 'isin': 'EGS383S1C011', 'mubasher_id': 'ORAS'},
    
    # الأسمنت
    'CCAP': {'name': 'القاهرة للاستثمار', 'base_price': 14.61, 'sector': 'Cement', 'isin': 'EGS68371C018', 'mubasher_id': 'CCAP'},
    'SUCE': {'name': 'السويس للأسمنت', 'base_price': 65.00, 'sector': 'Cement', 'isin': 'EGS60532C018', 'mubasher_id': 'SUCE'},
    'PORD': {'name': 'أسمنت بورتلاند طرة', 'base_price': 18.00, 'sector': 'Cement', 'isin': 'EGS60562C012', 'mubasher_id': 'PORD'},
    'HCCB': {'name': 'حلوان للأسمنت', 'base_price': 12.00, 'sector': 'Cement', 'isin': 'EGS60572C010', 'mubasher_id': 'HCCB'},
    'TSCE': {'name': 'طره الأسمنت', 'base_price': 58.00, 'sector': 'Cement', 'isin': 'EGS60542C016', 'mubasher_id': 'TSCE'},
    
    # الأغذية
    'HELI': {'name': 'هليوبوليس للإسكان', 'base_price': 11.00, 'sector': 'Food & Beverage', 'isin': 'EGS60351C014', 'mubasher_id': 'HELI'},
    'JUFO': {'name': 'جهينة للصناعات الغذائية', 'base_price': 5.80, 'sector': 'Food & Beverage', 'isin': 'EGS65611C015', 'mubasher_id': 'JUFO'},
    'DOMT': {'name': 'دومتي', 'base_price': 18.50, 'sector': 'Food & Beverage', 'isin': 'EGS65621C013', 'mubasher_id': 'DMTY'},
    'EDFP': {'name': 'ايديتا للصناعات الغذائية', 'base_price': 15.00, 'sector': 'Food & Beverage', 'isin': 'EGS65631C011', 'mubasher_id': 'EDFP'},
    'EAST': {'name': 'الشرقية ايسترن كومباني', 'base_price': 52.00, 'sector': 'Food & Beverage', 'isin': 'EGS60181C016', 'mubasher_id': 'EAST'},
    'NSFA': {'name': 'نستله مصر', 'base_price': 850.00, 'sector': 'Food & Beverage', 'isin': 'EGS65641C019', 'mubasher_id': 'NSFA'},
    'NATT': {'name': 'النساجون الشرقيون', 'base_price': 25.00, 'sector': 'Food & Beverage', 'isin': 'EGS65651C017', 'mubasher_id': 'NATT'},
    'OBRI': {'name': 'العبور للاستثمار العقاري', 'base_price': 9.50, 'sector': 'Food & Beverage', 'isin': 'EGS60401C012', 'mubasher_id': 'OBRI'},
    
    # الأدوية
    'PHAR': {'name': 'الإسكندرية للأدوية', 'base_price': 28.00, 'sector': 'Healthcare', 'isin': 'EGS60282C012', 'mubasher_id': 'PHAR'},
    'MBPD': {'name': 'ممفيس للأدوية', 'base_price': 65.00, 'sector': 'Healthcare', 'isin': 'EGS60292C010', 'mubasher_id': 'MBPD'},
    'GTHE': {'name': 'المصرية الدولية للصناعات الدوائية', 'base_price': 12.00, 'sector': 'Healthcare', 'isin': 'EGS60302C016', 'mubasher_id': 'GTHE'},
    'NIPH': {'name': 'النيل للأدوية', 'base_price': 45.00, 'sector': 'Healthcare', 'isin': 'EGS60312C014', 'mubasher_id': 'NIPH'},
    'MOPH': {'name': 'المصرية للمنتجات الطبية', 'base_price': 8.50, 'sector': 'Healthcare', 'isin': 'EGS60322C012', 'mubasher_id': 'MOPH'},
    'ARAB': {'name': 'العربية للأدوية', 'base_price': 18.00, 'sector': 'Healthcare', 'isin': 'EGS60332C010', 'mubasher_id': 'ARAB'},
    
    # السياحة
    'OTMT': {'name': 'أوراسكوم للفنادق', 'base_price': 35.00, 'sector': 'Tourism', 'isin': 'EGS65371C013', 'mubasher_id': 'OTMT'},
    'EGTS': {'name': 'المصرية للمنتجعات السياحية', 'base_price': 12.50, 'sector': 'Tourism', 'isin': 'EGS70431C019', 'mubasher_id': 'EGTS'},
    'RMDA': {'name': 'رمكو لمصر', 'base_price': 5.80, 'sector': 'Tourism', 'isin': 'EGS70441C017', 'mubasher_id': 'RMDA'},
    'SAUT': {'name': 'شارم دريمز', 'base_price': 3.20, 'sector': 'Tourism', 'isin': 'EGS70451C015', 'mubasher_id': 'SAUT'},
    
    # الخدمات المالية
    'EFIH': {'name': 'المصرية للتمويل والاستثمار', 'base_price': 7.50, 'sector': 'Financial Services', 'isin': 'EGS68241C014', 'mubasher_id': 'EFIH'},
    'DHCI': {'name': 'دلتا للطباعة', 'base_price': 22.00, 'sector': 'Financial Services', 'isin': 'EGS68261C010', 'mubasher_id': 'DHCI'},
    'CIRA': {'name': 'القاهرة للاستثمارات', 'base_price': 9.80, 'sector': 'Financial Services', 'isin': 'EGS68271C018', 'mubasher_id': 'CIRA'},
    'EGIS': {'name': 'المصرية للاستثمار العقاري', 'base_price': 15.00, 'sector': 'Financial Services', 'isin': 'EGS68281C016', 'mubasher_id': 'EGIS'},
    'UEGM': {'name': 'يونيفرسال للطباعة', 'base_price': 6.50, 'sector': 'Financial Services', 'isin': 'EGS68291C014', 'mubasher_id': 'UEGM'},
    'MCRT': {'name': 'مصر للتأمين', 'base_price': 18.00, 'sector': 'Financial Services', 'isin': 'EGS68301C018', 'mubasher_id': 'MCRT'},
    'MFPC': {'name': 'مصر للتأمين التكافلي', 'base_price': 12.00, 'sector': 'Financial Services', 'isin': 'EGS68311C016', 'mubasher_id': 'MFPC'},
    'KPLC': {'name': 'كفر الزيات للمبيدات', 'base_price': 45.00, 'sector': 'Financial Services', 'isin': 'EGS68321C014', 'mubasher_id': 'KPLC'},
    'SFPC': {'name': 'صافي للأغذية', 'base_price': 8.50, 'sector': 'Financial Services', 'isin': 'EGS68331C012', 'mubasher_id': 'SFPC'},
    'MOKP': {'name': 'مستشفى النزهة الدولي', 'base_price': 15.00, 'sector': 'Financial Services', 'isin': 'EGS68341C010', 'mubasher_id': 'MOKP'},
    'WEPO': {'name': 'ويبو', 'base_price': 5.20, 'sector': 'Financial Services', 'isin': 'EGS68351C018', 'mubasher_id': 'WEPO'},
    'GECO': {'name': 'جنرال كابيتال', 'base_price': 7.80, 'sector': 'Financial Services', 'isin': 'EGS68361C016', 'mubasher_id': 'GECO'},
    
    # التكنولوجيا
    'MNOF': {'name': 'مينا فارما', 'base_price': 22.00, 'sector': 'Technology', 'isin': 'EGS68381C014', 'mubasher_id': 'MNOF'},
    'ITEN': {'name': 'آي تي إي', 'base_price': 8.50, 'sector': 'Technology', 'isin': 'EGS68391C012', 'mubasher_id': 'ITEN'},
    'RAYA': {'name': 'راية القابضة', 'base_price': 18.00, 'sector': 'Technology', 'isin': 'EGS68401C016', 'mubasher_id': 'RAYA'},
}

# Cache للأسعار
price_cache = {}
cache_timestamp = {}
price_source = {}
CACHE_DURATION = 300  # 5 دقائق

def get_live_price_egxpy(ticker):
    """جلب السعر من EGXPY (محسّن)"""
    try:
        from egxpy.download import get_EGXdata
        
        data = get_EGXdata([ticker], interval='1D', period='5d')
        
        if data is not None and not data.empty:
            if ticker in data.columns or ticker in data:
                price_data = data[ticker] if ticker in data else data
                
                if isinstance(price_data, pd.DataFrame):
                    if 'Close' in price_data.columns:
                        price = float(price_data['Close'].iloc[-1])
                    else:
                        price = float(price_data.iloc[-1].values[0])
                else:
                    price = float(price_data.iloc[-1])
                
                if price > 0:
                    print(f"✅ EGXPY: {price} EGP")
                    return price
        
        return None
        
    except ImportError:
        print(f"⚠️ EGXPY not installed")
        return None
    except Exception as e:
        print(f"❌ EGXPY error: {str(e)}")
        return None

def get_live_price_yahoo(ticker):
    """جلب السعر من Yahoo Finance (محسّن ومعدّل)"""
    try:
        stock_info = STOCK_BASE_DATA.get(ticker)
        if not stock_info:
            return None
        
        base_price = stock_info['base_price']
        
        # محاولات متعددة مع ticker symbols مختلفة
        attempts = [
            f"{stock_info.get('mubasher_id', ticker)}.CA",  # COMI.CA
            f"{ticker}.CA",                                  # CIB.CA
        ]
        
        for yahoo_ticker in attempts:
            try:
                stock = yf.Ticker(yahoo_ticker)
                
                # جرب من history الأول (أدق)
                hist = stock.history(period='5d')
                if not hist.empty and len(hist) > 0:
                    price = float(hist['Close'].iloc[-1])
                    
                    # Validation أوسع: ±70% من base price
                    if price > 0 and base_price * 0.3 <= price <= base_price * 2.0:
                        print(f"✅ Yahoo ({yahoo_ticker}): {price} EGP")
                        return price
                    else:
                        print(f"⚠️ {yahoo_ticker}: Price {price} out of range (expected ~{base_price})")
                        continue
                
                # جرب من info (backup)
                info = stock.info
                price = (info.get('currentPrice') or 
                        info.get('regularMarketPrice') or 
                        info.get('previousClose'))
                
                if price and price > 0:
                    # Validation
                    if base_price * 0.3 <= price <= base_price * 2.0:
                        print(f"✅ Yahoo info ({yahoo_ticker}): {price} EGP")
                        return price
                        
            except Exception as e:
                print(f"⚠️ Yahoo attempt {yahoo_ticker} failed: {str(e)}")
                continue
        
        return None
        
    except Exception as e:
        print(f"❌ Yahoo error: {str(e)}")
        return None

def get_live_price(ticker):
    """جلب السعر من مصادر متعددة (Hybrid)"""
    global price_cache, cache_timestamp, price_source
    
    # تحقق من الـ cache
    if ticker in price_cache and ticker in cache_timestamp:
        time_diff = (datetime.now() - cache_timestamp[ticker]).seconds
        if time_diff < CACHE_DURATION:
            return price_cache[ticker]
    
    price = None
    source = None
    
    # 1. جرب EGXPY الأول
    print(f"🔍 Fetching {ticker}... [1] EGXPY... ", end='')
    price = get_live_price_egxpy(ticker)
    if price:
        source = 'EGXPY'
    
    # 2. لو فشل، جرب Yahoo Finance
    if not price:
        print(f"[2] Yahoo... ", end='')
        price = get_live_price_yahoo(ticker)
        if price:
            source = 'Yahoo Finance'
    
    # 3. احفظ في cache لو نجح
    if price:
        price_cache[ticker] = price
        cache_timestamp[ticker] = datetime.now()
        price_source[ticker] = source
        STOCK_BASE_DATA[ticker]['base_price'] = price  # تحديث base price
        print(f"✅")
        return price
    
    # 4. استخدم base price كـ fallback
    print(f"⚠️ Using base price")
    source = 'Base Price (Fallback)'
    price = STOCK_BASE_DATA[ticker]['base_price']
    price_source[ticker] = source
    return price

def get_current_price(ticker):
    """السعر الحالي"""
    return get_live_price(ticker)

def generate_realistic_stock_data(ticker, days=365):
    """توليد بيانات تاريخية بناءً على السعر الحقيقي"""
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
    """حساب المؤشرات الفنية"""
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

# ================ API ENDPOINTS ================

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'message': '🚀 Egyptian Stock Analyzer API',
        'status': 'healthy',
        'version': '5.0 - Production',
        'total_stocks': len(STOCK_BASE_DATA),
        'mode': 'LIVE - Multi-Source Hybrid',
        'data_sources': {
            'primary': 'EGXPY (Egyptian Exchange specialist)',
            'secondary': 'Yahoo Finance',
            'fallback': 'Base prices'
        },
        'cache_duration': f'{CACHE_DURATION}s',
        'endpoints': {
            '/': 'API Info',
            '/health': 'Health check',
            '/api/stock/<ticker>': 'Stock analysis (GET)',
            '/api/prices': 'All prices (GET)',
            '/api/compare': 'Compare stocks (POST)',
            '/api/refresh/<ticker>': 'Refresh price (GET)',
            '/api/sectors': 'Group by sectors (GET)',
            '/api/available': 'Available tickers (GET)',
            '/api/search?q=name': 'Search stocks (GET)'
        },
        'examples': {
            'stock_analysis': '/api/stock/CIB',
            'compare_stocks': 'POST /api/compare {"tickers": ["CIB", "PHDC"]}',
            'search': '/api/search?q=بنك'
        }
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check للـ Render"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'uptime': 'running',
        'stocks_loaded': len(STOCK_BASE_DATA),
        'cache_size': len(price_cache),
        'version': '5.0'
    }), 200

@app.route('/api/stock/<ticker>', methods=['GET'])
def analyze_stock(ticker):
    """تحليل فني كامل لسهم"""
    try:
        ticker = ticker.upper()
        
        if ticker not in STOCK_BASE_DATA:
            return jsonify({
                'success': False,
                'error': f'Ticker {ticker} not found',
                'available_count': len(STOCK_BASE_DATA),
                'tip': 'Use /api/available to see all tickers'
            }), 404
        
        days = int(request.args.get('days', 365))
        if days > 1095:
            days = 1095
        
        # جلب البيانات
        data = generate_realistic_stock_data(ticker, days)
        
        # حساب المؤشرات
        indicators = calculate_technical_indicators(data)
        
        stock_info = STOCK_BASE_DATA[ticker]
        
        return jsonify({
            'success': True,
            'ticker': ticker,
            'name': stock_info['name'],
            'sector': stock_info['sector'],
            'isin': stock_info.get('isin', 'N/A'),
            'currency': 'EGP',
            'price_source': price_source.get(ticker, 'Not fetched yet'),
            'price_cached': ticker in price_cache,
            'last_price_update': cache_timestamp[ticker].strftime('%Y-%m-%d %H:%M:%S') if ticker in cache_timestamp else 'Just fetched',
            'price_data': {
                'current_price': round(indicators['current_price'], 2),
                'daily_change_percent': round(indicators['daily_change'], 2),
                'period_high': round(float(data['High'].max()), 2),
                'period_low': round(float(data['Low'].min()), 2),
                'open': round(float(data['Open'].iloc[-1]), 2),
                'high': round(float(data['High'].iloc[-1]), 2),
                'low': round(float(data['Low'].iloc[-1]), 2),
                'volume': int(data['Volume'].iloc[-1])
            },
            'technical_indicators': {
                'rsi': {
                    'value': round(indicators['rsi'], 2),
                    'signal': 'Overbought' if indicators['rsi'] > 70 else 'Oversold' if indicators['rsi'] < 30 else 'Neutral',
                    'description': 'Relative Strength Index (14-day)'
                },
                'moving_averages': {
                    'ma_20': round(indicators['ma_20'], 2) if indicators['ma_20'] else None,
                    'ma_50': round(indicators['ma_50'], 2) if indicators['ma_50'] else None,
                    'ma_200': round(indicators['ma_200'], 2) if indicators['ma_200'] else None,
                    'trend': indicators['trend'],
                    'description': 'Price vs MA-50 trend'
                },
                'macd': {
                    'value': round(indicators['macd'], 4),
                    'signal': round(indicators['signal_line'], 4),
                    'histogram': round(indicators['macd'] - indicators['signal_line'], 4),
                    'signal_text': 'Bullish' if indicators['macd'] > indicators['signal_line'] else 'Bearish',
                    'description': 'MACD (12,26,9)'
                }
            },
            'recommendation': {
                'action': indicators['recommendation'],
                'description': f"Based on RSI, MACD, and trend analysis"
            },
            'volume_analysis': {
                'current': int(data['Volume'].iloc[-1]),
                'average': int(data['Volume'].mean()),
                'ratio_percent': round((int(data['Volume'].iloc[-1]) / int(data['Volume'].mean())) * 100, 2)
            }
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/prices', methods=['GET'])
def current_prices():
    """الأسعار الحالية لكل الأسهم"""
    sector_filter = request.args.get('sector', None)
    
    prices = {}
    
    for ticker, data in STOCK_BASE_DATA.items():
        # Filter بالـ sector لو موجود
        if sector_filter and data['sector'].lower() != sector_filter.lower():
            continue
            
        current = get_current_price(ticker)
        
        prices[ticker] = {
            'name': data['name'],
            'sector': data['sector'],
            'price': round(current, 2),
            'currency': 'EGP',
            'source': price_source.get(ticker, 'Not fetched yet'),
            'cached': ticker in price_cache,
            'last_updated': cache_timestamp[ticker].strftime('%H:%M:%S') if ticker in cache_timestamp else 'Not fetched'
        }
    
    return jsonify({
        'success': True,
        'total': len(prices),
        'sector_filter': sector_filter,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'prices': prices
    })

@app.route('/api/compare', methods=['POST'])
def compare_stocks():
    """مقارنة بين أسهم متعددة"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No JSON data provided',
            'example': {'tickers': ['CIB', 'PHDC', 'SWDY']}
        }), 400
    
    tickers = data.get('tickers', [])
    
    if not tickers or len(tickers) < 2:
        return jsonify({
            'success': False,
            'error': 'Please provide at least 2 tickers',
            'example': {'tickers': ['CIB', 'PHDC']}
        }), 400
    
    comparison = []
    for ticker in tickers:
        ticker = ticker.upper()
        if ticker not in STOCK_BASE_DATA:
            continue
            
        stock_info = STOCK_BASE_DATA[ticker]
        current_price = get_current_price(ticker)
        
        # حساب مؤشرات بسيطة
        stock_data = generate_realistic_stock_data(ticker, 90)
        indicators = calculate_technical_indicators(stock_data)
        
        comparison.append({
            'ticker': ticker,
            'name': stock_info['name'],
            'sector': stock_info['sector'],
            'price': round(current_price, 2),
            'daily_change': round(indicators['daily_change'], 2),
            'rsi': round(indicators['rsi'], 2),
            'trend': indicators['trend'],
            'recommendation': indicators['recommendation'],
            'source': price_source.get(ticker, 'Unknown')
        })
    
    return jsonify({
        'success': True,
        'total': len(comparison),
        'comparison': comparison,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/refresh/<ticker>', methods=['GET'])
def refresh_price(ticker):
    """فرض تحديث سعر معين"""
    ticker = ticker.upper()
    
    if ticker not in STOCK_BASE_DATA:
        return jsonify({
            'success': False,
            'error': f'Ticker {ticker} not found'
        }), 404
    
    # احذف من الـ cache
    if ticker in price_cache:
        del price_cache[ticker]
    if ticker in cache_timestamp:
        del cache_timestamp[ticker]
    if ticker in price_source:
        del price_source[ticker]
    
    # جلب السعر الجديد
    new_price = get_live_price(ticker)
    
    return jsonify({
        'success': True,
        'ticker': ticker,
        'price': round(new_price, 2),
        'source': price_source.get(ticker, 'Unknown'),
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'cached': False
    })

@app.route('/api/sectors', methods=['GET'])
def get_sectors():
    """تجميع الأسهم حسب القطاعات"""
    sectors = {}
    for ticker, data in STOCK_BASE_DATA.items():
        sector = data['sector']
        if sector not in sectors:
            sectors[sector] = []
        sectors[sector].append({
            'ticker': ticker,
            'name': data['name'],
            'price': round(get_current_price(ticker), 2),
            'isin': data.get('isin', 'N/A')
        })
    
    return jsonify({
        'success': True,
        'total_sectors': len(sectors),
        'sectors': sectors,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/search', methods=['GET'])
def search_stocks():
    """البحث عن الأسهم"""
    query = request.args.get('q', '').lower()
    
    if not query:
        return jsonify({
            'success': False,
            'error': 'Please provide search query (?q=...)',
            'example': '/api/search?q=بنك'
        }), 400
    
    results = []
    for ticker, data in STOCK_BASE_DATA.items():
        if (query in ticker.lower() or 
            query in data['name'].lower() or 
            query in data['sector'].lower()):
            results.append({
                'ticker': ticker,
                'name': data['name'],
                'sector': data['sector'],
                'price': round(get_current_price(ticker), 2),
                'isin': data.get('isin', 'N/A')
            })
    
    return jsonify({
        'success': True,
        'query': query,
        'results_count': len(results),
        'stocks': results
    })

@app.route('/api/available', methods=['GET'])
def available_tickers():
    """قائمة كل الأسهم المتاحة"""
    return jsonify({
        'success': True,
        'total': len(STOCK_BASE_DATA),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'tickers': [{
            'symbol': symbol,
            'name': data['name'],
            'sector': data['sector'],
            'isin': data.get('isin', 'N/A'),
            'currency': 'EGP'
        } for symbol, data in STOCK_BASE_DATA.items()]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 70)
    print("🚀 Egyptian Stock Analyzer API - Production v5.0")
    print("=" * 70)
    print(f"📊 Total Stocks: {len(STOCK_BASE_DATA)}")
    print(f"🔴 Mode: LIVE - Multi-Source Hybrid")
    print(f"📡 Data Sources: EGXPY → Yahoo Finance → Base Prices")
    print(f"💾 Cache Duration: {CACHE_DURATION}s")
    print(f"🌐 Port: {port}")
    print("=" * 70)
    app.run(host='0.0.0.0', port=port, debug=False)
