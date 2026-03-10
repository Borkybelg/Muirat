import streamlit as st
import pandas as pd
import yfinance as yf
import os
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime

import streamlit as st
from streamlit.web.server.websocket_headers import _get_websocket_headers

import streamlit as st

def check_password():
    # --- AUTOMATISCHER PC-CHECK (MODERNE VERSION) ---
    # Wir schauen in die Header der aktuellen Verbindung
    host = st.context.headers.get("host", "")
    
    # Wenn "localhost" in der Adresse steht, bist du am PC -> Sofort durchlassen
    if "localhost" in host or "127.0.0.1" in host:
        return True

    # --- PASSWORT-LOGIK FÜR HANDY / EXTERN ---
    if "password_correct" not in st.session_state:
        st.title("🔐 Sicherer Zugriff")
        st.info("Mobiler Zugriff erkannt. Bitte Passwort eingeben.")
        st.text_input("Passwort:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Passwort:", type="password", on_change=password_entered, key="password")
        st.error("❌ Passwort falsch!")
        return False
    else:
        return True

def password_entered():
    # Hier dein Passwort festlegen
    if st.session_state["password"] == "password":
        st.session_state["password_correct"] = True
        del st.session_state["password"]
    else:
        st.session_state["password_correct"] = False

# --- DEINE APP STARTET HIER ---
if check_password():
    st.title("🚀 Mein Portfolio")
    # Hier kommt dein restlicher Code hin (eingerückt!)
    st.write("Willkommen! Am PC ohne Passwort, am Handy mit Passwort.")
    # Hier kannst du deinen alten Code (Tabellen, Charts etc.) einrücken!


st.divider()

# --- KONFIGURATION ---
filename = "portfolio.csv" 
history_file = "history.csv"
st.set_page_config(page_title="Investment Center Pro", layout="wide")

# --- 1. DATEN-FUNKTIONEN ---
def load_data():
    if not os.path.exists(filename) or os.stat(filename).st_size == 0:
        return pd.DataFrame(columns=["ticker", "menge", "kaufpreis", "typ"])
    return pd.read_csv(filename)

def load_history():
    if not os.path.exists(history_file) or os.stat(history_file).st_size == 0:
        df = pd.DataFrame(columns=["datum", "ticker", "menge", "ek_preis", "vk_preis", "gewinn_verlust"])
        df.to_csv(history_file, index=False)
        return df
    return pd.read_csv(history_file)

def save_data(df_to_save):
    df_to_save.to_csv(filename, index=False)

def add_to_history(ticker, menge, ek, vk):
    try:
        df_h = load_history()
        gewinn = (float(vk) - float(ek)) * float(menge)
        new_entry = pd.DataFrame([{
            "datum": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "ticker": str(ticker).upper(),
            "menge": float(menge),
            "ek_preis": float(ek),
            "vk_preis": float(vk),
            "gewinn_verlust": float(gewinn)
        }])
        df_h = pd.concat([df_h, new_entry], ignore_index=True)
        df_h.to_csv(history_file, index=False)
    except Exception as e:
        st.error(f"Fehler beim Speichern: {e}")

@st.cache_data(ttl=120)
def get_all_prices(tickers, types):
    prices = {}
    for t, typ in zip(tickers, types):
        t_str = str(t).lower().strip()
        try:
            y_ticker = t.upper().strip()
            if typ == "Krypto" and "-USD" not in y_ticker: y_ticker = f"{y_ticker}-USD"
            tk = yf.Ticker(y_ticker)
            p = tk.fast_info.last_price
            if p is None or p <= 0:
                hist = tk.history(period="1d")
                if not hist.empty: p = hist['Close'].iloc[-1]
            prices[t_str] = p if p else 0.0
        except: prices[t_str] = 0.0
    return prices

# --- 2. MARKT-MONITOR (TICKER) ---
st.title("🚀 Investment Zentrale Pro")
st.subheader("📊 Markt-Monitor")

