import streamlit as st
import pandas as pd
import yfinance as yf
import os
import plotly.express as px
from datetime import datetime

# --- 0. KONFIGURATION ---
st.set_page_config(page_title="Investment Center Pro", layout="wide")
filename = "portfolio.csv"
history_file = "history.csv"

# --- 1. PASSWORT-LOGIK ---
def password_entered():
    if st.session_state["password"].strip().lower() == "pa":
        st.session_state["password_correct"] = True
        st.session_state["password"] = ""
    else:
        st.session_state["password_correct"] = False

def check_password():
    if st.session_state.get("password_correct", False):
        return True
    st.title("🔐 Sicherer Zugriff")
    st.text_input("Passwort:", type="password", on_change=password_entered, key="password")
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("❌ Passwort falsch!")
    return False

# --- START DER APP ---
if check_password():

    # DATEN-FUNKTIONEN
    def load_data():
        if not os.path.exists(filename) or os.stat(filename).st_size == 0:
            return pd.DataFrame(columns=["ticker", "menge", "kaufpreis", "typ"])
        try:
            return pd.read_csv(filename)
        except:
            return pd.DataFrame(columns=["ticker", "menge", "kaufpreis", "typ"])

    def load_history():
        if not os.path.exists(history_file) or os.stat(history_file).st_size == 0:
            return pd.DataFrame(columns=["datum", "ticker", "menge", "ek", "vk", "gewinn"])
        try:
            return pd.read_csv(history_file)
        except:
            return pd.DataFrame(columns=["datum", "ticker", "menge", "ek", "vk", "gewinn"])

    def save_data(df_to_save):
        df_to_save.to_csv(filename, index=False)

    def add_to_history(ticker, menge, ek, vk):
        h_df = load_history()
        gewinn = (float(vk) - float(ek)) * float(menge)
        neu = pd.DataFrame([{
            "datum": datetime.now().strftime("%d.%m.%Y"),
            "ticker": ticker.upper(),
            "menge": menge,
            "ek": ek,
            "vk": vk,
            "gewinn": gewinn
        }])
        pd.concat([h_df, neu], ignore_index=True).to_csv(history_file, index=False)

    @st.cache_data(ttl=120)
    def get_prices(tickers, types):
        p_dict = {}
        for t, typ in zip(tickers, types):
            try:
                sym = str(t).strip().upper()
                if typ == "Krypto" and "-USD" not in sym:
                    sym = f"{sym}-USD"
                
                ticker_obj = yf.Ticker(sym)
                info = ticker_obj.fast_info
                current_price = info.last_price
                currency = info.currency # Hier prüfen wir die Währung (z.B. HKD, EUR)

                # Falls die Währung nicht USD ist, rechnen wir um
                if currency != "USD":
                    # Wir holen den Wechselkurs, z.B. HKDUSD=X
                    rate_ticker = f"{currency}USD=X"
                    rate = yf.Ticker(rate_ticker).fast_info.last_price
                    current_price = current_price * rate
                
                p_dict[t.lower()] = current_price
            except:
                p_dict[t.lower()] = 0.0
        return p_dict

    # --- UI BEREICH ---
    st.title("🚀 Investment Zentrale Pro")

    # 2. MARKT MONITOR (Nur einmal, korrekt eingerückt)
    st.subheader("📊 Globaler Markt-Monitor")
    m_tickers = {
        "DAX": "^GDAXI", "MDAX": "^MDAXI", "S&P 500": "^GSPC", "Nasdaq": "^NDX", "Russel 2000": "^RUT",
        "China 50": "000016.SS", "Nikkei 225": "^N225", "FTSE 100": "^FTSE", "EUR/USD": "EURUSD=X", "DXY": "DX-Y.NYB",
        "Gold": "GC=F", "VIX": "^VIX", "BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD"
    }
    
    cols = st.columns(5)
    for i, (name, symbol) in enumerate(m_tickers.items()):
        col_idx = i % 5
        try:
            val = yf.Ticker(symbol).fast_info.last_price
            if "EURUSD" in symbol:
                fmt_val = f"{val:.4f} $"
            elif val > 1000:
                fmt_val = f"{val:,.0f} $"
            else:
                fmt_val = f"{val:,.2f} $"
            cols[col_idx].metric(name, fmt_val)
        except:
            cols[col_idx].metric(name, "N/A")

    st.divider()

    # DATEN LADEN
    df_base = load_data()

    # 3. PORTFOLIO BERECHNUNGEN
    if not df_base.empty:
        prices = get_prices(df_base['ticker'].tolist(), df_base['typ'].tolist())
        df = df_base.copy()
        df['Kurs'] = df['ticker'].str.lower().map(prices).fillna(0.0)
        df['Wert'] = df['menge'] * df['Kurs']
        df['Invest'] = df['menge'] * df['kaufpreis']
        df['Profit'] = df['Wert'] - df['Invest']

        # GESAMT METRIKEN
        m1, m2, m3 = st.columns(3)
        m1.metric("Gesamtwert", f"{df['Wert'].sum():,.2f} $")
        m2.metric("Investiert", f"{df['Invest'].sum():,.2f} $")
        ges_profit = df['Profit'].sum()
        ges_perf = (ges_profit / df['Invest'].sum() * 100) if df['Invest'].sum() > 0 else 0
        m3.metric("Profit", f"{ges_profit:,.2f} $", f"{ges_perf:+.2f}%")

        t1, t2, t3, t4, t5 = st.tabs(["🌍 Übersicht", "📈 Aktien", "₿ Krypto", "📊 ETFs", "📜 Historie"])

        with t1:
            st.dataframe(df[['ticker', 'typ', 'menge', 'Kurs', 'Wert', 'Profit']], use_container_width=True)
            c1, c2 = st.columns(2)
            c1.plotly_chart(px.pie(df, values='Wert', names='typ', title="Verteilung Klassen"), use_container_width=True)
            c2.plotly_chart(px.pie(df, values='Wert', names='ticker', title="Verteilung Assets"), use_container_width=True)

        def show_class(category):
            sub = df[df['typ'] == category]
            if not sub.empty:
                cat_wert = sub['Wert'].sum()
                cat_invest = sub['Invest'].sum()
                cat_profit = sub['Profit'].sum()
                cat_perf = (cat_profit / cat_invest * 100) if cat_invest > 0 else 0
                
                cm1, cm2, cm3 = st.columns(3)
                cm1.metric(f"Wert {category}", f"{cat_wert:,.2f} $")
                cm2.metric(f"Invest {category}", f"{cat_invest:,.2f} $")
                cm3.metric(f"Profit {category}", f"{cat_profit:,.2f} $", f"{cat_perf:+.2f}%")
                st.write("---")

                for idx, row in sub.iterrows():
                    with st.expander(f"⚙️ {row['ticker'].upper()} managen"):
                        e1, e2 = st.columns(2)
                        with e1:
                            n_qty = st.number_input("Menge", value=float(row['menge']), key=f"q_{idx}")
                            n_ek = st.number_input("EK Preis", value=float(row['kaufpreis']), key=f"e_{idx}")
                        with e2:
                            tr_type = st.radio("Aktion", ["Kauf", "Verkauf"], key=f"tr_{idx}")
                            tr_amt = st.number_input("Trade Menge", min_value=0.0, key=f"tra_{idx}")
                        
                        b1, b2 = st.columns(2)
                        with b1:
                            if st.button("Speichern", key=f"save_{idx}"):
                                if tr_amt > 0:
                                    if tr_type == "Verkauf":
                                        add_to_history(row['ticker'], tr_amt, row['kaufpreis'], row['Kurs'])
                                        df_base.loc[idx, 'menge'] -= tr_amt
                                    else:
                                        df_base.loc[idx, 'menge'] += tr_amt
                                df_base.loc[idx, 'menge'] = n_qty
                                df_base.loc[idx, 'kaufpreis'] = n_ek
                                save_data(df_base[df_base['menge'] > 0])
                                st.rerun()
                        with b2:
                            if st.button("🗑️ Löschen", key=f"del_{idx}"):
                                save_data(df_base.drop(idx))
                                st.rerun()
                st.table(sub[['ticker', 'menge', 'Kurs', 'Wert', 'Profit']])
            else:
                st.info(f"Keine {category} vorhanden.")

        with t2: show_class("Aktie")
        with t3: show_class("Krypto")
        with t4: show_class("ETF")
        with t5:
            h_df = load_history()
            if not h_df.empty:
                h_df["gewinn"] = pd.to_numeric(h_df["gewinn"], errors="coerce").fillna(0)
                st.metric("Realisierter Gewinn", f"{h_df['gewinn'].sum():,.2f} $")
                st.dataframe(h_df, use_container_width=True)

    else:
        st.info("Portfolio ist leer.")

    # 5. TOOLS
    st.divider()
    tc1, tc2, tc3 = st.columns(3)
    with tc1:
        st.subheader("📥 Backup")
        st.download_button("Download Portfolio", df_base.to_csv(index=False), "portfolio.csv", "text/csv")
    with tc2:
        st.subheader("📤 Restore")
        up = st.file_uploader("CSV Datei", type="csv")
        if up and st.button("Daten laden"):
            save_data(pd.read_csv(up))
            st.rerun()
    with tc3:
        st.subheader("➕ Neu hinzufügen")
        with st.form("new_asset"):
            nt = st.text_input("Ticker")
            nm = st.number_input("Menge", min_value=0.0)
            nk = st.number_input("Kaufpreis", min_value=0.0)
            ny = st.selectbox("Typ", ["Aktie", "Krypto", "ETF"])
            if st.form_submit_button("Hinzufügen"):
                new_row = pd.DataFrame([{"ticker": nt, "menge": nm, "kaufpreis": nk, "typ": ny}])
                save_data(pd.concat([df_base, new_row], ignore_index=True))
                st.rerun()