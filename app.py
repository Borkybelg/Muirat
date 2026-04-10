import streamlit as st
import pandas as pd
import yfinance as yf
import os
import requests
import streamlit.components.v1 as components
import streamlit as st
import requests
import feedparser # Falls Fehlermeldung: im Terminal 'pip install feedparser' eingeben

def calculate_stochastic(df, k_window=14, d_window=3, overbought=90, oversold=10):
    if len(df) < k_window + d_window:
        return {"k": 50, "d": 50, "signal": "WAIT 🟡"}

    # Höchst- und Tiefststände der letzten n Tage
    low_min = df['Low'].rolling(window=k_window).min()
    high_max = df['High'].rolling(window=k_window).max()

    # %K Berechnung
    df['%K'] = 100 * ((df['Close'] - low_min) / (high_max - low_min + 1e-9))
    # %D Berechnung (Durchschnitt von %K)
    df['%D'] = df['%K'].rolling(window=d_window).mean()

    last_k = df['%K'].iloc[-1]
    last_d = df['%D'].iloc[-1]
    prev_k = df['%K'].iloc[-2]
    prev_d = df['%D'].iloc[-2]

    # Signal-Logik für 90/10
    signal = "WAIT 🟡"
    
    # LONG: Kreuzung von unten nach oben IM überverkauften Bereich (< 10)
    if last_k > last_d and prev_k <= prev_d and last_k <= oversold:
        signal = "STRONG LONG 🚀"
    
    # SHORT: Kreuzung von oben nach unten IM überkauften Bereich (> 90)
    elif last_k < last_d and prev_k >= prev_d and last_k >= overbought:
        signal = "STRONG SHORT 💀"
        
    return {"k": last_k, "d": last_d, "signal": signal}
def calculate_signals(df):
    # Alles hier drunter muss eingerückt sein!
    if len(df) < 30: 
        return {"rsi": 50, "ema20": 0, "trend": "Neutral", "cvd": 0, "oi": 0, "sentiment": "Neutral"}
    
    # RSI Berechnung nach TradingView Standard
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    
    rs = avg_gain / (avg_loss + 1e-9)
    rsi_series = 100 - (100 / (1 + rs))
    last_rsi = rsi_series.iloc[-1]
    
    ema20 = df['Close'].ewm(span=20, adjust=False).mean()
    last_ema = ema20.iloc[-1]
    last_p = df['Close'].iloc[-1]
    
    vol_delta = (df['Close'] - df['Open']) / (df['High'] - df['Low'] + 1e-9) * df['Volume']
    cvd_val = vol_delta.rolling(window=20).sum().iloc[-1]
    
    if last_p > last_ema and last_rsi < 70: 
        trend = "LONG 🟢"
    elif last_p < last_ema and last_rsi > 30: 
        trend = "SHORT 🔴"
    else: 
        trend = "WAIT 🟡"
    
    return {
        "rsi": last_rsi, 
        "ema20": last_ema, 
        "trend": trend, 
        "cvd": cvd_val, 
        "sentiment": "BULLISH 🚀" if last_rsi > 50 else "BEARISH 📉"
    }
def get_free_crypto_news():
    # Wir mischen die Feeds von CoinTelegraph und CoinDesk
    feeds = [
        "https://cointelegraph.com/rss/tag/bitcoin",
        "https://www.coindesk.com/arc/outboundfeeds/rss/"
    ]
    all_news = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]: # Die neuesten 3 pro Seite
                all_news.append({
                    "title": entry.title,
                    "link": entry.link,
                    "source": "CoinDesk" if "coindesk" in url else "CoinTelegraph"
                })
        except:
            continue
    return all_news

def get_crypto_panic_news():
    # Ohne Key nutzen wir den öffentlichen RSS-Feed/API-Endpoint, der manchmal begrenzt ist
    # Hol dir am besten einen kostenlosen Key auf cryptopanic.com
    api_key = "DEIN_KEY_HIER" 
    url = f"https://cryptopanic.com/api/v1/posts/?auth_token={api_key}&public=true&kind=news"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        return data.get('results', [])
    except:
        return []
def get_yahoo_news_safe(ticker="^GDAXI"):
    try:
        t = yf.Ticker(ticker)
        news = t.news
        if not news:
            news = yf.Ticker("^GDAXI").news
        return news
    except:
        return []