m_tickers = {
    "VIX (Angst)": "^VIX", "S&P 500": "^GSPC", "Nasdaq 100": "^NDX", 
    "Dow Jones": "^DJI", "DAX": "^GDAXI", "Hang Seng": "^HSI",
    "Nikkei 225": "^N225", "Shanghai": "000001.SS", "Gold": "PAXG-USD", 
    "Silber": "SI=F", "Kupfer": "HG=F", "Brent Öl": "BZ=F", 
    "EUR/USD": "EURUSD=X", "USD/TRY": "USDTRY=X"
}

m_cols = st.columns(len(m_tickers))
for i, (name, sym) in enumerate(m_tickers.items()):
    try:
        tk = yf.Ticker(sym)
        hist = tk.history(period="2d")
        if not hist.empty:
            p = hist['Close'].iloc[-1]
            c = ((p - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2] * 100) if len(hist) > 1 else 0.0
            f = ".2f" if any(x in name for x in ["VIX", "USD", "EUR"]) else ".0f"
            m_cols[i].metric(name, f"{p:{f}}", f"{c:+.2f}%")
    except: m_cols[i].metric(name, "ERR")

st.divider()

# --- 3. FEAR & GREED (GAUGES) ---
@st.cache_data(ttl=1800)
def get_fng_data():
    try:
        c_res = requests.get("https://api.alternative.me/fng/", timeout=5).json()
        c_v, c_s = int(c_res['data'][0]['value']), c_res['data'][0]['value_classification']
    except: c_v, c_s = 50, "Neutral"
    try:
        vix = yf.Ticker("^VIX").fast_info.last_price
        s_v = max(1, min(99, int(100 - (vix * 3)))) if vix else 50
        s_s = "Fear" if s_v < 45 else "Greed" if s_v > 55 else "Neutral"
    except: s_v, s_s = 50, "Neutral"
    return (s_v, s_s), (c_v, c_s)

def draw_gauge_final(value, title, subtitle):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = value,
        title = {'text': f"<b>{title}</b><br><span style='color:gray; font-size:14px'>{subtitle}</span>"},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "white"},
                 'steps': [{'range': [0, 25], 'color': '#8B0000'}, {'range': [25, 45], 'color': '#FF4B4B'},
                           {'range': [45, 55], 'color': '#FFA500'}, {'range': [55, 75], 'color': '#90EE90'},
                           {'range': [75, 100], 'color': '#008000'}]}
    ))
    fig.update_layout(height=200, margin=dict(l=40, r=40, t=60, b=20), paper_bgcolor='rgba(0,0,0,0)', font={'color': "white"})
    return fig

st.write("### 🌡️ Markt-Sentiment")
(s_val, s_txt), (c_val, c_txt) = get_fng_data()
col_s, col_c = st.columns(2)
with col_s: st.plotly_chart(draw_gauge_final(s_val, "Stocks (VIX)", s_txt), use_container_width=True)
with col_c: st.plotly_chart(draw_gauge_final(c_val, "Crypto", c_txt), use_container_width=True)

