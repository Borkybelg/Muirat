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

# --- CSS Styling für das Design ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; }
    iframe { border-radius: 8px; border: 1px solid #444; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border-left: 5px solid #00ff88; }
    .header-box { padding: 10px; border-radius: 5px; background: #262730; margin: 20px 0 10px 0; border-left: 5px solid #ff4b4b; color: white; }
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
            results[t.lower()] = {"price": info.last_price * rate}
        except: results[t.lower()] = {"price": 0.0}
    return results

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Steuerung")
    base_currency = st.radio("Währung:", ["EUR", "USD"])
    curr_symbol = "€" if base_currency == "EUR" else "$"
    st.divider()
    num_charts = st.slider("Trading Fenster", 1, 16, 4)
    cols_layout = st.select_slider("Spalten", options=[1, 2, 3, 4], value=2)
    st.divider()
    try:
        r = requests.get("https://api.alternative.me/fng/").json()
        fng_val = r['data'][0]['value']
        st.metric("Crypto Fear & Greed", f"{fng_val}/100")
    except: pass

# ==========================================================
# TEIL 1: MARKT MONITOR (OBEN)
# ==========================================================
st.subheader("📊 Global Market Watch")
m_tickers = {"DAX": "^GDAXI", "S&P 500": "^GSPC", "Nasdaq": "^NDX", "Gold": "GC=F", "Öl": "BZ=F", "VIX": "^VIX", "BTC-EUR": "BTC-EUR"}
m_cols = st.columns(len(m_tickers))
for i, (name, sym) in enumerate(m_tickers.items()):
    try:
        val = yf.Ticker(sym).fast_info.last_price
        m_cols[i].metric(name, f"{val:,.2f}")
    except: m_cols[i].metric(name, "Err")

st.divider()

# ==========================================================
# TEIL 2: PORTFOLIO BEREICH (GETRENNT)
# ==========================================================
df_base = load_data()

if df_base.empty:
    st.warning("⚠️ Dein Portfolio ist noch leer. Scrolle nach ganz unten, um Assets hinzuzufügen!")
else:
    p_info = get_prices_info(df_base['ticker'].tolist(), df_base['typ'].tolist(), base_currency)
    df = df_base.copy()
    df['Kurs_Aktuell'] = df['ticker'].str.lower().apply(lambda x: p_info.get(x, {}).get('price', 0))
    df['Gesamtwert'] = df['menge'] * df['Kurs_Aktuell']
    df['Investiert'] = df['menge'] * df['kaufpreis']
    df['G_V_Euro'] = df['Gesamtwert'] - df['Investiert']
    
    # 🏆 GESAMT KAPITAL ANZEIGE
    total_val = df['Gesamtwert'].sum()
    total_profit = df['G_V_Euro'].sum()
    total_perc = (total_profit / df['Investiert'].sum() * 100) if df['Investiert'].sum() > 0 else 0
    
    st.markdown(f"<div class='header-box'><h1 style='text-align:center;'>💰 Gesamt Kapital: {total_val:,.2f} {curr_symbol}</h1></div>", unsafe_allow_html=True)
    st.columns(3)[1].metric("Gesamt Gewinn/Verlust", f"{total_profit:,.2f} {curr_symbol}", f"{total_perc:+.2f}%")

    # 📂 ABTEILUNGEN (AKTIEN, KRYPTO, ETF)
    for cat in ["Aktie", "Krypto", "ETF"]:
        sub = df[df['typ'] == cat]
        if not sub.empty:
            st.markdown(f"### 📦 {cat} Abteilung")
            w_sum = sub['Gesamtwert'].sum()
            p_sum = sub['G_V_Euro'].sum()
            perc = (p_sum / sub['Investiert'].sum() * 100) if sub['Investiert'].sum() > 0 else 0
            
            c1, c2 = st.columns(2)
            c1.metric(f"Summe {cat}", f"{w_sum:,.2f} {curr_symbol}")
            c2.metric("G/V Abteilung", f"{p_sum:,.2f} {curr_symbol}", f"{perc:+.2f}%")
            
            with st.expander(f"Details für {cat} anzeigen"):
                for idx, row in sub.iterrows():
                    col_a, col_b, col_c = st.columns([3, 2, 1])
                    col_a.write(f"**{row['name']}** ({row['ticker']})")
                    col_b.write(f"Wert: {row['Gesamtwert']:,.2f} {curr_symbol} (G/V: {row['G_V_Euro']:,.2f})")
                    if col_c.button("🗑️", key=f"del_{idx}"):
                        df_base = df_base.drop(idx)
                        save_data(df_base); st.rerun()
            st.divider()

# ==========================================================
# TEIL 3: TRADING TERMINAL
# ==========================================================
st.markdown("---")
st.header("🖼️ Trading Terminal")
tv_grid = st.columns(cols_layout)
for i in range(num_charts):
    with tv_grid[i % cols_layout]:
        t_in = st.text_input(f"Fenster {i+1}", value="BINANCE:BTCUSDT", key=f"chart_{i}")
        components.html(f"""
            <div id="tv_{i}" style="height:350px;"></div>
            <script src="https://s3.tradingview.com/tv.js"></script>
            <script>new TradingView.widget({{"autosize": true, "symbol": "{t_in}", "interval": "D", "theme": "dark", "container_id": "tv_{i}"}});</script>
        """, height=360)

# ==========================================================
# TEIL 4: ADMINISTRATION (Ganz unten)
# ==========================================================
st.divider()
with st.expander("🛠️ Administration (Asset hinzufügen / Backup)"):
    col1, col2 = st.columns(2)
    with col1:
        with st.form("new"):
            st.subheader("➕ Neues Asset")
            nt, nn = st.text_input("Ticker"), st.text_input("Name")
            nm, nk = st.number_input("Menge"), st.number_input("Kaufpreis")
            ny = st.selectbox("Typ", ["Aktie", "Krypto", "ETF"])
            if st.form_submit_button("Speichern"):
                new_df = pd.concat([df_base, pd.DataFrame([{"ticker": nt.upper(), "name": nn, "menge": nm, "kaufpreis": nk, "typ": ny}])], ignore_index=True)
                save_data(new_df); st.rerun()
    with col2:
        st.subheader("💾 Backup & Restore")
        st.download_button("Download Portfolio", df_base.to_csv(index=False), "portfolio.csv")
        up = st.file_uploader("Upload CSV")
        if up and st.button("Restore"):
            save_data(pd.read_csv(up)); st.rerun()