# Das hier ist der "Alias", damit beide Namen funktionieren:
get_yahoo_news = get_yahoo_news_safe 

def get_crypto_panic_news(api_key="DEIN_API_KEY"):
    url = f"https://cryptopanic.com/api/v1/posts/?auth_token={api_key}&public=true"
    try:
        r = requests.get(url, timeout=5)
        return r.json().get('results', [])
    except:
        return []


# Wechselkurse 1 Stunde lang speichern (spart pro Klick ca. 5-8 Sekunden)
@st.cache_data(ttl=3600)
def get_fx_rate_cached(from_curr, to_curr):
    if not from_curr or from_curr == to_curr: return 1.0
    try:
        pair = f"{from_curr}{to_curr}=X"
        return yf.Ticker(pair).fast_info.last_price
    except: return 1.0

# Preise 2 Minuten lang speichern
@st.cache_data(ttl=120)
def get_batch_prices(ticker_list):
    if not ticker_list: return {}
    data = yf.download(ticker_list, period="5d", interval="1d", progress=False)
    prices = {}
    if not data.empty:
        for t in ticker_list:
            try:
                # Schneller Zugriff auf die letzte Close-Spalte
                series = data['Close'][t].dropna() if len(ticker_list) > 1 else data['Close'].dropna()
                prices[t] = series.iloc[-1]
            except: prices[t] = None
    return prices

# --- 0. KONFIGURATION & SPEICHERUNG ---
st.set_page_config(page_title="Investment Center Pro 2026", layout="wide")

filename = "portfolio.csv"
chart_config_file = "charts_config.csv"
signal_watchlist_file = "signals_watchlist.csv"

# --- 1. TECHNISCHE FUNKTIONEN (RSI, EMA, FX) ---
def calculate_signals(df):
    if len(df) < 30: 
        return {"rsi": 50, "stoch_k": 50, "stoch_d": 50, "trend": "WAIT 🟡", "sentiment": "Neutral", "cvd": 0}
    
    # --- RSI BERECHNUNG ---
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    rsi_series = 100 - (100 / (1 + rs))
    last_rsi = rsi_series.iloc[-1]

    # --- STOCHASTIK BERECHNUNG (90/10) ---
    low_14 = df['Low'].rolling(window=14).min()
    high_14 = df['High'].rolling(window=14).max()
    df['%K'] = 100 * ((df['Close'] - low_14) / (high_14 - low_14 + 1e-9))
    df['%D'] = df['%K'].rolling(window=3).mean()
    
    last_k, last_d = df['%K'].iloc[-1], df['%D'].iloc[-1]
    prev_k, prev_d = df['%K'].iloc[-2], df['%D'].iloc[-2]

    # --- EMA & VOLUMEN (CVD) ---
    ema20 = df['Close'].ewm(span=20, adjust=False).mean()
    last_ema = ema20.iloc[-1]
    last_p = df['Close'].iloc[-1]
    vol_delta = (df['Close'] - df['Open']) / (df['High'] - df['Low'] + 1e-9) * df['Volume']
    cvd_val = vol_delta.rolling(window=20).sum().iloc[-1]

    # --- KOMBINIERTE LOGIK ---
    trend = "WAIT 🟡"
    # LONG: Stochastik Kreuzung unten (<10) + RSI niedrig
    if last_k > last_d and prev_k <= prev_d and last_k <= 10:
        trend = "STRONG LONG 🚀" if last_rsi < 40 else "LONG 🟢"
    # SHORT: Stochastik Kreuzung oben (>90) + RSI hoch
    elif last_k < last_d and prev_k >= prev_d and last_k >= 90:
        trend = "STRONG SHORT 💀" if last_rsi > 60 else "SHORT 🔴"
    # Fallback auf EMA Trend, wenn keine Stoch-Kreuzung vorliegt
    elif last_p > last_ema:
        trend = "TREND UP 📈"
    elif last_p < last_ema:
        trend = "TREND DOWN 📉"

    return {
        "rsi": last_rsi, 
        "stoch_k": last_k,
        "stoch_d": last_d,
        "trend": trend, 
        "cvd": cvd_val, 
        "sentiment": "BULLISH 🚀" if last_rsi > 50 else "BEARISH 📉"
    }

