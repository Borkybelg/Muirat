import streamlit as st
import pandas as pd
import yfinance as yf
import os
import plotly.express as px
from datetime import datetime

# --- KONFIGURATION ---
st.set_page_config(page_title="Investment Center Pro", layout="wide")
filename = "portfolio.csv"
history_file = "history.csv"

# --- PASSWORT ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

def check_password():
    if st.session_state["password_correct"]: return True
    st.title("🔐 Sicherer Zugriff")
    pwd = st.text_input("Passwort:", type="password")
    if st.button("Anmelden"):
        if pwd.lower() == "pa":
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("❌ Falsch!")
    return False

if check_password():
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Einstellungen")
        base_currency = st.radio("Währung", ["EUR", "USD"])
        curr_sym = "€" if base_currency == "EUR" else "$"

    # --- DATEN-FUNKTIONEN ---
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

    @st.cache_data(ttl=120)
    def get_prices(tickers, types, target_curr):
        p_dict = {}
        try:
            r = yf.download(["EURUSD=X", "EURHKD=X"], period="1d", progress=False)['Close']
            u_to_e = 1 / r["EURUSD=X"].iloc[-1]
            h_to_e = 1 / r["EURHKD=X"].iloc[-1]
        except: u_to_e, h_to_e = 0.92, 0.12

        for t, typ in zip(tickers, types):
            try:
                sym = str(t).upper()
                if typ == "Krypto" and "-USD" not in sym: sym = f"{sym}-USD"
                raw = yf.Ticker(sym).fast_info.last_price
                if sym.endswith(".HK"):
                    p = raw * h_to_e if target_curr == "EUR" else raw * (h_to_e / u_to_e)
                elif typ == "Krypto" or ".DE" not in sym:
                    p = raw * u_to_e if target_curr == "EUR" else raw
                else: p = raw if target_curr == "EUR" else raw / u_to_e
                p_dict[t.lower()] = p
            except: p_dict[t.lower()] = 0.0
        return p_dict

    # --- MARKT MONITOR ---
    st.title("🚀 Global Market Watch")
    m_ticks = {"DAX": "^GDAXI", "S&P 500": "^GSPC", "Nasdaq": "^NDX", "Russell 2k": "^RUT", "Gold": "GC=F", "Brent": "BZ=F", "VIX": "^VIX"}
    cols = st.columns(len(m_ticks))
    for i, (n, s) in enumerate(m_ticks.items()):
        try:
            val = yf.Ticker(s).history(period="1d")['Close'].iloc[-1]
            cols[i].metric(n, f"{val:,.2f}")
        except: cols[i].metric(n, "N/A")

    # --- PORTFOLIO LOGIK ---
    df_base = load_data()
    if not df_base.empty:
        prices = get_prices(df_base['ticker'].tolist(), df_base['typ'].tolist(), base_currency)
        df = df_base.copy()
        df['Kurs'] = df['ticker'].str.lower().map(prices).fillna(0.0)
        df['Wert'] = df['menge'] * df['Kurs']
        df['Invest'] = df['menge'] * df['kaufpreis']
        df['Profit'] = df['Wert'] - df['Invest']

        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Gesamtwert", f"{df['Wert'].sum():,.2f} {curr_sym}")
        c2.metric("Investiert", f"{df['Invest'].sum():,.2f} {curr_sym}")
        p_sum = df['Profit'].sum()
        c3.metric("Profit", f"{p_sum:,.2f} {curr_sym}", f"{(p_sum/df['Invest'].sum()*100) if df['Invest'].sum()>0 else 0:+.2f}%")

        tabs = st.tabs(["🌍 Übersicht", "📈 Assets", "➕ Neu & Backup"])
        
        with tabs[0]:
            st.dataframe(df[['name', 'ticker', 'typ', 'menge', 'Kurs', 'Wert', 'Profit']], use_container_width=True)
            st.plotly_chart(px.pie(df, values='Wert', names='name', title="Verteilung"), use_container_width=True)

        with tabs[1]:
            for idx, row in df.iterrows():
                with st.expander(f"⚙️ {row['name']} ({row['ticker']})"):
                    if st.button(f"Löschen {row['ticker']}", key=f"del_{idx}"):
                        save_data(df_base.drop(idx)); st.rerun()

        with tabs[2]:
            st.subheader("➕ Neues Asset")
            with st.form("add_form"):
                col_a, col_b = st.columns(2)
                nt = col_a.text_input("Ticker (z.B. 0992.HK)")
                nn = col_b.text_input("Beschreibung (z.B. Lenovo)")
                nm = st.number_input("Menge", min_value=0.0)
                nk = st.number_input(f"EK in {curr_sym}", min_value=0.0)
                ny = st.selectbox("Typ", ["Aktie", "Krypto", "ETF"])
                if st.form_submit_button("Hinzufügen"):
                    new = pd.DataFrame([{"ticker": nt.upper(), "name": nn, "menge": nm, "kaufpreis": nk, "typ": ny}])
                    save_data(pd.concat([df_base, new], ignore_index=True))
                    st.rerun()
            st.divider()
            st.download_button("📥 Backup CSV", df_base.to_csv(index=False), "portfolio.csv")
    else:
        st.info("Portfolio leer. Füge unten ein Asset hinzu!")
        # Formular auch bei leerem Portfolio anzeigen
        with st.form("first_add"):
            nt = st.text_input("Ticker")
            nn = st.text_input("Beschreibung")
            nm = st.number_input("Menge")
            nk = st.number_input("EK")
            ny = st.selectbox("Typ", ["Aktie", "Krypto", "ETF"])
            if st.form_submit_button("Erstes Asset hinzufügen"):
                new = pd.DataFrame([{"ticker": nt.upper(), "name": nn, "menge": nm, "kaufpreis": nk, "typ": ny}])
                save_data(new); st.rerun()
