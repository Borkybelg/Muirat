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
chart_config_file = "charts_config.csv"

# --- 1. PASSWORT-LOGIK ---
def password_entered():
    if st.session_state["password"].strip().lower() == "pa":
        st.session_state["password_correct"] = True
        st.session_state["password"] = ""
    else:
        st.session_state["password_correct"] = False

def check_password():
    if st.session_state.get("password_correct", False): return True
    st.title("🔐 Sicherer Zugriff")
    st.text_input("Passwort:", type="password", on_change=password_entered, key="password")
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("❌ Passwort falsch!")
    return False

# --- START DER APP ---
if check_password():

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Menü")
        base_currency = st.radio("Portfolio-Währung:", ["EUR", "USD"], index=0)
        curr_symbol = "€" if base_currency == "EUR" else "$"
        
        st.divider()
        st.subheader("🌡️ Markt-Sentiment")
        try:
            r = requests.get("https://api.alternative.me/fng/").json()
            fng_val = r['data'][0]['value']
            fng_class = r['data'][0]['value_classification']
            st.metric("Crypto Fear & Greed", f"{fng_val}/100", fng_class)
        except: st.write("Crypto F&G: N/A")
        
        # Aktien Sentiment direkt darunter
        st.markdown("[📊 Aktien Fear & Greed (CNN)](https://edition.cnn.com/markets/fear-and-greed)")
        
        st.divider()
        st.subheader("📺 Terminal Setup")
        num_charts = st.slider("Anzahl Charts", 1, 16, 4)
        cols_layout = st.select_slider("Spalten", options=[1, 2, 3, 4], value=2)

    # --- DATEN-FUNKTIONEN ---
    def load_data():
        cols = ["ticker", "name", "menge", "kaufpreis", "typ"] 
        if not os.path.exists(filename) or os.stat(filename).st_size == 0:
            return pd.DataFrame(columns=cols)
        try:
            df = pd.read_csv(filename)
            if "name" not in df.columns: df["name"] = df["ticker"]
            return df[cols]
        except: return pd.DataFrame(columns=cols)

    def save_data(df_to_save):
        if df_to_save is not None:
            cols = ["ticker", "name", "menge", "kaufpreis", "typ"]
            for c in cols:
                if c not in df_to_save.columns: df_to_save[c] = ""
            df_to_save[cols].to_csv(filename, index=False)

    @st.cache_data(ttl=120)
    def get_currency_rate(from_curr, to_curr):
        if not from_curr or from_curr == to_curr: return 1.0
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
                results[t.lower()] = {"price": info.last_price * rate, "curr": info.currency, "rate": rate}
            except: results[t.lower()] = {"price": 0.0, "curr": "USD", "rate": 1.0}
        return results

    # --- PORTFOLIO BEREICH ---
    st.title(f"🚀 Investment Zentrale Pro ({base_currency})")

    st.subheader("📊 Global Market Watch")
    m_tickers = {"DAX": "^GDAXI", "S&P 500": "^GSPC", "Nasdaq": "^NDX", "Gold": "GC=F", "VIX": "^VIX", "BTC-EUR": "BTC-EUR"}
    m_cols = st.columns(len(m_tickers))
    for i, (n, s) in enumerate(m_tickers.items()):
        try:
            val = yf.Ticker(s).fast_info.last_price
            m_cols[i].metric(n, f"{val:,.2f}")
        except: m_cols[i].metric(n, "Error")

    st.divider()
    df_base = load_data()

    if not df_base.empty:
        p_info = get_prices_info(df_base['ticker'].tolist(), df_base['typ'].tolist(), base_currency)
        df = df_base.copy()
        df['Kurs_T'] = df['ticker'].str.lower().apply(lambda x: p_info.get(x, {}).get('price', 0))
        df['Rate_T'] = df['ticker'].str.lower().apply(lambda x: p_info.get(x, {}).get('rate', 1.0))
        df['Wert_T'] = df['menge'] * df['Kurs_T']
        df['Invest_T'] = df['menge'] * df['kaufpreis'] * df['Rate_T']
        df['Profit_T'] = df['Wert_T'] - df['Invest_T']
        df['Profit_%'] = (df['Profit_T'] / df['Invest_T'] * 100).fillna(0)

        m1, m2, m3 = st.columns(3)
        m1.metric("Gesamtwert", f"{df['Wert_T'].sum():,.2f} {curr_symbol}")
        m2.metric("Investiert", f"{df['Invest_T'].sum():,.2f} {curr_symbol}")
        p_ges = df['Profit_T'].sum()
        perf_ges = (p_ges / df['Invest_T'].sum() * 100) if df['Invest_T'].sum() > 0 else 0
        m3.metric("Profit Gesamt", f"{p_ges:,.2f} {curr_symbol}", f"{perf_ges:+.2f}%")

        st.divider()
        t1, t2, t3, t4 = st.tabs(["🌍 Übersicht", "📈 Aktien", "₿ Krypto", "📊 ETFs"])
        
        with t1:
            st.dataframe(df[['name', 'ticker', 'typ', 'menge', 'Kurs_T', 'Wert_T', 'Profit_T']], use_container_width=True)

        def show_class(category):
            sub = df[df['typ'] == category]
            if not sub.empty:
                st.write(f"### {category} Details")
                for idx, row in sub.iterrows():
                    with st.expander(f"{row['name']} ({row['ticker']})"):
                        st.write(f"Wert: {row['Wert_T']:,.2f} {curr_symbol}")
                        if st.button("🗑️ Löschen", key=f"del_{idx}"):
                            save_data(df_base.drop(idx)); st.rerun()

        with t2: show_class("Aktie")
        with t3: show_class("Krypto")
        with t4: show_class("ETF")

    # --- TOOLS ---
    st.divider()
    tc1, tc2, tc3 = st.columns(3)
    with tc1: st.download_button("📥 Backup", df_base.to_csv(index=False), "portfolio.csv")
    with tc2:
        up = st.file_uploader("📤 Restore", type="csv")
        if up and st.button("Einspielen"):
            save_data(pd.read_csv(up)); st.rerun()
    with tc3:
        with st.expander("➕ Neu"):
            with st.form("new"):
                nt, nn, nm, nk = st.text_input("Ticker"), st.text_input("Name"), st.number_input("Menge"), st.number_input("EK")
                ny = st.selectbox("Typ", ["Aktie", "Krypto", "ETF"])
                if st.form_submit_button("Hinzufügen"):
                    save_data(pd.concat([df_base, pd.DataFrame([{"ticker":nt.upper(),"name":nn,"menge":nm,"kaufpreis":nk,"typ":ny}])], ignore_index=True))
                    st.rerun()

    # --- TERMINAL ---
    st.markdown("---")
    st.header("🖼️ Multi-Chart Terminal")

    if "saved_tickers" not in st.session_state:
        if os.path.exists(chart_config_file):
            st.session_state.saved_tickers = pd.read_csv(chart_config_file)['ticker'].tolist()
        else:
            st.session_state.saved_tickers = ["BINANCE:BTCUSDT"] * 16

    def render_tv_chart(symbol, index):
        html = f"""<div id="tv_{index}" style="height:450px;"></div><script src="https://s3.tradingview.com/tv.js"></script>
        <script>new TradingView.widget({{"autosize":true,"symbol":"{symbol}","interval":"D","theme":"dark","container_id":"tv_{index}"}});</script>"""
        components.html(html, height=460)

    tv_cols = st.columns(cols_layout)
    current_tickers = []
    for i in range(num_charts):
        with tv_cols[i % cols_layout]:
            val = st.session_state.saved_tickers[i] if i < len(st.session_state.saved_tickers) else "BINANCE:BTCUSDT"
            t_in = st.text_input(f"Chart {i+1}", value=val, key=f"tv_input_{i}")
            current_tickers.append(t_in)
            render_tv_chart(t_in, i)

    if st.button("💾 Layout speichern"):
        st.session_state.saved_tickers = current_tickers
        pd.DataFrame({"ticker": current_tickers}).to_csv(chart_config_file, index=False)
        st.success("✅ Charts gespeichert!")