def get_sector_performance():
    sectors = {
        "Technology (XLK)": "XLK",
        "Energy (XLE)": "XLE",
        "Health Care (XLV)": "XLV",
        "Financials (XLF)": "XLF",
        "Communication (XLC)": "XLC",
        "Consumer Disc. (XLY)": "XLY",
        "Industrials (XLI)": "XLI",
        "Semiconductors (SOXX)": "SOXX"
    }
    
    sec_results = []
    try:
        # Batch Download für alle Sektoren-ETFs
        sec_data = yf.download(list(sectors.values()), period="5d", interval="1d", progress=False)['Close']
        
        for name, ticker in sectors.items():
            if ticker in sec_data.columns:
                series = sec_data[ticker].dropna()
                if len(series) > 1:
                    perf = ((series.iloc[-1] / series.iloc[0]) - 1) * 100
                    sec_results.append({"Sektor": name, "Trend %": round(perf, 2)})
    except Exception as e:
        st.error(f"Sektor-Fehler: {e}")
        
    return pd.DataFrame(sec_results)
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    rsi = 100 - (100 / (1 + rs))
    ema20 = df['Close'].ewm(span=20, adjust=False).mean()
    
    # CVD & OI Proxy
    vol_delta = (df['Close'] - df['Open']) / (df['High'] - df['Low'] + 1e-9) * df['Volume']
    cvd = vol_delta.rolling(window=20).sum().iloc[-1]
    oi_proxy = (df['Close'] * df['Volume']).rolling(window=20).mean().iloc[-1]
    
    last_p, last_rsi, last_ema20 = df['Close'].iloc[-1], rsi.iloc[-1], ema20.iloc[-1]
    
    # Sentiment & Trend
    bull_score = 0
    if last_p > last_ema20: bull_score += 1
    if last_rsi < 60: bull_score += 1
    if cvd > 0: bull_score += 1
    sentiment = "BULLISH 🐂" if bull_score >= 2 else "BEARISH 🐻"
    
    if last_p > last_ema20 and last_rsi < 70: trend = "LONG 🟢"
    elif last_p < last_ema20 and last_rsi > 30: trend = "SHORT 🔴"
    else: trend = "WAIT 🟡"
    
    return {"rsi": last_rsi, "ema20": last_ema20, "trend": trend, "cvd": cvd, "oi": oi_proxy, "sentiment": sentiment}

@st.cache_data(ttl=300)
def get_fx_rate(from_curr, to_curr):
    """Holt den Wechselkurs für ALLE Währungen (auch IDR, HKD, JPY)"""
    if not from_curr or from_curr == to_curr: return 1.0
    # Bereinigung von Yahoo-Sonderbezeichnungen
    from_curr = str(from_curr).replace("ILA", "ILS").replace("GBp", "GBP")
    try:
        pair = f"{from_curr}{to_curr}=X"
        rate = yf.Ticker(pair).fast_info.last_price
        return rate if rate else 1.0
    except:
        return 1.0

def get_live_data(ticker):
    try:
        t = yf.Ticker(ticker)
        # Wir nutzen fast_info, da es viel schneller ist als t.info
        fast = t.fast_info
        return {
            "price": fast.last_price, 
            "currency": fast.currency, 
            "name": ticker # Name weglassen spart Zeit (keine extra API-Abfrage)
        }
    except:
        return None
# --- 2. SIDEBAR (SENTIMENT & SETUP) ---
with st.sidebar:
    st.header("⚙️ Steuerung")
    base_currency = st.radio("Basis-Währung:", ["EUR", "USD"])
    st.divider()
    st.subheader("⏱️ Signal-Intervall")
    tf = st.selectbox("Timeframe:", ["5m", "30m", "1h", "4h", "8h", "12h", "1d"], index=6)
    st.divider()
    st.subheader("🌡️ Markt-Sentiment")
    try:
        r = requests.get("https://api.alternative.me/fng/").json()
        fng = r['data'][0]['value']
        st.metric("Fear & Greed", f"{fng}/100", r['data'][0]['value_classification'])
        st.progress(int(fng)/100)
    except: st.write("Sentiment N/A")
    st.divider()
    num_charts = st.slider("Anzahl Charts", 1, 16, 4)
    cols_layout = st.select_slider("Spalten", [1, 2, 3, 4], 2)

# --- 3. PASSWORT ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False
if not st.session_state["password_correct"]:
    pwd = st.text_input("Sicherheitscode:", type="password")
    if st.button("Anmelden") or (pwd.lower() == "pa"):
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

