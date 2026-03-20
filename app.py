import streamlit as st
import pandas as pd
import yfinance as yf
import os
import requests
import streamlit.components.v1 as components
import streamlit as st
import requests
import feedparser # Falls Fehlermeldung: im Terminal 'pip install feedparser' eingeben

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
    if len(df) < 50: 
        return {"rsi": 50, "ema20": 0, "trend": "Neutral", "cvd": 0, "oi": 0, "sentiment": "Neutral"}
    
    # RSI Berechnung
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    rsi_val = 100 - (100 / (1 + rs))
    
    # EMA 20
    ema20 = df['Close'].ewm(span=20, adjust=False).mean()
    
    # CVD & OI Proxy (Volumen-Analyse)
    vol_delta = (df['Close'] - df['Open']) / (df['High'] - df['Low'] + 1e-9) * df['Volume']
    cvd_val = vol_delta.rolling(window=20).sum().iloc[-1]
    oi_proxy = (df['Close'] * df['Volume']).rolling(window=20).mean().iloc[-1]
    
    last_p = df['Close'].iloc[-1]
    last_rsi = rsi_val.iloc[-1]
    last_ema = ema20.iloc[-1]
    
    # Sentiment & Trend Logik
    bull_score = 0
    if last_p > last_ema: bull_score += 1
    if last_rsi < 60: bull_score += 1
    if cvd_val > 0: bull_score += 1
    
    sentiment = "BULLISH 🚀" if bull_score >= 2 else "BEARISH 📉"
    
    if last_p > last_ema and last_rsi < 70: trend = "LONG 🟢"
    elif last_p < last_ema and last_rsi > 30: trend = "SHORT 🔴"
    else: trend = "WAIT 🟡"
    
    return {
        "rsi": last_rsi, 
        "ema20": last_ema, 
        "trend": trend, 
        "cvd": cvd_val, 
        "oi": oi_proxy, 
        "sentiment": sentiment
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
        # Wir holen die Daten der letzten 2 Tage im Stunden-Intervall
        hist = t.history(period="2d", interval="1h")
        if hist.empty: return None
        
        current_price = hist['Close'].iloc[-1]
        prev_1h = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        
        # 24h Änderung (ungefähr 24 Datenpunkte bei 1h Intervall)
        prev_24h = hist['Close'].iloc[0] 
        
        ch1h = ((current_price / prev_1h) - 1) * 100
        ch24h = ((current_price / prev_24h) - 1) * 100
        
        return {
            "price": current_price,
            "currency": t.fast_info.currency,
            "name": ticker,
            "price_change_1h": ch1h,
            "price_change_24h": ch24h
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
    if st.button("Anmelden") or (pwd.lower() == "para"):
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

st.subheader("📊 Global Market Watch (24h)")
m_tickers = {
    "DAX": "^GDAXI", "S&P 500": "^GSPC", "Nasdaq": "^NDX", "Dow Jones": "^DJI",
    "SDAX": "^SDAXI",  "MDAX": "^MDAXI", "TecDAX": "^TECDAX", "Russell 2k": "^RUT", 
    "Nikkei 225": "^N225", "China 50": "XIN9.FGI", "BTC-USD": "BTC-USD", "ETH-USD": "ETH-USD", 
    "Gold": "GC=F", "Silber": "SI=F", "Öl": "BZ=F", "VIX": "^VIX", "EUR/TRY": "EURTRY=X"
}

m_cols = st.columns(6)
for i, (n, s) in enumerate(m_tickers.items()):
    try:
        t_obj = yf.Ticker(s)
        fast = t_obj.fast_info
        
        current_price = fast.last_price
        # Berechnung der täglichen Änderung basierend auf dem gestrigen Schlusskurs
        prev_close = fast.previous_close
        
        if prev_close and prev_close > 0:
            change_pct = ((current_price - prev_close) / prev_close) * 100
        else:
            change_pct = 0.0

        # Anzeige mit Delta-Farbe (Grün für +, Rot für -)
        m_cols[i % 6].metric(
            label=n, 
            value=f"{current_price:,.2f}", 
            delta=f"{change_pct:+.2f}%"
        )
    except: 
        m_cols[i % 6].metric(n, "Err")
st.divider()

t_port, t_sig, t_multi, t_sec = st.tabs(["💰 PORTFOLIO", "🚦 SIGNAL MONITOR", "🖼️ TERMINAL", "📈 SEKTOREN"])

# --- TAB 1: PORTFOLIO ---
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
                info = get_live_data(ntick)
                if info:
                    fname = nname if nname else info['name']
                    nrow = pd.DataFrame([{"ticker":ntick.upper(),"name":fname,"menge":nqty,"kaufpreis":nek,"typ":ncat,"curr":info['currency']}])
                    if os.path.exists(filename):
                        pd.concat([pd.read_csv(filename), nrow]).to_csv(filename, index=False)
                    else: nrow.to_csv(filename, index=False)
                    st.success(f"{fname} hinzugefügt!"); st.rerun()
                else: st.error("Ticker nicht gefunden!")

    if os.path.exists(filename):
        df = pd.read_csv(filename).dropna(subset=['ticker'])
        if not df.empty:
            results = []
            for idx, row in df.iterrows():
                live = get_live_data(row['ticker'])
                if live and live['price'] > 0:
                    cp = live['price']
                    asset_curr = live['currency'] 
                    rate = get_fx_rate(asset_curr, base_currency)
                    val_base = row['menge'] * cp * rate
                    inv_base = row['menge'] * row['kaufpreis'] * rate
                    
                    # --- HIER WAR DER FEHLER: Sauberer Dictionary-Eintrag ---
                    results.append({
                        **row, 
                        "Wert": val_base, 
                        "Invest": inv_base, 
                        "GV": val_base - inv_base, 
                        "ch1h": live.get('price_change_1h', 0),
                        "ch24h": live.get('price_change_24h', 0),
                        "orig_idx": idx
                    })

            rdf = pd.DataFrame(results)
            total_v = rdf['Wert'].sum()
            total_gv = rdf['GV'].sum()
            total_inv = rdf['Invest'].sum()
            total_p = (total_gv / total_inv * 100) if total_inv > 0 else 0
            
            st.metric(f"🏦 GESAMTDEPOT ({base_currency})", f"{total_v:,.2f}", f"{total_p:+.2f}% ({total_gv:,.2f})")
            st.divider()

            # --- VISUALISIERUNG (Gekürzt für Übersicht) ---
            col_chart, col_stats, col_news = st.columns([1.5, 1, 1])
            # ... (dein restlicher Chart-Code kann hier bleiben) ...

            st.divider()

# --- ASSET LISTEN (OPTIMIERT MIT EK & STÜCKZAHL) ---
for k in ["Aktie", "Krypto", "ETF"]:
    sub = rdf[rdf['typ'] == k]
    if not sub.empty:
        s_wert = sub['Wert'].sum()
        s_gv = sub['GV'].sum()
        with st.expander(f"📦 {k}s (Gesamt: {s_wert:,.2f} | G/V: {s_gv:+.2f})", expanded=True):
            # Wir brauchen mehr Platz, daher passen wir die Breiten an
            # c1:Name, c2:Wert/EK, c3:G/V, c4:1H, c5:24H, c6:Menge, c7:Aktion
            h1, h2, h3, h4, h5, h6, h7 = st.columns([2, 1.8, 1.2, 0.8, 0.8, 1, 1.5])
            h1.caption("NAME")
            h2.caption(f"WERT / EK ({base_currency})")
            h3.caption("G/V")
            h4.caption("1H %")
            h5.caption("24H %")
            h6.caption("STÜCK")
            h7.caption("AKTION")

            for _, r in sub.iterrows():
                c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 1.8, 1.2, 0.8, 0.8, 1, 1.5])
                
                # Spalte 1: Name & Ticker
                c1.markdown(f"**{r['name']}**\n<small>{r['ticker']}</small>", unsafe_allow_html=True)
                
                # Sicherer Zugriff: Falls 'curr' fehlt, nimm die Basiswährung
                asset_currency = r.get('curr', base_currency) 
                rate = get_fx_rate(asset_currency, base_currency)
                
                # Spalte 3: Gewinn/Verlust
                gv_col = "green" if r['GV'] >= 0 else "red"
                c3.markdown(f"<span style='color:{gv_col}; font-weight:bold;'>{r['GV']:+.2f}</span>", unsafe_allow_html=True)
                
                # Spalte 4 & 5: Prozente
                c4.markdown(f"<span style='color:{'#00FF00' if r.get('ch1h',0)>=0 else '#FF4B4B'};'>{r.get('ch1h',0):+.2f}%</span>", unsafe_allow_html=True)
                c5.markdown(f"<span style='color:{'#00FF00' if r.get('ch24h',0)>=0 else '#FF4B4B'};'>{r.get('ch24h',0):+.2f}%</span>", unsafe_allow_html=True)
                
                # Spalte 6: Stückzahl
                c6.write(f"{r['menge']}")
                
                # Spalte 7: AKTIONEN
                with c7:
                    btn_edit, btn_sell, btn_del = st.columns(3)
                    
                    # 1. BEARBEITEN (📝)
                    with btn_edit:
                        with st.popover("📝"):
                            with st.form(f"edit_form_{r['orig_idx']}"):
                                st.write(f"Ändere {r['name']}")
                                new_n = st.text_input("Name", r['name'])
                                new_m = st.number_input("Stückzahl", value=float(r['menge']), step=0.01, format="%.4f")
                                new_e = st.number_input("Kaufpreis (EK)", value=float(r['kaufpreis']), step=0.01)
                                if st.form_submit_button("Speichern"):
                                    df_save = pd.read_csv(filename)
                                    df_save.at[r['orig_idx'], 'name'] = new_n
                                    df_save.at[r['orig_idx'], 'menge'] = new_m
                                    df_save.at[r['orig_idx'], 'kaufpreis'] = new_e
                                    df_save.to_csv(filename, index=False)
                                    st.rerun()

                    # 2. VERKAUFEN (💰) - Jetzt mit Verkaufspreis
                    with btn_sell:
                        with st.popover("💰"):
                            st.write(f"Verkauf: {r['name']}")
                            # Eingabe der Menge
                            sell_qty = st.number_input("Menge zum Verkaufen", 0.0, float(r['menge']), float(r['menge']), key=f"s_qty_{r['orig_idx']}")
                            # NEU: Eingabe des Verkaufspreises
                            sell_price = st.number_input("Verkaufspreis pro Stück", value=float(live['price'] if live else 0), key=f"s_prc_{r['orig_idx']}")
                            
                            if st.button("Verkauf Bestätigen", key=f"s_btn_{r['orig_idx']}"):
                                df_temp = pd.read_csv(filename)
                                
                                # Berechnung für deine Notizen (optional: hier könnte man eine History-Datei füllen)
                                gewinn = (sell_price - r['kaufpreis']) * sell_qty
                                st.toast(f"Verkauft! Gewinn: {gewinn:,.2f} {r.get('curr', 'EUR')}")

                                if sell_qty >= r['menge']:
                                    # Alles verkauft -> Zeile löschen
                                    df_temp = df_temp.drop(r['orig_idx'])
                                else:
                                    # Teilverkauf -> Menge reduzieren
                                    df_temp.at[r['orig_idx'], 'menge'] = r['menge'] - sell_qty
                                
                                df_temp.to_csv(filename, index=False)
                                st.rerun()
                    # 3. LÖSCHEN (🗑️)
                    with btn_del:
                        if st.button("🗑️", key=f"del_final_{r['orig_idx']}"):
                            df_temp = pd.read_csv(filename)
                            df_temp = df_temp.drop(r['orig_idx'])
                            df_temp.to_csv(filename, index=False)
                            st.rerun()

            # --- VISUALISIERUNG & STATS ---
            col_chart, col_stats, col_news = st.columns([1.5, 1, 1])
            with col_chart:
                import plotly.express as px
                c_data = rdf.groupby('typ')['Wert'].sum().reset_index()
                fig = px.pie(c_data, values='Wert', names='typ', hole=0.5, color_discrete_map={'Aktie':'#3498db', 'Krypto':'#f1c40f', 'ETF':'#9b59b6'})
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=220, showlegend=False)
                # Ändere den Key zu etwas Dynamischem oder entferne ihn einfach:
                st.plotly_chart(fig, use_container_width=True, key=f"donut_{base_currency}")

            with col_stats:
                st.write("🏆 **Top Asset**")
                top_r = rdf.loc[rdf['GV'].idxmax()]
                st.success(f"**{top_r['name']}**\n\n{top_r['GV']:+.2f} {base_currency}")
                st.write("📉 **Flop Asset**")
                flop_r = rdf.loc[rdf['GV'].idxmin()]
                st.error(f"**{flop_r['name']}**\n\n{flop_r['GV']:+.2f} {base_currency}")

            with col_news:
                st.write("📰 **Letzte News**")
                main_t = rdf.loc[rdf['Wert'].idxmax()]['ticker']
                y_news = get_yahoo_news(main_t)
                if y_news:
                    for n in y_news[:2]:
                        if 'title' in n and 'link' in n:
                            st.markdown(f"• <small>[{n['title'][:45]}...]({n['link']})</small>", unsafe_allow_html=True)
                else: st.caption("Keine News gefunden.")

            st.divider()

            # --- ASSET LISTEN (KOMPLETT MIT AKTIONEN) ---
            for k in ["Aktie", "Krypto", "ETF"]:
                sub = rdf[rdf['typ'] == k]
                if not sub.empty:
                    s_wert = sub['Wert'].sum()
                    s_gv = sub['GV'].sum()
                    with st.expander(f"📦 {k}s (Summe: {s_wert:,.2f} | G/V: {s_gv:+.2f})", expanded=True):
                        # Header mit 7 Spalten
                        h1, h2, h3, h4, h5, h6, h7 = st.columns([2, 1.2, 1.2, 0.8, 0.8, 1, 1.2])
                        h1.caption("NAME")
                        h2.caption(f"WERT ({base_currency})")
                        h3.caption("G/V")
                        h4.caption("1H %")
                        h5.caption("24H %")
                        h6.caption("MENGE")
                        h7.caption("AKTION")

                        for _, r in sub.iterrows():
                            c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 1.2, 1.2, 0.8, 0.8, 1, 1.2])
                            
                            c1.write(f"**{r['name']}**")
                            c2.write(f"{r['Wert']:,.2f}")
                            
                            gv_col = "green" if r['GV'] >= 0 else "red"
                            c3.markdown(f"<span style='color:{gv_col}; font-weight:bold;'>{r['GV']:+.2f}</span>", unsafe_allow_html=True)
                            
                            # Kursbewegung 1H (Grün/Rot)
                            c1h_col = "#00FF00" if r.get('ch1h', 0) >= 0 else "#FF4B4B"
                            c4.markdown(f"<span style='color:{c1h_col};'>{r.get('ch1h', 0):+.2f}%</span>", unsafe_allow_html=True)
                            
                            # Kursbewegung 24H (Grün/Rot)
                            c24h_col = "#00FF00" if r.get('ch24h', 0) >= 0 else "#FF4B4B"
                            c5.markdown(f"<span style='color:{c24h_col};'>{r.get('ch24h', 0):+.2f}%</span>", unsafe_allow_html=True)
                            
                            c6.write(f"{r['menge']}")
                            
                            with c7:
                                col_edit, col_sell, col_del = st.columns(3)
                                
                                # 1. Bearbeiten (📝)
                                with col_edit:
                                    with st.popover("📝"):
                                        with st.form(f"ed_{r['orig_idx']}"):
                                            et = st.text_input("Ticker", r['ticker'])
                                            en = st.text_input("Name", r['name'])
                                            em = st.number_input("Menge", float(r['menge']))
                                            ee = st.number_input("EK", float(r['kaufpreis']))
                                            if st.form_submit_button("Speichern"):
                                                df_edit = pd.read_csv(filename)
                                                df_edit.at[r['orig_idx'], 'ticker'] = et.upper()
                                                df_edit.at[r['orig_idx'], 'name'] = en
                                                df_edit.at[r['orig_idx'], 'menge'] = em
                                                df_edit.at[r['orig_idx'], 'kaufpreis'] = ee
                                                df_edit.to_csv(filename, index=False)
                                                st.rerun()

                                # 2. Verkaufen (💰)
                                with col_sell:
                                    with st.popover("💰"):
                                        v_m = st.number_input("Menge", 0.0, float(r['menge']), float(r['menge']), key=f"vs_{r['orig_idx']}")
                                        if st.button("Bestätigen", key=f"vb_{r['orig_idx']}"):
                                            df_sell = pd.read_csv(filename)
                                            if v_m >= r['menge']:
                                                df_sell = df_sell.drop(r['orig_idx'])
                                            else:
                                                df_sell.at[r['orig_idx'], 'menge'] = r['menge'] - v_m
                                            df_sell.to_csv(filename, index=False)
                                            st.rerun()

                                # 3. Löschen (🗑️)
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
    s_watch = pd.read_csv(signal_watchlist_file)['ticker'].tolist() if os.path.exists(signal_watchlist_file) else ["^GDAXI", "BTC-USD"]
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

# --- TAB 3: TERMINAL (REPARIERTE VERSION) ---
with t_multi:
    # 1. FUNKTION ZUM SPEICHERN (definiert, bevor sie benutzt wird)
    def save_all_charts():
        ticker_liste = []
        for j in range(16):
            key = f"tm_{j}"
            # Wir holen uns die Werte direkt aus dem Streamlit-Speicher (Session State)
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

    # Liste auf 16 auffüllen
    while len(saved_t) < 16:
        saved_t.append("BTCUSD")
    
    # Timeframe-Mapping
    tv_tf = {"5m":"5","30m":"30","1h":"60","4h":"240","8h":"480","12h":"720","1d":"D"}.get(tf, "D")
    
    t_cols = st.columns(cols_layout)
    
    # 3. DIE CHARTS ANZEIGEN
    for i in range(num_charts):
        with t_cols[i % cols_layout]:
            # WICHTIG: 'on_change' sorgt dafür, dass NameError nicht mehr passiert,
            # da sofort gespeichert wird, wenn du etwas änderst.
            ti = st.text_input(
                f"Fenster {i+1}", 
                value=saved_t[i], 
                key=f"tm_{i}", 
                on_change=save_all_charts
            )
            
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

        