# --- 4. ASSET MANAGEMENT FUNKTION ---
def show_asset_management(asset_df, category_name, df_base):
    for idx, row in asset_df.iterrows():
        is_loss = float(row['Gewinn']) < 0
        status_icon = "🔴" if is_loss else "🟢"
        gain_color = "#FF4B4B" if is_loss else "#28A745"
        with st.expander(f"{status_icon} {row['ticker'].upper()} | Kurs: {row['Kurs']:,.2f} $ | Gewinn: {row['Gewinn']:,.2f} $"):
            c_info, c_manage = st.columns(2)
            with c_info:
                st.write(f"**Bestand:** {row['menge']:.4f} | **Ø EK:** {row['kaufpreis']:,.2f} $")
                st.markdown(f"<h3 style='color:{gain_color};'>{row['Gewinn']:,.2f} $ ({row['Prozent']:+.2f} %)</h3>", unsafe_allow_html=True)
            with c_manage:
                sub1, sub2, sub3 = st.tabs(["🛒 Trade", "📝 Edit", "🗑️"])
                with sub1:
                    m_type = st.radio("Aktion", ["Kauf", "Verkauf"], key=f"tr_{idx}")
                    amt = st.number_input("Menge", min_value=0.0, key=f"am_{idx}")
                    if m_type == "Verkauf":
                        vk_p = st.number_input("VK-Preis", value=float(row['Kurs']), key=f"vk_{idx}")
                        if st.button("Verkauf loggen", key=f"btn_{idx}"):
                            add_to_history(row['ticker'], amt, row['kaufpreis'], vk_p)
                            df_base.loc[idx, 'menge'] -= amt
                            if df_base.loc[idx, 'menge'] <= 0: df_base = df_base.drop(idx)
                            save_data(df_base); st.rerun()
                    elif st.button("Kauf speichern", key=f"kb_{idx}"):
                        p_k = st.number_input("Kaufpreis", key=f"pk_{idx}")
                        df_base.loc[idx, 'menge'] += amt
                        save_data(df_base); st.rerun()

# --- 5. PORTFOLIO LOGIK ---
df_base = load_data()
if not df_base.empty:
    prices = get_all_prices(df_base['ticker'].tolist(), df_base['typ'].tolist())
    df = df_base.copy()
    df['Kurs'] = df['ticker'].str.lower().map(prices).fillna(0.0)
    df['Wert'] = (df['menge'] * df['Kurs']).round(2)
    df['Kosten'] = (df['menge'] * df['kaufpreis']).round(2)
    df['Gewinn'] = (df['Wert'] - df['Kosten']).round(2)
    df['Prozent'] = (df['Gewinn'] / df['Kosten'] * 100).round(2)

    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Gesamt Portfolio", f"{df['Wert'].sum():,.2f} $")
    m2.metric("Investiert", f"{df['Kosten'].sum():,.2f} $")
    m3.metric("Profit", f"{df['Gewinn'].sum():,.2f} $", f"{(df['Gewinn'].sum()/df['Kosten'].sum()*100):+.2f}%")

    t1, t2, t3, t4, t5 = st.tabs(["🌍 Übersicht", "📈 Aktien", "₿ Krypto", "📊 ETFs", "📜 Historie"])
    with t1: st.dataframe(df[['ticker', 'typ', 'menge', 'Kurs', 'Wert', 'Prozent']], use_container_width=True)
    
    def sub_summary(sub_df, title, original_df):
        if not sub_df.empty:
            c1, c2, c3 = st.columns(3)
            s_gain = sub_df['Gewinn'].sum()
            c1.info(f"Wert: {sub_df['Wert'].sum():,.2f} $")
            c2.info(f"Invest: {sub_df['Kosten'].sum():,.2f} $")
            color = "#28A745" if s_gain >= 0 else "#FF4B4B"
            c3.markdown(f"<div style='border:1px solid #ccc; padding:10px;'><b>Ergebnis:</b><h2 style='color:{color};'>{s_gain:,.2f} $</h2></div>", unsafe_allow_html=True)
            show_asset_management(sub_df, title, original_df)
    
    with t2: sub_summary(df[df['typ'] == "Aktie"], "Aktien", df_base)
    with t3: sub_summary(df[df['typ'] == "Krypto"], "Kryptos", df_base)
    with t4: sub_summary(df[df['typ'] == "ETF"], "ETFs", df_base)
    with t5:
        h_df = load_history()
        st.table(h_df.sort_index(ascending=False))
        st.download_button("📥 History CSV", h_df.to_csv(index=False), "history.csv")

# --- 6. HINZUFÜGEN ---
with st.expander("➕ Neues Asset hinzufügen"):
    with st.form("add_f", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        nt = c1.text_input("Ticker")
        nm = c2.number_input("Menge", min_value=0.0)
        np = c3.number_input("Kaufpreis", min_value=0.0)
        nty = c4.selectbox