st.subheader("📊 Global Market Watch")

m_tickers = {
    "DAX": "^GDAXI", "S&P 500": "^GSPC", "Nasdaq": "^NDX", "Dow Jones": "^DJI", "Kospi": "KOSPI-3.KS" ,
    "SDAX": "^SDAXI",  "MDAX": "^MDAXI", "TecDAX": "^TECDAX", "Russell 2k": "^RUT", 
    "Nikkei 225": "^N225",  "CSI300 ": "000300.SS", "BTC-USD": "BTC-USD", "ETH-USD": "ETH-USD", "ETH-EUR": "ETH-EUR", 
    "Gold": "GC=F", "Silber": "SI=F", "BRENT": "BZ=F", "VIX": "^VIX", "EUR/TRY": "EURTRY=X", "EUR/USD": "EURUSD=X", "RINF": "RINF",  "MOVE": "^MOVE3M", "EXY": "^129992-USD-CURW", "DXY": "DX-Y.NYB",
}

m_cols = st.columns(8)

for i, (n, s) in enumerate(m_tickers.items()):
    try:
        ticker = yf.Ticker(s)
        info = ticker.fast_info
        cp = info.last_price
        pc = info.previous_close
        
        # --- NACHKOMMASTELLEN-LOGIK ---
        # Wenn es eine Währung (=X) oder der Dollar Index (DX) ist -> 4 Stellen
        if "=X" in s or "DX" in s:
            precision = ".4f"
        else:
            precision = ".2f"
        
        # Prozentuale Änderung berechnen
        delta_val = None
        if pc and cp:
            pct = ((cp - pc) / pc) * 100
            delta_val = f"{pct:+.2f}%"

        # Anzeige mit der gewählten Präzision
        m_cols[i % 8].metric(
            label=n, 
            value=f"{cp:{precision}}", # Hier wird dynamisch .2f oder .4f genutzt
            delta=delta_val
        )
    except: 
        m_cols[i % 8].metric(n, "Err")

t_port, t_sig, t_multi, t_sec = st.tabs(["💰 PORTFOLIO", "🚦 SIGNAL MONITOR", "🖼️ TERMINAL", "📈 SEKTOREN"])

