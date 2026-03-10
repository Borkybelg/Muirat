import streamlit as st
import pandas as pd
import yfinance as yf
import os
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime

# --- 0. KONFIGURATION (Muss ganz oben stehen) ---
st.set_page_config(page_title="Investment Center Pro", layout="wide")
filename = "portfolio.csv" 
history_file = "history.csv"

# --- 1. PASSWORT-LOGIK ---
def password_entered():
    # .strip() entfernt Leerzeichen, .lower() macht alles klein (einfacher am Handy)
    if st.session_state["password"].strip().lower() == "pa":
        st.session_state["password_correct"] = True
        st.session_state["password"] = "" 
    else:
        st.session_state["password_correct"] = False

def check_password():
    # Lokaler Zugriff (PC) wird sofort durchgelassen
    host = st.context.headers.get("host", "")
    if "localhost" in host or "127.0.0.1" in host:
        return True

    if st.session_state.get("password_correct", False):
        return True

    st.title("🔐 Sicherer Zugriff")
    st.info("Bitte Passwort eingeben, um Murats Portfolio zu sehen.")
    st.text_input("Passwort:", type="password", on_change=password_entered, key="password")

    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("❌ Passwort falsch!")
    return False

# --- HIER STARTET DIE GESCHÜTZTE APP ---
if check_password():
    # --- 2. DATEN-FUNKTIONEN ---
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

    # --- 3. MARKT-MONITOR ---
    st.title("🚀 Investment Zentrale Pro")
    st.subheader("📊 Markt-Monitor")

    m_tickers = {
        "VIX": "^VIX", "S&P 500": "^GSPC", "Nasdaq 100": "^NDX", 
        "Dow Jones": "^DJI", "DAX": "^GDAXI", "Gold": "PAXG-USD", 
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

    # --- 4. PORTFOLIO LOGIK & BERECHNUNG ---
    df_base = load_data()
    if not df_base.empty:
        prices = get_all_prices(df_base['ticker'].tolist(), df_base['typ'].tolist())
        df = df_base.copy()
        df['Kurs'] = df['ticker'].str.lower().map(prices).fillna(0.0)
        df['Wert'] = (df['menge'] * df['Kurs']).round(2)
        df['Kosten'] = (df['menge'] * df['kaufpreis']).round(2)
        df['Gewinn'] = (df['Wert'] - df['Kosten']).round(2)
        df['Prozent'] = (df['Gewinn'] / df['Kosten'] * 100).round(2)

        # --- METRIKEN ---
        total_val = df['Wert'].sum()
        total_invest = df['Kosten'].sum()
        total_profit = df['Gewinn'].sum()

        m1, m2, m3 = st.columns(3)
        m1.metric("Portfolio Wert", f"{total_val:,.2f} $")
        m2.metric("Investiert", f"{total_invest:,.2f} $")
        m3.metric("Gewinn/Verlust", f"{total_profit:,.2f} $", f"{(total_profit/total_invest*100 if total_invest > 0 else 0):+.2f}%")
        
        st.divider()

        # --- DIAGRAMME ---
        st.write("### 📊 Verteilung")
        c1, c2 = st.columns(2)
        with c1:
            fig1 = px.pie(df, values='Wert', names='ticker', hole=0.4, title="Nach Assets")
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            fig2 = px.pie(df, values='Wert', names='typ', hole=0.4, title="Nach Klassen")
            st.plotly_chart(fig2, use_container_width=True)

        st.divider()
        
        # --- TABS ---
        t1, t2, t3, t4, t5 = st.tabs(["🌍 Übersicht", "📈 Aktien", "₿ Krypto", "📊 ETFs", "📜 Historie"])
        
        with t1:
            st.dataframe(df[['ticker', 'typ', 'menge', 'Kurs', 'Wert', 'Prozent']], use_container_width=True)

        # --- Asset Management Funktionen (hier vereinfacht für den Schutz) ---
        def show_assets(sub_df, original_df):
            if not sub_df.empty:
                for idx, row in sub_df.iterrows():
                    with st.expander(f"{row['ticker'].upper()} | Gewinn: {row['Gewinn']:,.2f} $"):
                        st.write(f"Bestand: {row['menge']} | EK: {row['kaufpreis']} $")

        with t2: show_assets(df[df['typ'] == "Aktie"], df_base)
        with t3: show_assets(df[df['typ'] == "Krypto"], df_base)
        with t4: show_assets(df[df['typ'] == "ETF"], df_base)
        with t5:
            h_df = load_history()
            st.table(h_df.sort_index(ascending=False))

    # --- HINZUFÜGEN FORMULAR ---
    with st.expander("➕ Neues Asset hinzufügen"):
        with st.form("add_f", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)
            nt = c1.text_input("Ticker")
            nm = c2.number_input("Menge", min_value=0.0)
            np = c3.number_input("Kaufpreis", min_value=0.0)
            nty = c4.selectbox("Typ", ["Aktie", "Krypto", "ETF"])
            if st.form_submit_button("Hinzufügen"):
                new_row = pd.DataFrame([{"ticker": nt.lower(), "menge": nm, "kaufpreis": np, "typ": nty}])
                df_base = pd.concat([df_base, new_row], ignore_index=True)
                save_data(df_base)
                st.rerun()