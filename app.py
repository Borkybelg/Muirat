import streamlit as st
import pandas as pd
import yfinance as yf
import os
import requests
import streamlit.components.v1 as components
import feedparser

# --- 1. GLOBALE FUNKTIONEN (Ganz oben definieren) ---

def calculate_signals(df):
    """Berechnet RSI (Wilder's), EMA und Trends wie in TradingView."""
    if len(df) < 30: 
        return {"rsi": 50, "ema20": 0, "trend": "Neutral", "cvd": 0, "oi": 0, "sentiment": "Neutral"}
    
    # RSI Berechnung nach TradingView Standard (Wilder's/EMA)
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Wilder's Smoothing: alpha = 1/14
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    
    rs = avg_gain / (avg_loss + 1e-9)
    rsi_series = 100 - (100 / (1 + rs))
    last_rsi = rsi_series.iloc[-1]
    
    # EMA 20
    ema20 = df['Close'].ewm(span=20, adjust=False).mean()
    last_ema = ema20.iloc[-1]
    last_p = df['Close'].iloc[-1]
    
    # CVD & OI Proxy
    vol_delta = (df['Close'] - df['Open']) / (df['High'] - df['Low'] + 1e-9) * df['Volume']
    cvd_val = vol_delta.rolling(window=20).sum().iloc[-1]
    oi_proxy = (df['Close'] * df['Volume']).rolling(window=20).mean().iloc[-1]
    
    # Trend-Logik
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
        "oi": oi_proxy,
        "sentiment": "BULLISH 🚀" if last_rsi > 50 else "BEARISH 📉"
    }

@st.cache_data(ttl=3600)
def get_fx_rate(from_curr, to_curr):
    if not from_curr or from_curr == to_curr: return 1.0
    from_curr = str(from_curr).replace("ILA", "ILS").replace("GBp", "GBP")
    try:
        pair = f"{from_curr}{to_curr}=X"
        rate = yf.Ticker(pair).fast_info.last_price
        return rate if rate else 1.0
    except: return 1.0

def get_sector_performance():
    sectors = {"Tech": "XLK", "Energy": "XLE", "Health": "XLV", "Financials": "XLF", "Semis": "SOXX"}
    results = []
    try:
        data = yf.download(list(sectors.values()), period="5d", interval="1d", progress=False)['Close']
        for name, ticker in sectors.items():
            if ticker in data.columns:
                series = data[ticker].dropna()
                perf = ((series.iloc[-1] / series.iloc[0]) - 1) * 100
                results.append({"Sektor": name, "Ticker": ticker, "Trend %": round(perf, 2)})
    except: pass
    return pd.DataFrame(results)

# --- 2. SETUP & SIDEBAR ---
st.set_page_config(page_title="Investment Center Pro 2026", layout="wide")
filename = "portfolio.csv"
chart_config_file = "charts_config.csv"
signal_watchlist_file = "signals_watchlist.csv"

with st.sidebar:
    st.header("⚙️ Steuerung")
    base_currency = st.radio("Basis-Währung:", ["EUR", "USD"])
    tf = st.selectbox("Timeframe:", ["5m", "30m", "1h", "4h", "1d"], index=2)
    num_charts = st.slider("Anzahl Charts", 1, 16, 4)
    cols_layout = st.select_slider("Spalten", [1, 2, 3, 4], 2)

# --- 3. LOGIN ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False
if not st.session_state["password_correct"]:
    pwd = st.text_input("Sicherheitscode:", type="password")
    if pwd.lower() == "pa":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- 4. MAIN UI ---
st.subheader("📊 Global Market Watch")
# (Hier kämen deine Metriken/Kacheln für DAX, S&P etc. - gekürzt für Übersicht)

t_port, t_sig, t_multi, t_sec = st.tabs(["💰 PORTFOLIO", "🚦 SIGNAL MONITOR", "🖼️ TERMINAL", "📈 SEKTOREN"])

with t_port:
    st.write("Portfolio Management")
    # (Dein Portfolio-Code...)

with t_sig:
    st.subheader("Signal Monitor (TradingView Style)")
    if not os.path.exists(signal_watchlist_file):
        pd.DataFrame({"ticker": ["META", "BTC-USD"]}).to_csv(signal_watchlist_file, index=False)
    
    s_watch = pd.read_csv(signal_watchlist_file)['ticker'].tolist()
    
    with st.form("add_sig"):
        ns = st.text_input("Ticker hinzufügen:")
        if st.form_submit_button("Hinzufügen") and ns:
            s_watch.append(ns.upper())
            pd.DataFrame({"ticker": s_watch}).to_csv(signal_watchlist_file, index=False)
            st.rerun()

    for t in s_watch:
        try:
            # Download Daten
            sd = yf.download(t, period="2mo", interval=tf if tf != "4h" else "1h", progress=False)
            if not sd.empty:
                if isinstance(sd.columns, pd.MultiIndex): sd.columns = sd.columns.get_level_values(0)
                if tf == "4h": sd = sd.resample('4H').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
                
                # Berechnung
                sig = calculate_signals(sd)
                
                # Anzeige
                c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1])
                c1.write(f"**{t}**")
                c2.write(f"RSI: {sig['rsi']:.1f}")
                c3.write(sig['sentiment'])
                
                color = "green" if "LONG" in sig['trend'] else "red" if "SHORT" in sig['trend'] else "gray"
                c4.markdown(f"<div style='background-color:{color}; color:white; border-radius:5px; text-align:center;'>{sig['trend']}</div>", unsafe_allow_html=True)
                
                if c5.button("🗑️", key=f"del_{t}"):
                    s_watch.remove(t)
                    pd.DataFrame({"ticker": s_watch}).to_csv(signal_watchlist_file, index=False)
                    st.rerun()
        except: st.error(f"Fehler bei {t}")

with t_multi:
    # TradingView Terminal Logik (Dein bestehender Code ist hier okay)
    st.write("Terminal")

with t_sec:
    st.subheader("Sektoren Trend")
    # Sektoren Anzeige...