# --- TAB 1: PORTFOLIO (UPDATE: 1H, 24H & EK ANZEIGE) ---
with t_port:
    st.subheader("🔍 Neues Asset suchen & Portfolio erweitern")
    with st.expander("➕ Asset-Eingabemaske", expanded=False):
        with st.form("quick_add"):
            c1, c2, c3, c4, c5 = st.columns([1.5, 1, 1, 1, 1])
            ntick = c1.text_input("Ticker (z.B. AAPL, BTC-USD)")
            nname = c2.text_input("Name (optional)")
            nqty = c3.number_input("Menge", format="%.4f")
            nek = c4.number_input("EK (Lokalwährung)", format="%.2f")
            ncat = c5.selectbox("Typ", ["Aktie", "Krypto", "ETF"])
            if st.form_submit_button("➕ Hinzufügen"):
                # Erweitertes get_live_data wird hier genutzt
                t_info = yf.Ticker(ntick)
                try:
                    hist = t_info.history(period="2d")
                    cp = hist['Close'].iloc[-1]
                    curr = t_info.fast_info.currency
                    fname = nname if nname else ntick.upper()
                    nrow = pd.DataFrame([{"ticker":ntick.upper(),"name":fname,"menge":nqty,"kaufpreis":nek,"typ":ncat,"curr":curr}])
                    if os.path.exists(filename):
                        pd.concat([pd.read_csv(filename), nrow]).to_csv(filename, index=False)
                    else: nrow.to_csv(filename, index=False)
                    st.success(f"{fname} hinzugefügt!"); st.rerun()
                except: st.error("Ticker nicht gefunden!")

    if os.path.exists(filename):
        df = pd.read_csv(filename).dropna(subset=['ticker'])
        if not df.empty:
            results = []
            for idx, row in df.iterrows():
                try:
                    t = yf.Ticker(row['ticker'])
                    # Wir holen die Daten
                    hist = t.history(period="2d", interval="1h")
                    if not hist.empty:
                        cp = hist['Close'].iloc[-1]
                        
                        # --- WÄHRUNGS-FIX ---
                        # Wir schauen, was yfinance als Währung für diesen Ticker meldet
                        asset_curr = t.fast_info.currency 
                        
                        # Falls yfinance nichts liefert, nehmen wir den Wert aus der CSV
                        if not asset_curr:
                            asset_curr = row.get('curr', base_currency)
                        
                        # WICHTIG: Nur umrechnen, wenn die Währungen unterschiedlich sind!
                        if asset_curr.upper() == base_currency.upper():
                            rate = 1.0
                        else:
                            rate = get_fx_rate(asset_curr, base_currency)
                        
                        # Berechnung der Werte in Basiswährung
                        val_base = row['menge'] * cp * rate
                        inv_base = row['menge'] * row['kaufpreis'] * rate
                        
                        # Performance-Daten
                        change_24h = ((cp / hist['Close'].iloc[0]) - 1) * 100 if len(hist) > 1 else 0
                        change_1h = ((cp / hist['Close'].iloc[-2]) - 1) * 100 if len(hist) > 1 else 0
                        
                        results.append({
                            **row, 
                            "Wert": val_base, 
                            "Invest": inv_base, 
                            "GV": val_base - inv_base, 
                            "ch1h": change_1h,
                            "ch24h": change_24h,
                            "orig_idx": idx
                        })
                except Exception as e:
                    print(f"Fehler bei {row['ticker']}: {e}")
                    continue

            if results:
                rdf = pd.DataFrame(results)
                total_v = rdf['Wert'].sum()
                total_gv = rdf['GV'].sum()
                total_inv = rdf['Invest'].sum()
                total_p = (total_gv / total_inv * 100) if total_inv > 0 else 0
                
                st.metric(f"🏦 GESAMTDEPOT ({base_currency})", f"{total_v:,.2f}", f"{total_p:+.2f}% ({total_gv:,.2f})")
                st.divider()

                # --- ASSET LISTEN ---
                for k in ["Aktie", "Krypto", "ETF"]:
                    sub = rdf[rdf['typ'] == k]
                    if not sub.empty:
                        s_wert = sub['Wert'].sum()
                        s_gv = sub['GV'].sum()
                        with st.expander(f"📦 {k}s (Summe: {s_wert:,.2f} | G/V: {s_gv:+.2f})", expanded=True):
                            # Spalten-Layout angepasst für 1h und 24h
                            h1, h2, h3, h4, h5, h6, h7 = st.columns([2, 1.2, 1.2, 0.8, 0.8, 0.8, 1.2])
                            h1.caption("NAME / EK")
                            h2.caption(f"WERT ({base_currency})")
                            h3.caption("G/V")
                            h4.caption("1H %")
                            h5.caption("24H %")
                            h6.caption("MENGE")
                            h7.caption("AKTION")

                            for _, r in sub.iterrows():
                                c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 1.2, 1.2, 0.8, 0.8, 0.8, 1.2])
                                
                                # Spalte 1: Name und EK (Kaufpreis)
                                c1.markdown(f"**{r['name']}**\n<small>EK: {r['kaufpreis']:,.2f}</small>", unsafe_allow_html=True)
                                
                                # Spalte 2: Aktueller Wert
                                c2.write(f"{r['Wert']:,.2f}")
                                
                                # Spalte 3: G/V
                                color_gv = "green" if r['GV'] >= 0 else "red"
                                c3.markdown(f"<span style='color:{color_gv}; font-weight:bold;'>{r['GV']:+.2f}</span>", unsafe_allow_html=True)
                                
                                # Spalte 4: 1H %
                                c4_col = "#00FF00" if r['ch1h'] >= 0 else "#FF4B4B"
                                c4.markdown(f"<span style='color:{c4_col};'>{r['ch1h']:+.2f}%</span>", unsafe_allow_html=True)
                                
                                # Spalte 5: 24H %
                                c5_col = "#00FF00" if r['ch24h'] >= 0 else "#FF4B4B"
                                c5.markdown(f"<span style='color:{c5_col};'>{r['ch24h']:+.2f}%</span>", unsafe_allow_html=True)
                                
                                # Spalte 6: Menge
                                c6.write(f"{r['menge']}")
                                
                                # Spalte 7: Aktionen
                                with c7:
                                    col_edit, col_sell, col_del = st.columns(3)
                                    with col_edit:
                                        with st.popover("📝"):
                                            with st.form(f"ed_{r['orig_idx']}"):
                                                en = st.text_input("Name", r['name'])
                                                em = st.number_input("Menge", float(r['menge']))
                                                ee = st.number_input("EK", float(r['kaufpreis']))
                                                if st.form_submit_button("Speichern"):
                                                    df_edit = pd.read_csv(filename)
                                                    df_edit.at[r['orig_idx'], 'name'] = en
                                                    df_edit.at[r['orig_idx'], 'menge'] = em
                                                    df_edit.at[r['orig_idx'], 'kaufpreis'] = ee
                                                    df_edit.to_csv(filename, index=False)
                                                    st.rerun()
                                    with col_sell:
                                        with st.popover("💰"):
                                            # Hier sind jetzt zwei Eingabefelder
                                            v_m = st.number_input("Menge verkaufen", 0.0, float(r['menge']), float(r['menge']), key=f"vs_{r['orig_idx']}")
                                            v_p = st.number_input("Verkaufspreis (pro Stück)", 0.0, None, float(r['Wert']/r['menge']), key=f"vp_{r['orig_idx']}")
                                            
                                            if st.button("Verkauf Bestätigen", key=f"vb_{r['orig_idx']}"):
                                                df_sell = pd.read_csv(filename)
                                                
                                                # Berechnung des realisierten Gewinns für die Anzeige
                                                gewinn = (v_p - r['kaufpreis']) * v_m
                                                
                                                if v_m >= r['menge']:
                                                    # Komplettverkauf: Zeile löschen
                                                    df_sell = df_sell.drop(r['orig_idx'])
                                                    st.success(f"Komplett verkauft! Realisierter G/V: {gewinn:,.2f}")
                                                else:
                                                    # Teilverkauf: Menge reduzieren
                                                    df_sell.at[r['orig_idx'], 'menge'] = r['menge'] - v_m
                                                    st.success(f"Teilverkauf gebucht! Gewinn: {gewinn:,.2f}")
                                                
                                                df_sell.to_csv(filename, index=False)
                                                st.rerun()
                                    with col_del:
                                        if st.button("🗑️", key=f"dl_{r['orig_idx']}"):
                                            df_del = pd.read_csv(filename)
                                            df_del = df_del.drop(r['orig_idx'])
                                            df_del.to_csv(filename, index=False)
                                            st.rerun()
    st.divider()
    cd, cu = st.columns(2)
    if os.path.exists(filename): 
        cd.download_button("📥 Backup CSV", pd.read_csv(filename).to_csv(index=False), "portfolio.csv")
    up = cu.file_uploader("📤 CSV Wiederherstellen", type="csv")
    if up: 
        pd.read_csv(up).to_csv(filename, index=False)
        st.rerun()
