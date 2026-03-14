import streamlit as st
import pandas as pd
import yfinance as yf
import os
import requests
import plotly.express as px
from datetime import datetime
import streamlit.components.v1 as components

# --- 0. KONFIGURATION ---
st.set_page_config(page_title="Investment Center Pro & Terminal", layout="wide")
filename = "portfolio.csv"
history_file = "history.csv"

# --- CSS Styling ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; }
    iframe { border-radius: 8px; border: 1px solid #444; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border-left: 5px solid #00ff88; }
    </style>
""", unsafe_allow_html=True)

# --- 1. PASSWORT-LOGIK ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

def password_entered():
    if st.session_state["password"].strip().lower() == "pa":
        st.session_state["password_correct"] = True
        st.session_state["password"] = ""
    else: st.error("❌ Passwort falsch!")

if not st.session_state["password_correct"]:
    st.title("🔐 Sicherer Zugriff")
    st.text_input("Passwort:", type="password", on_change=password_entered, key="password")
    st.stop()

# --- DATEN-FUNKTIONEN ---
def load_data():
    cols = ["ticker", "name", "menge", "kaufpreis", "typ"] 
    if not os.path.exists(filename) or os.stat(filename).st_size == 0:
        return pd.DataFrame(columns=cols)
    try:
        df = pd.read_csv(filename)
        for c in cols:
            if c not in df.columns: df[c] = ""
        return df[cols]
    except: return pd.DataFrame(columns=cols)

def save_data(df_to_save):
    df_to_save.to_csv(filename, index=False)

def load_history():
    if not os.path.exists(history_file) or os.stat(history_file).st_size == 0:
        return pd.DataFrame(columns=["datum", "ticker", "menge", "ek", "vk", "gewinn"])
    return pd.read_csv(history_file)

@st.cache_data(ttl=120)
def get_prices_info(tickers, types):
    results = {}
    for t, typ in zip(tickers, types):
        try:
            sym = str(t).strip().upper()
            if typ == "Krypto" and "-USD" not in sym: sym = f"{sym}-USD"
            t_obj = yf.Ticker(sym)
            results[t.lower()] = {"price": t_obj.fast_info.last_price, "curr": t_obj.fast_info.currency}
        except: results[t.lower()] = {"price": 0.0, "curr": "USD"}
    return results

# --- SIDEBAR (Kommando-Zentrale) ---
with st.sidebar:
    st.header("⚙️ Menü")
    base_currency = st.radio("Währung:", ["EUR", "USD"])
    curr_symbol = "€" if base_currency == "EUR" else "$"
    
    st.divider()
    st.subheader("🌡️ Sentiment")
    try:
        r = requests.get("https://api.alternative.me/fng/").json()
        fng_val = r['data'][0]['value']
        fng_class = r['data'][0]['value_classification']
        st.metric("Crypto Fear & Greed", f"{fng_val}/100", fng_class)
    except: st.write("F&G: N/A")
    
    st.divider()
    st.subheader("📺 Terminal Setup")
    num_charts = st.slider("Anzahl Fenster", 1, 16, 4)
    cols_layout = st.select_slider("Spalten", options=[1, 2, 3, 4], value=2)

# ==========================================================
# TEIL 1: MARKT MONITOR (TICKERS)
# ==========================================================
st.subheader("📊 Global Market Watch")
m_tickers = {"DAX": "^GDAXI", "S&P 500": "^GSPC", "Nasdaq": "^NDX", "Gold": "GC=F", "BTC-EUR": "BTC-EUR"}
m_cols = st.columns(len(m_tickers))
for i, (n, s) in enumerate(m_tickers.items()):
    try:
        val = yf.Ticker(s).fast_info.last_price
        m_cols[i].metric(n, f"{val:,.2f}")
    except: m_cols[i].metric(n, "Error")

st.divider()

# ==========================================================
# TEIL 2: PORTFOLIO SUMME & ASSETS
# ==========================================================
df_base = load_data()
if not df_base.empty:
    p_info = get_prices_info(df_base['ticker'].tolist(), df_base['typ'].tolist())
    df = df_base.copy()
    df['Kurs_T'] = df['ticker'].str.lower().apply(lambda x: p_info.get(x, {}).get('price', 0))
    df['Wert_T'] = df['menge'] * df['Kurs_T']
    df['Invest_T'] = df['menge'] * df['kaufpreis']
    df['Profit_T'] = df['Wert_T'] - df['Invest_T']
    
    # Metriken Oben
    c1, c2, c3 = st.columns(3)
    c1.metric("Portfolio Wert", f"{df['Wert_T'].sum():,.2f} {curr_symbol}")
    c2.metric("Investiert", f"{df['Invest_T'].sum():,.2f} {curr_symbol}")
    c3.metric("Profit", f"{df['Profit_T'].sum():,.2f} {curr_symbol}")

    with st.expander("📂 Portfolio Details anzeigen"):
        st.dataframe(df[['name', 'ticker', 'typ', 'menge', 'Kurs_T', 'Wert_T']], use_container_width=True)

st.divider()

# ==========================================================
# TEIL 3: MULTI-CHART TERMINAL (BIS ZU 16 FENSTER)
# ==========================================================
st.header("🖼️ TradingView Pro Terminal")

def render_chart(symbol, index):
    html_code = f"""
    <div id="tv_{index}" style="height:400px;"></div>
    <script src="https://s3.tradingview.com/tv.js"></script>
    <script>
    new TradingView.widget({{"autosize": true, "symbol": "{symbol}", "interval": "D", "timezone": "Europe/Berlin", "theme": "dark", "style": "1", "locale": "de", "enable_publishing": false, "withdateranges": true, "hide_side_toolbar": false, "allow_symbol_change": true, "container_id": "tv_{index}"}});
    </script>"""
    components.html(html_code, height=410)

tv_grid = st.columns(cols_layout)
for i in range(num_charts):
    with tv_grid[i % cols_layout]:
        # Standard-Ticker Logik
        default_t = "BINANCE:BTCUSDT"
        if i == 0: default_t = "CRYPTOCAP:TOTAL"
        elif i == 1: default_t = "CRYPTOCAP:TOTAL2"
        
        t_input = st.text_input(f"Fenster {i+1}", value=default_t, key=f"v_{i}")
        render_chart(t_input, i)

# ==========================================================
# TEIL 4: BACKUP & NEU (Ganz unten)
# ==========================================================
st.divider()
with st.expander("🛠️ Administration & Backup"):
    col_add, col_back = st.columns(2)
    with col_add:
        st.subheader("➕ Neues Asset")
        with st.form("new"):
            nt = st.text_input("Ticker")
            nn = st.text_input("Name")
            nm = st.number_input("Menge", min_value=0.0)
            nk = st.number_input("Kaufpreis")
            ny = st.selectbox("Typ", ["Aktie", "Krypto", "ETF"])
            if st.form_submit_button("Hinzufügen"):
                new_row = pd.DataFrame([{"ticker": nt.upper(), "name": nn, "menge": nm, "kaufpreis": nk, "typ": ny}])
                save_data(pd.concat([df_base, new_row], ignore_index=True))
                st.rerun()
    with col_back:
        st.subheader("💾 Datensicherung")
        st.download_button("Download CSV", df_base.to_csv(index=False), "portfolio.csv")
