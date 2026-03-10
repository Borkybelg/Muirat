import streamlit as st
import pandas as pd
import yfinance as yf
import os
import requests
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
    if st.session_state.get("password_correct", False): return True
    st.title("🔐 Sicherer Zugriff")
    st.text_input("Passwort:", type="password", on_change=password_entered, key="password")
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("❌ Passwort falsch!")
    return False

# --- START DER APP ---
if check_password():

    # --- SIDEBAR (Die Kommando-Zentrale) ---
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
        st.markdown("[📊 CNN Fear & Greed (Stocks)](https://edition.cnn.com/markets/fear-and-greed)")
        st.divider()
        st.info("Einklappen mit '>' oben links.")

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
            "ticker": ticker.upper(), "menge": menge, "ek": ek, "vk": vk, "gewinn": gewinn
        }])
        pd.concat([h_df, neu], ignore_index=True).to_csv(history_file, index=False)

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

    # --- HAUPTBEREICH ---
    st.title(f"🚀 Investment Zentrale Pro ({base_currency})")

    # 2. MARKT MONITOR (VOLLSTÄNDIG)
    st.subheader(f"📊 Globaler Markt-Überblick ({base_currency})")
    m_tickers = {
        "DAX": "^GDAXI", "MDAX": "^MDAXI", "S&P 500": "^GSPC", "Nasdaq": "^NDX", "Russel 2000": "^RUT",
        "Gold": "GC=F", "VIX": "^VIX", "BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD"
    }
    cols = st.columns(5)
    for i, (name, symbol) in enumerate(m_tickers.items()):
        try:
            tick = yf.Ticker(symbol)
            p = tick.fast_info.last_price * get_currency_rate(tick.fast_info.currency, base_currency)
            cols[i % 5].metric(name, f"{p:,.2f} {curr_symbol}")
        except: cols[i % 5].metric(name, "N/A")

    st.divider()
    df_base = load_data()

    if not df_base.empty:
        p_info = get_prices_info(df_base['ticker'].tolist(), df_base['typ'].tolist(), base_currency)
        df = df_base.copy()
        df['Kurs_T'] = df['ticker'].str.lower().apply(lambda x: p_info.get(x, {}).get('price', 0))
        df['Rate_T'] = df['ticker'].str.lower().apply(lambda x: p_info.get(x, {}).get('rate', 1.0))
        df['Orig_C'] = df['ticker'].str.lower().apply(lambda x: p_info.get(x, {}).get('curr', 'USD'))
        df['Wert_T'] = df['menge'] * df['Kurs_T']
        df['Invest_T'] = df['menge'] * df['kaufpreis'] * df['Rate_T']
        df['Profit_T'] = df['Wert_T'] - df['Invest_T']
        df['Profit_%'] = (df['Profit_T'] / df['Invest_T'] * 100).fillna(0)

        # GESAMT METRIKEN (MIT FARBE)
        m1, m2, m3 = st.columns(3)
        m1.metric("Gesamtwert Portfolio", f"{df['Wert_T'].sum():,.2f} {curr_symbol}")
        m2.metric("Gesamt Investiert", f"{df['Invest_T'].sum():,.2f} {curr_symbol}")
        p_ges = df['Profit_T'].sum()
        perf_ges = (p_ges / df['Invest_T'].sum() * 100) if df['Invest_T'].sum() > 0 else 0
        m3.metric("Profit Gesamt", f"{p_ges:,.2f} {curr_symbol}", f"{perf_ges:+.2f}%")

        st.divider()
        t1, t2, t3, t4, t5 = st.tabs(["🌍 Übersicht", "📈 Aktien", "₿ Krypto", "📊 ETFs", "📜 Historie"])
        
        with t1:
            disp_df = df[['ticker', 'typ', 'menge', 'Kurs_T', 'Wert_T', 'Profit_T', 'Profit_%', 'Orig_C']].copy()
            disp_df['Profit_%'] = disp_df['Profit_%'].map("{:+.2f}%".format)
            st.dataframe(disp_df, use_container_width=True)
            c1, c2 = st.columns(2)
            c1.plotly_chart(px.pie(df, values='Wert_T', names='typ', title="Verteilung Klassen"), use_container_width=True)
            c2.plotly_chart(px.pie(df, values='Wert_T', names='ticker', title="Verteilung Assets"), use_container_width=True)

        def show_class(category):
            sub = df[df['typ'] == category]
            if not sub.empty:
                # KATEGORIE SUMMEN (MIT FARBE)
                c_wert, c_inv = sub['Wert_T'].sum(), sub['Invest_T'].sum()
                c_prof = c_wert - c_inv
                c_perf = (c_prof / c_inv * 100) if c_inv > 0 else 0
                
                cm1, cm2, cm3 = st.columns(3)
                cm1.metric(f"Wert {category}", f"{c_wert:,.2f} {curr_symbol}")
                cm2.metric(f"Invest {category}", f"{c_inv:,.2f} {curr_symbol}")
                cm3.metric(f"Profit {category}", f"{c_prof:,.2f} {curr_symbol}", f"{c_perf:+.2f}%")
                st.write("---")

                for idx, row in sub.iterrows():
                    with st.expander(f"⚙️ {row['ticker'].upper()} | {row['Profit_%']:+.2f}%"):
                        # BEARBEITEN
                        c_n, c_q, c_e = st.columns(3)
                        n_name = c_n.text_input("Ticker", value=row['ticker'], key=f"n_{idx}")
                        n_qty = c_q.number_input("Menge", value=float(row['menge']), key=f"q_{idx}")
                        n_ek = c_e.number_input(f"EK ({row['Orig_C']})", value=float(row['kaufpreis']), key=f"e_{idx}")
                        
                        col_tr, col_amt = st.columns(2)
                        tr_type = col_tr.radio("Transaktion", ["Keine", "Kauf", "Verkauf"], horizontal=True, key=f"tr_{idx}")
                        tr_amt = col_amt.number_input("Trade Menge", min_value=0.0, key=f"tra_{idx}")
                        
                        b_s, b_d = st.columns(2)
                        if b_s.button("💾 Speichern", key=f"s_{idx}"):
                            if tr_type != "Keine" and tr_amt > 0:
                                if tr_type == "Verkauf":
                                    add_to_history(row['ticker'], tr_amt, row['kaufpreis']*row['Rate_T'], row['Kurs_T'])
                                    df_base.loc[idx, 'menge'] -= tr_amt
                                else:
                                    df_base.loc[idx, 'menge'] += tr_amt
                            df_base.loc[idx, 'ticker'] = n_name.upper()
                            df_base.loc[idx, 'menge'] = n_qty
                            df_base.loc[idx, 'kaufpreis'] = n_ek
                            save_data(df_base[df_base['menge'] > 0]); st.rerun()
                        if b_d.button("🗑️ Löschen", key=f"del_{idx}"):
                            save_data(df_base.drop(idx)); st.rerun()
                
                sub_disp = sub[['ticker', 'menge', 'Kurs_T', 'Wert_T', 'Profit_T', 'Profit_%']].copy()
                sub_disp['Profit_%'] = sub_disp['Profit_%'].map("{:+.2f}%".format)
                st.table(sub_disp)
            else: st.info(f"Keine {category} vorhanden.")

        with t2: show_class("Aktie")
        with t3: show_class("Krypto")
        with t4: show_class("ETF")
        with t5:
            h_df = load_history()
            if not h_df.empty: st.dataframe(h_df, use_container_width=True)

    # 3. TOOLS
    st.divider()
    tc1, tc2, tc3 = st.columns(3)
    with tc1:
        st.subheader("📥 Backup")
        st.download_button("Download CSV", df_base.to_csv(index=False), "portfolio.csv")
    with tc2:
        st.subheader("📤 Restore")
        up = st.file_uploader("Upload CSV", type="csv")
        if up and st.button("Überschreiben"):
            save_data(pd.read_csv(up)); st.rerun()
    with tc3:
        st.subheader("➕ Neu")
        with st.form("new"):
            nt = st.text_input("Ticker")
            nm = st.number_input("Menge", min_value=0.0)
            nk = st.number_input("Kaufpreis")
            ny = st.selectbox("Typ", ["Aktie", "Krypto", "ETF"])
            if st.form_submit_button("Hinzufügen"):
                save_data(pd.concat([df_base, pd.DataFrame([{"ticker": nt, "menge": nm, "kaufpreis": nk, "typ": ny}])], ignore_index=True)); st.rerun()