# --- TAB 2: SIGNAL MONITOR ---
with t_sig:
    s_watch = pd.read_csv(signal_watchlist_file)['ticker'].tolist() if os.path.exists(signal_watchlist_file) else ["^GDAXI", "BTC-USD", "ETH-USD", "^GSPC","^NDX","^DJI", "KOSPI-3.KS" ]
    with st.form("s_add"):
        ns = st.text_input("Ticker zur Watchlist speichern:")
        if st.form_submit_button("Add"):
            if ns and ns.upper() not in s_watch:
                s_watch.append(ns.upper()); pd.DataFrame({"ticker": s_watch}).to_csv(signal_watchlist_file, index=False); st.rerun()
    
    for t in s_watch:
        try:
            sd = yf.download(t, period="2mo", interval=(tf if tf in ["5m", "1h", "1d"] else "1h"), progress=False)
            if not sd.empty:
                if isinstance(sd.columns, pd.MultiIndex): sd.columns = sd.columns.get_level_values(0)
                if tf in ["4h", "8h", "12h"]: sd = sd.resample(tf).agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
                sig = calculate_signals(sd)
                c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1, 1, 1, 0.5])
                c1.write(f"**{t}**")
                c2.write(f"RSI: {sig['rsi']:.1f}")
                c3.write(f"{sig['sentiment']}")
                c4.write(f"CVD: {'📈' if sig['cvd'] > 0 else '📉'}")
                color = "green" if "LONG" in sig['trend'] else "red" if "SHORT" in sig['trend'] else "gray"
                c5.markdown(f"<div style='background-color:{color}; color:white; padding:5px; text-align:center; border-radius:5px;'>{sig['trend']}</div>", unsafe_allow_html=True)
                if c6.button("🗑️", key=f"ds_{t}"):
                    s_watch.remove(t); pd.DataFrame({"ticker": s_watch}).to_csv(signal_watchlist_file, index=False); st.rerun()
        except: pass

