import streamlit as st
import pandas as pd
import yfinance as yf
import os
import requests
import plotly.express as px
from datetime import datetime
import streamlit.components.v1 as components

# --- 0. KONFIGURATION ---
st.set_page_config(page_title="Investment Center Pro", layout="wide")
filename = "portfolio.csv"
history_file = "history.csv"

# --- CSS Styling ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; }
    iframe { border-radius: 8px; border: 1px solid #444; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border-left: 5px solid #00ff88; }
    .category-box { padding: 10px; border-radius: 5px; background: #262730; margin-bottom: 10px; border-left: 5px solid #00d4ff; }
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

@st.cache_data(ttl=300)
def get_currency_rate(from_curr, to_curr):
    if from_curr == to_curr or not from_curr: return 1.0
    try: return yf.Ticker(f"{from_curr}{to_curr}=X").fast_info.last_price
    except: return 1.0

@st.cache_data(ttl=120)
def get_prices_info(tickers, types, target_curr):
    results = {}
    for t, typ in zip(tickers, types):
        try:
            sym = str(t).strip().upper()
            if typ == "Krypto" and "-USD" not in sym: sym = f"{sym}-USD"
            t_obj = yf.Ticker(sym)
            info = t_obj.fast_info
            rate = get_currency_rate(info.currency, target_curr)
            results[t.lower()] = {"price": info.last_price * rate, "curr": info.currency}
        except: results[t.lower()] = {"price": 0.0, "curr": "USD"}
    return results

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Steuerung")
    base_currency = st.radio("Portfolio-Währung:", ["EUR", "USD"])
    curr_symbol = "€" if base_currency == "EUR" else "$"
    
    st.divider()
    st.subheader("🌡️ Sentiment")
    try:
        r = requests.get("https://api.alternative.me/fng/").json()
        fng_val, fng_class = r['data'][0]['value'], r['data'][0]['value_classification']
        st.metric("Crypto Fear & Greed", f"{fng_val}/100", fng_class)
    except: st.write("F&G: N/A")
    
    st.divider()
    num_charts = st.slider("Trading Fenster", 1, 16, 4)
    cols_layout = st.select_slider("Spalten", options=[1, 2, 3, 4], value=2)

# ==========================================================
# TEIL 1: MARKT MONITOR
# ==========================================================
st.subheader("📊 Global Market Watch")
m_tickers = {
    "DAX": "^GDAXI", "S&P 500": "^GSPC", "Nasdaq": "^NDX", "Dow Jones": "^DJI",
    "Gold": "GC=F", "Silber": "SI=F", "Öl": "BZ=F", "VIX": "^VIX",
    "BTC-EUR": "BTC-EUR", "ETH-USD": "ETH-USD", "EUR/TRY": "EURTRY=X"
}
m_cols = st.columns(6)
for i, (name, sym) in enumerate(m_tickers.items()):
    try:
        val = yf.Ticker(sym).fast_info.last_price
        m_cols[i % 6].metric(name, f"{val:,.2f}")
    except: m_cols[i % 6].metric(name, "Error")

st.divider()

# ==========================================================
# TEIL 2: PORTFOLIO & GETRENNTE ABTEILUNGEN
# ==========================================================
df_base = load_data()
if not df_base.empty:
    p_info = get_prices_info(df_base['ticker'].tolist(), df_base['typ'].tolist(), base_currency)
    df = df_base.copy()
    df['Kurs_T'] = df['ticker'].str.lower().apply(lambda x: p_info.get(x, {}).get('price', 0))
    df['Wert_T'] = df['menge'] * df['Kurs_T']
    df['Invest_T'] = df['menge'] * df['kaufpreis']
    df['Profit_T'] = df['Wert_T'] - df['Invest_T']
    df['Profit_%'] = (df['Profit_T'] / df['Invest_T'] * 100).fillna(0)

    st.title(f"💰 Portfolio: {df['Wert_T'].sum():,.2f} {curr_symbol}")

    # GETRENNTE BEREICHE
    for cat in ["Aktie", "Krypto", "ETF"]:
        sub = df[df['typ'] == cat]
        if not sub.empty:
            st.markdown(f"<div class='category-box'><h3>{cat} Abteilung</h3></div>", unsafe_allow_html=True)
            s1, s2, s3 = st.columns(3)
            cat_wert = sub['Wert_T'].sum()
            cat_profit = sub['Profit_T'].sum()
            cat_perf = (cat_profit / sub['Invest_T'].sum() * 100) if sub['Invest_T'].sum() > 0 else 0
            
            s1.metric(f"Wert {cat}", f"{cat_wert:,.2f} {curr_symbol}")
            s2.metric(f"Gewinn/Verlust", f"{cat_profit:,.2f} {curr_symbol}", f"{cat_perf:+.2f}%")
            s3.write(f"Anzahl Assets: {len(sub)}")
            
            st.dataframe(sub[['name', 'ticker', 'menge', 'Kurs_T', 'Wert_T', 'Profit_%']], use_container_width=True)
            st.divider()

st.divider()

# ==========================================================
# TEIL 3: MULTI-CHART TERMINAL
# ==========================================================
st.header("🖼️ TradingView Multi-Terminal")

def render_tv(symbol, index):
    html = f"""
    <div id="tv_{index}" style="height:400px;"></div>
    <script src="https://s3.tradingview.com/tv.js"></script>
    <script>
    new TradingView.widget({{"autosize": true, "symbol": "{symbol}", "interval": "D", "theme": "dark", "style": "1", "locale": "de", "container_id": "tv_{index}"}});
    </script>"""
    components.html(html, height=410)

tv_grid = st.columns(cols_layout)
for i in range(num_charts):
    with tv_grid[i % cols_layout]:
        t_in = st.text_input(f"Fenster {i+1}", value="BINANCE:BTCUSDT", key=f"chart_{i}")
        render_tv(t_in, i)

# ==========================================================
# TEIL 4: ADMINISTRATION (BACKUP & RESTORE)
# ==========================================================
st.divider()
with st.expander("🛠️ Administration (Backup, Restore, Neu)"):
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("➕ Neu")
        with st.form("new"):
            nt, nn = st.text_input("Ticker"), st.text_input("Name")
            nm, nk = st.number_input("Menge"), st.number_input("Kaufpreis")
            ny = st.selectbox("Typ", ["Aktie", "Krypto", "ETF"])
            if st.form_submit_button("Hinzufügen"):
                save_data(pd.concat([df_base, pd.DataFrame([{"ticker": nt.upper(), "name": nn, "menge": nm, "kaufpreis": nk, "typ": ny}])], ignore_index=True))
                st.rerun()

    with c2:
        st.subheader("💾 Backup")
        st.download_button("Download Portfolio CSV", df_base.to_csv(index=False), "portfolio.csv")

    with c3:
        st.subheader("📥 Restore")
        up_file = st.file_uploader("CSV hochladen", type="csv")
        if up_file and st.button("Daten überschreiben"):
            new_df = pd.read_csv(up_file)
            save_data(new_df)
            st.success("Erfolgreich geladen!")
            st.rerun()




    
