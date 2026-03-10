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

    # --- SIDEBAR EINSTELLUNGEN ---
    with st.sidebar:
        st.header("⚙️ Einstellungen")
        base_currency = st.radio("Portfolio-Währung wählen:", ["EUR", "USD"], index=0)
        curr_symbol = "€" if base_currency == "EUR" else "$"

    # DATEN-FUNKTIONEN
    def load_data():
        if not os.path.exists(filename) or os.stat(filename).st_size == 0:
            return pd.DataFrame(columns=["ticker", "menge", "kaufpreis", "typ"])
        return pd.read_csv(filename)

    def load_history():
        if not os.path.exists(history_file) or os.stat(history_file).st_size == 0:
            return pd.DataFrame(columns=["datum", "ticker", "menge", "ek", "vk", "gewinn"])
        return pd.read_csv(history_file)

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
    def get_currency_rate(from_curr, to_curr):
        if not from_curr or from_curr == to_curr: return 1.0
        try:
            return yf.Ticker(f"{from_curr}{to_curr}=X").fast_info.last_price
        except:
            return 1.0

    @st.cache_data(ttl=120)
    def get_prices_info(tickers, types, target_curr):
        results = {}
        for t, typ in zip(tickers, types):
            try:
                sym = str(t).strip().upper()
                if typ == "Krypto" and "-USD" not in sym: sym = f"{sym}-USD"
                t_obj = yf.Ticker(sym)
                info = t_obj.fast_info
                raw_price = info.last_price
                orig_curr = info.currency
                rate = get_currency_rate(orig_curr, target_curr)
                results[t.lower()] = {"price_target": raw_price * rate, "curr": orig_curr, "rate": rate}
            except:
                results[t.lower()] = {"price_target": 0.0, "curr": "USD", "rate": 1.0}
        return results

    st.title(f"🚀 Investment Zentrale Pro ({base_currency})")

    # 2. MARKT MONITOR
    st.subheader(f"📊 Globaler Markt-Überblick (in {base_currency})")
    m_tickers = {
        "DAX": "^GDAXI", "S&P 500": "^GSPC", "Nasdaq": "^NDX", "Russel 2000": "^RUT",
        "China 50": "000016.SS", "Nikkei 225": "^N225", "EUR/USD": "EURUSD=X", "DXY": "DX-Y.NYB",
        "Gold": "GC=F", "VIX": "^VIX", "BTC": "BTC-USD", "ETH": "ETH-USD"
    }
    cols = st.columns(6)
    for i, (name, symbol) in enumerate(m_tickers.items()):
        try:
            tick = yf.Ticker(symbol)
            p = tick.fast_info.last_price
            c = tick.fast_info.currency
            r = get_currency_rate(c, base_currency)
            cols[i % 6].metric(name, f"{(p*r):,.2f} {curr_symbol}")
        except:
            cols[i % 6].metric(name, "N/A")

    st.divider()
    df_base = load_data()

    if not df_base.empty:
        p_info = get_prices_info(df_base['ticker'].tolist(), df_base['typ'].tolist(), base_currency)
        df = df_base.copy()
        df['Kurs_T'] = df['ticker'].str.lower().apply(lambda x: p_info.get(x, {}).get('price_target', 0))
        df['Rate_T'] = df['ticker'].str.lower().apply(lambda x: p_info.get(x, {}).get('rate', 1.0))
        df['Orig_C'] = df['ticker'].str.lower().apply(lambda x: p_info.get(x, {}).get('curr', 'USD'))
        
        df['Wert_T'] = df['menge'] * df['Kurs_T']
        df['Invest_T'] = df['menge'] * df['kaufpreis'] * df['Rate_T']
        df['Profit_T'] = df['Wert_T'] - df['Invest_T']

        # GESAMT METRIKEN
        m1, m2, m3 = st.columns(3)
        m1.metric("Gesamtwert Portfolio", f"{df['Wert_T'].sum():,.2f} {curr_symbol}")
        m2.metric("Gesamt Investiert", f"{df['Invest_T'].sum():,.2f} {curr_symbol}")
        p_ges = df['Profit_T'].sum()
        perf = (p_ges / df['Invest_T'].sum() * 100) if df['Invest_T'].sum() > 0 else 0
        m3.metric("Profit Gesamt", f"{p_ges:,.2f} {curr_symbol}", f"{perf:+.2f}%")

        st.divider()
        t1, t2, t3, t4, t5 = st.tabs(["🌍 Übersicht", "📈 Aktien", "₿ Krypto", "📊 ETFs", "📜 Historie"])

        with t1:
            st.dataframe(df[['ticker', 'typ', 'menge', 'Kurs_T', 'Wert_T', 'Profit_T', 'Orig_C']], use_container_width=True)
            c1, c2 = st.columns(2)
            c1.plotly_chart(px.pie(df, values='Wert_T', names='typ', title="Verteilung Klassen"), use_container_width=True)
            c2.plotly_chart(px.pie(df, values='Wert_T', names='ticker', title="Verteilung Assets"), use_container_width=True)

        def show_class(category):
            sub = df[df['typ'] == category]
            if not sub.empty:
                c_wert = sub['Wert_T'].sum()
                c_inv = sub['Invest_T'].sum()
                c_prof = c_wert - c_inv
                c_perf = (c_prof / c_inv * 100) if c_inv > 0 else 0
                
                cm1, cm2, cm3 = st.columns(3)
                cm1.metric(f"Wert {category}", f"{c_wert:,.2f} {curr_symbol}")
                cm2.metric(f"Invest {category}", f"{c_inv:,.2f} {curr_symbol}")
                cm3.metric(f"Profit {category}", f"{c_prof:,.2f} {curr_symbol}", f"{c_perf:+.2f}%")
                st.write("---")

                for idx, row in sub.iterrows():
                    with st.expander(f"⚙️ {row['ticker'].upper()} ({row['Orig_C']})"):
                        ea, eb = st.columns(2)
                        with ea:
                            n_qty = st.number_input("Menge", value=float(row['menge']), key=f"q_{idx}")
                            n_ek = st.number_input(f"EK ({row['Orig_C']})", value=float(row['kaufpreis']), key=f"e_{idx}")
                        with eb:
                            tr_t = st.radio("Aktion", ["Kauf", "Verkauf"], key=f"tr_{idx}")
                            tr_a = st.number_input("Menge Trade", min_value=0.0, key=f"tra_{idx}")
                        
                        btn1, btn2 = st.columns(2)
                        with btn1:
                            if st.button("Speichern", key=f"s_{idx}"):
                                if tr_a > 0:
                                    if tr_t == "Verkauf":
                                        add_to_history(row['ticker'], tr_a, row['kaufpreis']*row['Rate_T'], row['Kurs_T'])
                                        df_base.loc[idx, 'menge'] -= tr_a
                                    else:
                                        df_base.loc[idx, 'menge'] += tr_a
                                df_base.loc[idx, 'menge'] = n_qty
                                df_base.loc[idx, 'kaufpreis'] = n_ek
                                save_data(df_base[df_base['menge'] > 0])
                                st.rerun()
                        with btn2:
                            if st.button("🗑️ Löschen", key=f"del_{idx}"):
                                save_data(df_base.drop(idx))
                                st.rerun()
                st.table(sub[['ticker', 'menge', 'Kurs_T', 'Wert_T', 'Profit_T']])
            else:
                st.info(f"Keine {category} vorhanden.")

        with t2: show_class("Aktie")
        with t3: show_class("Krypto")
        with t4: show_class("ETF")
        with t5:
            h_df = load_history()
            if not h_df.empty:
                st.metric("Realisierter Gewinn", f"{pd.to_numeric(h_df['gewinn']).sum():,.2f} {curr_symbol}")
                st.dataframe(h_df, use_container_width=True)

    # 3. TOOLS (DOWNLOAD / UPLOAD / HINZUFÜGEN)
    st.divider()
    tc1, tc2, tc3 = st.columns(3)
    
    with tc1:
        st.subheader("📥 Backup")
        st.download_button("Portfolio als CSV downloaden", df_base.to_csv(index=False), "portfolio_backup.csv", "text/csv")
        
    with tc2:
        st.subheader("📤 Restore")
        uploaded_file = st.file_uploader("CSV Datei hochladen", type="csv")
        if uploaded_file and st.button("Daten überschreiben"):
            save_data(pd.read_csv(uploaded_file))
            st.rerun()

    with tc3:
        st.subheader("➕ Neu hinzufügen")
        with st.form("new"):
            nt = st.text_input("Ticker (z.B. AAPL, 2018.HK)")
            nm = st.number_input("Menge", min_value=0.0)
            nk = st.number_input("Kaufpreis (Originalwährung)")
            ny = st.selectbox("Typ", ["Aktie", "Krypto", "ETF"])
            if st.form_submit_button("Hinzufügen"):
                new_row = pd.DataFrame([{"ticker": nt, "menge": nm, "kaufpreis": nk, "typ": ny}])
                save_data(pd.concat([df_base, new_row], ignore_index=True))
                st.rerun()