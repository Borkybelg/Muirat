import streamlit as st
import pandas as pd
import yfinance as yf
import os
import requests
import plotly.express as px
from datetime import datetime
import streamlit.components.v1 as components

# --- 0. KONFIGURATION ---
st.set_page_config(page_title="Investment Center & Terminal", layout="wide")
filename = "portfolio.csv"
history_file = "history.csv"

# --- CSS für professionelles Dark-Design ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; }
    iframe { border-radius: 8px; border: 1px solid #444; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border-left: 5px solid #00ff88; }
    div[data-testid="stExpander"] { border: 1px solid #333; background: #0e1117; }
    </style>
""", unsafe_allow_html=True)

# --- 1. PASSWORT-LOGIK ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

def password_entered():
    if st.session_state["password"].strip().lower() == "pa":
        st.session_state["password_correct"] = True
        st.session_state["password"] = ""
    else:
        st.error("❌ Passwort falsch!")

def check_password():
    if st.session_state["password_correct"]: return True
    st.title("🔐 Sicherer Zugriff")
    st.text_input("Passwort:", type="password", on_change=password_entered, key="password")
    return False

# --- START DER APP ---
if check_password():

    # --- DATEN-FUNKTIONEN (DEINE BAUSTEINE) ---
    def load_data():
        cols = ["ticker", "name", "menge", "kaufpreis", "typ"] 
        if not os.path.exists(filename) or os.stat(filename).st_size == 0:
            return pd.DataFrame(columns=cols)
        df = pd.read_csv(filename)
        if "name" not in df.columns: df["name"] = df["ticker"]
        return df[cols]

    def save_data(df_to_save):
        cols = ["ticker", "name", "menge", "kaufpreis", "typ"]
        df_to_save[cols].to_csv(filename, index=False)

    def add_to_history(ticker, menge, ek, vk):
        h_df = pd.read_csv(history_file) if os.path.exists(history_file) else pd.DataFrame()
        gewinn = (float(vk) - float(ek)) * float(menge)
        neu = pd.DataFrame([{"datum": datetime.now().strftime("%d.%m.%Y"), "ticker": ticker.upper(), "menge": menge, "ek": ek, "vk": vk, "gewinn": gewinn}])
        pd.concat([h_df, neu], ignore_index=True).to_csv(history_file, index=False)

    @st.cache_data(ttl=120)
    def get_prices_info(tickers, types):
        results = {}
        for t, typ in zip(tickers, types):
            try:
                sym = str(t).strip().upper()
                if typ == "Krypto" and "-USD" not in sym: sym = f"{sym}-USD"
                t_obj = yf.Ticker(sym)
                info = t_obj.fast_info
                results[t.lower()] = {"price": info.last_price, "curr": info.currency}
            except: results[t.lower()] = {"price": 0.0, "curr": "USD"}
        return results

    # --- TRADINGVIEW FUNKTION ---
    def render_tv_chart(symbol, index):
        html_code = f"""
        <div id="tv_chart_{index}" style="height:450px;"></div>
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script type="text/javascript">
        new TradingView.widget({{
          "autosize": true, "symbol": "{symbol}", "interval": "H", "timezone": "Europe/Berlin",
          "theme": "dark", "style": "1", "locale": "de", "toolbar_bg": "#f1f3f6",
          "enable_publishing": false, "withdateranges": true, "hide_side_toolbar": false,
          "allow_symbol_change": true, "details": true, "hotlist": true, "calendar": true,
          "container_id": "tv_chart_{index}"
        }});
        </script> """
        components.html(html_code, height=460)

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Menü")
        base_currency = st.radio("Portfolio-Währung:", ["EUR", "USD"])
        curr_symbol = "€" if base_currency == "EUR" else "$"
        st.divider()
        num_charts = st.slider("Anzahl Trading-Fenster", 1, 4, 2)
        cols_layout = st.selectbox("Spalten-Layout", [1, 2], index=1)

    # ==========================================================
    # TEIL 1: PORTFOLIO (DEIN BESTEHENDER CODE)
    # ==========================================================
    st.title(f"🚀 Investment Zentrale Pro ({base_currency})")
    
    df_base = load_data()
    if not df_base.empty:
        p_info = get_prices_info(df_base['ticker'].tolist(), df_base['typ'].tolist())
        df = df_base.copy()
        df['Kurs_T'] = df['ticker'].str.lower().apply(lambda x: p_info.get(x, {}).get('price', 0))
        df['Wert_T'] = df['menge'] * df['Kurs_T']
        df['Invest_T'] = df['menge'] * df['kaufpreis']
        df['Profit_T'] = df['Wert_T'] - df['Invest_T']
        df['Profit_%'] = (df['Profit_T'] / df['Invest_T'] * 100).fillna(0)

        # Metriken Oben
        m1, m2, m3 = st.columns(3)
        m1.metric("Gesamtwert", f"{df['Wert_T'].sum():,.2f} {curr_symbol}")
        m2.metric("Investiert", f"{df['Invest_T'].sum():,.2f} {curr_symbol}")
        m3.metric("Gewinn/Verlust", f"{df['Profit_T'].sum():,.2f} {curr_symbol}", f"{df['Profit_%'].mean():+.2f}%")

        # Tabs für Kategorien
        t1, t2, t3, t4 = st.tabs(["🌍 Übersicht", "📈 Aktien", "₿ Krypto", "📜 Historie"])
        with t1:
            st.dataframe(df[['name', 'ticker', 'typ', 'menge', 'Kurs_T', 'Wert_T', 'Profit_%']], use_container_width=True)
            c1, c2 = st.columns(2)
            c1.plotly_chart(px.pie(df, values='Wert_T', names='typ', title="Klassen"), use_container_width=True)
            c2.plotly_chart(px.pie(df