# --- TAB 3: TERMINAL (KORRIGIERTE VERSION) ---
with t_multi:
    # 1. FUNKTION ZUM SPEICHERN (Hier definieren)
    def save_all_charts():
        ticker_liste = []
        for j in range(16):
            key = f"tm_{j}"
            # Wert aus Session State holen, Fallback auf BTCUSD
            val = st.session_state.get(key, "BTCUSD")
            ticker_liste.append(val)
        
        # Speichern in die Datei
        pd.DataFrame({"ticker": ticker_liste}).to_csv(chart_config_file, index=False)

    # 2. DATEN LADEN
    if os.path.exists(chart_config_file):
        try:
            saved_t = pd.read_csv(chart_config_file)['ticker'].tolist()
        except:
            saved_t = ["BTCUSD"] * 16
    else:
        saved_t = ["BTCUSD"] * 16

    # Liste auf 16 auffüllen, falls sie kürzer ist
    while len(saved_t) < 16:
        saved_t.append("BTCUSD")
    
    # Timeframe-Mapping
    tv_tf = {"5m":"5","30m":"30","1h":"60","4h":"240","8h":"480","12h":"720","1d":"D"}.get(tf, "D")
    
    t_cols = st.columns(cols_layout)
    
    # 3. DIE CHARTS ANZEIGEN
    for i in range(num_charts):
        # WICHTIG: Die Spalte korrekt auswählen
        with t_cols[i % cols_layout]:
            # Das Eingabefeld
            ti = st.text_input(
                f"Fenster {i+1}", 
                value=saved_t[i], 
                key=f"tm_{i}", 
                on_change=save_all_charts # Ruft die Funktion oben auf
            )
            
            # Das TradingView Widget
            components.html(f"""
                <div id="tv_{i}" style="height:450px;"></div>
                <script src="https://s3.tradingview.com/tv.js"></script>
                <script>
                new TradingView.widget({{
                  "autosize": true,
                  "symbol": "{ti}",
                  "interval": "{tv_tf}",
                  "timezone": "Europe/Berlin",
                  "theme": "dark",
                  "style": "1",
                  "locale": "de",
                  "enable_publishing": false,
                  "hide_side_toolbar": false,
                  "allow_symbol_change": true,
                  "container_id": "tv_{i}"
                }});
                </script>
            """, height=460)

    # DIESE ZEILE WAR FALSCH EINGERÜCKT (JETZT KORREKT UNTER DER FOR-SCHLEIFE)
    st.success("✅ Automatisches Speichern aktiv: Tippe einen Ticker und drücke ENTER.")
# --- TAB 4: SEKTOREN ---
with t_sec:
    st.subheader("🌐 Globaler Sektor-Trend (5 Tage)")
    
    with st.spinner('Analysiere Sektoren...'):
        sec_df = get_sector_performance()
    
    if not sec_df.empty:
        # Sortieren: Beste Sektoren nach oben
        sec_df = sec_df.sort_values(by="Trend %", ascending=False)
        
        # Anzeige in Kacheln (4 pro Reihe)
        rows = [sec_df.iloc[i:i+4] for i in range(0, len(sec_df), 4)]
        
        for row_data in rows:
            cols = st.columns(4)
            for i, (idx, row) in enumerate(row_data.iterrows()):
                color = "#2ecc71" if row['Trend %'] > 0 else "#e74c3c"
                cols[i].markdown(f"""
                    <div style="background-color:#1e1e1e; padding:15px; border-radius:10px; border-top: 4px solid {color}; text-align:center;">
                        <p style="margin:0; font-size:12px; color:#bdc3c7; text-transform:uppercase;">{row['Sektor'].split(' (')[0]}</p>
                        <h3 style="margin:0; color:{color};">{row['Trend %']:+.2f}%</h3>
                        <small style="color:#7f8c8d;">{row['Sektor'].split('(')[1].replace(')','')}</small>
                    </div>
                """, unsafe_allow_html=True)
        
        st.divider()
        st.caption("Daten basieren auf den US-Sektor-ETFs (XLK, XLE, SOXX etc.) als globale Benchmarks.")  

        
