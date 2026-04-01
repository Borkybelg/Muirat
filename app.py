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
            df = pd.read_csv(history_file)
            if not isinstance(df, pd.DataFrame):
                return pd.DataFrame(columns=["datum", "ticker", "menge", "ek", "vk", "gewinn"])
            
            # Falls alte Spaltennamen existieren, umbenennen
            if "gewinn_verlust" in df.columns:
                df = df.rename(columns={"gewinn_verlust": "gewinn"})
            
            # Fehlende Spalten ergänzen
            for col in ["datum", "ticker", "menge", "ek", "vk", "gewinn"]:
                if col not in df.columns:
                    df[col] = 0.0 if col in ["menge", "ek", "vk", "gewinn"] else ""
            return df
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
                sym = t.upper()
                if typ == "Krypto" and "-USD" not in sym:
                    sym = f"{sym}-USD"
                p_dict[t.lower()] = yf.Ticker(sym).fast_info.last_price
            except Exception:
                p_dict[t.lower()] = 0.0
        return p_dict

    st.title("🚀 Investment Zentrale Pro")

    # 2. MARKT MONITOR
    m_tickers = {"DAX": "^GDAXI", "FTSE 100": "^FTSE", "S&P 500": "^GSPC", "Nasdaq": "^NDX",
    "Gold": "GC=F", "Silber": "SI=F", "Brent Öl": "BZ=F", 
    "BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD"
}
    cols = st.columns(len(m_tickers))
    for i, (n, s) in enumerate(m_tickers.items()):
        try:
            val = yf.Ticker(s).fast_info.last_price
            cols[i].metric(n, f"{val:,.2f}")
        except:
            cols[i].metric(n, "Error")

    st.divider()
    df_base = load_data()

    # 3. BERECHNUNGEN
    if not df_base.empty:
        prices = get_prices(df_base['ticker'].tolist(), df_base['typ'].tolist())
        df = df_base.copy()
        df['Kurs'] = df['ticker'].str.lower().map(prices).fillna(0.0)
        df['Wert'] = df['menge'] * df['Kurs']
        df['Invest'] = df['menge'] * df['kaufpreis']
        df['Profit'] = df['Wert'] - df['Invest']

        m1, m2, m3 = st.columns(3)
        m1.metric("Gesamtwert", f"{df['Wert'].sum():,.2f} $")
        m2.metric("Investiert", f"{df['Invest'].sum():,.2f} $")
        ges_invest = df['Invest'].sum()
        ges_profit = df['Profit'].sum()
        ges_perf = (ges_profit / ges_invest * 100) if ges_invest > 0 else 0
        m3.metric("Profit", f"{ges_profit:,.2f} $", f"{ges_perf:+.2f}%")

        st.divider()

        # 4. KATEGORIEN TABS
        t1, t2, t3, t4, t5 = st.tabs(["🌍 Übersicht", "📈 Aktien", "₿ Krypto", "📊 ETFs", "📜 Historie"])

        with t1:
            st.write("### Alle Assets")
            st.dataframe(df[['ticker', 'typ', 'menge', 'Kurs', 'Wert', 'Profit']], use_container_width=True)
            c1, c2 = st.columns(2)
            c1.plotly_chart(px.pie(df, values='Wert', names='typ', title="Verteilung Klassen"), use_container_width=True)
            c2.plotly_chart(px.pie(df, values='Wert', names='ticker', title="Verteilung Assets"), use_container_width=True)

        def show_class(category):
            sub = df[df['typ'] == category]
            if not sub.empty:
                val_sum, inv_sum = sub['Wert'].sum(), sub['Invest'].sum()
                diff = val_sum - inv_sum
                perc = (diff / inv_sum * 100) if inv_sum > 0 else 0.0

                col1, col2, col3 = st.columns(3)
                col1.metric(f"Wert {category}", f"{val_sum:,.2f} $")
                col2.metric(f"Invest {category}", f"{inv_sum:,.2f} $")
                col3.metric("Performance", f"{diff:,.2f} $", f"{perc:+.2f}%")

                for idx, row in sub.iterrows():
                    with st.expander(f"⚙️ {row['ticker'].upper()} managen"):
                        e1, e2 = st.columns(2)
                        with e1:
                            n_name = st.text_input("Name", value=row['ticker'], key=f"n_{idx}")
                            n_qty = st.number_input("Menge", value=float(row['menge']), key=f"q_{idx}")
                            n_ek = st.number_input("EK", value=float(row['kaufpreis']), key=f"e_{idx}")
                        with e2:
                            tr_type = st.radio("Aktion", ["Kauf", "Verkauf"], key=f"tr_{idx}")
                            tr_amt = st.number_input("Trade Menge", min_value=0.0, key=f"tra_{idx}")

                        if st.button(f"Speichern", key=f"btn_{idx}"):
                            if tr_amt > 0:
                                if tr_type == "Verkauf":
                                    add_to_history(row['ticker'], tr_amt, row['kaufpreis'], row['Kurs'])
                                    df_base.loc[idx, 'menge'] -= tr_amt
                                else:
                                    df_base.loc[idx, 'menge'] += tr_amt
                            
                            df_base.loc[idx, 'ticker'] = n_name
                            df_base.loc[idx, 'menge'] = n_qty
                            df_base.loc[idx, 'kaufpreis'] = n_ek
                            save_data(df_base[df_base['menge'] > 0])
                            st.rerun()
                st.table(sub[['ticker', 'menge', 'Kurs', 'Wert', 'Profit']])
            else:
                st.info(f"Keine {category} vorhanden.")

        with t2: show_class("Aktie")
        with t3: show_class("Krypto")
        with t4: show_class("ETF")
        
        with t5:
            st.subheader("📜 Verkaufshistorie")
            h_df = load_history()
            if not h_df.empty:
                # Sicherstellen, dass die Spalte 'gewinn' existiert und numerisch ist
                if "gewinn" in h_df.columns:
                    h_df["gewinn"] = pd.to_numeric(h_df["gewinn"], errors="coerce").fillna(0.0)
                    total_h = h_df["gewinn"].sum()
                    st.metric("Gesamtgewinn realisiert", f"{total_h:,.2f} $")
                st.dataframe(h_df, use_container_width=True)
            else:
                st.info("Historie leer.")
    else:
        st.info("Portfolio ist leer.")

    # 5. TOOLS
    st.divider()
    c_down, c_up, c_add = st.columns(3)
    with c_down:
        st.subheader("📥 Backup")
        st.download_button("Download CSV", df_base.to_csv(index=False), "portfolio.csv", "text/csv")
    with c_up:
        st.subheader("📤 Restore")
        up = st.file_uploader("Upload", type="csv")
        if up and st.button("Overwrite"):
            save_data(pd.read_csv(up))
            st.rerun()
    with c_add:
        st.subheader("➕ Neu")
        with st.form("add"):
            nt = st.text_input("Ticker")
            nm = st.number_input("Menge", min_value=0.0)
            nk = st.number_input("Preis", min_value=0.0)
            ny = st.selectbox("Typ", ["Aktie", "Krypto", "ETF"])
            if st.form_submit_button("Add"):
                new_row = pd.DataFrame([{"ticker": nt, "menge": nm, "kaufpreis": nk, "typ": ny}])
                save_data(pd.concat([df_base, new_row], ignore_index=True))
                st.rerun()
