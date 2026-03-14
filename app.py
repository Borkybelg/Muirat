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
    else: st.session_state["password_correct"] = False

def check_password():
    if st.session_state.get("password_correct", False): return True
    st.title("🔐 Sicherer Zugriff")
    st.text_input("Passwort:", type="password", on_change=password_entered, key="password")
    return False

if check_password():
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Menü")
        base_currency = st.radio("Währung:", ["EUR", "USD"])
        curr_symbol = "€" if base_currency == "EUR" else "$"
        st.divider()
        st.subheader("🌡️ Markt-Sentiment")
        try:
            r = requests.get("https://api.alternative.me/fng/").json()
            st.metric("Crypto Fear & Greed", f"{r['data'][0]['value']}/100", r['data'][0]['value_classification'])
        except: st.write("Crypto F&G: N/A")
        st.markdown("[📊 Aktien Fear & Greed (CNN)](https://edition.cnn.com/markets/fear-and-greed)")
        st.divider()
        num_charts = st.slider("Anzahl Charts", 1, 16, 4)
        cols_layout = st.select_slider("Spalten", options=[1, 2, 3, 4], value=2)

    # --- DATEN-FUNKTIONEN ---
    def load_data():
        cols = ["ticker", "name", "menge", "kaufpreis", "typ"] 
        if not os.path.exists(filename) or os.stat(filename).st_size == 0:
            return pd.DataFrame(columns=cols)
        df = pd.read_csv(filename)
        if "name" not in df.columns: df["name"] = df["ticker"]
        return df[cols]

    def save_data(df_to_save):
        df_to_save.to_csv(filename, index=False)

    @st.cache_data(ttl=120)
    def get_prices_info(tickers, types, target_curr):
        results = {}
        for t, typ in zip(tickers, types):
            try:
                sym = str(t).strip().upper()
                if typ == "Krypto" and "-USD" not in sym: sym = f"{sym}-USD"
                t_obj = yf.Ticker(sym)
                info = t_obj.fast_info
                rate = yf.Ticker(f"{info.currency}{target_curr}=X").fast_info.last_price if info.currency != target_curr else 1.0
                results[t.lower()] = {"price": info.last_price * rate, "rate": rate}
            except: results[t.lower()] = {"price": 0.0, "rate": 1.0}
        return results

    # --- MARKT MONITOR (ALLE TICKER) ---
    st.subheader("📊 Global Market Watch")
    m_tickers = {
        "DAX": "^GDAXI", "S&P 500": "^GSPC", "Nasdaq": "^NDX", "Dow Jones": "^DJI",
        "SDAX": "^SDAXI",  "MDAX": "^MDAXI", "TecDAX": "^TECDAX", "Russell 2k": "^RUT", 
         "Nikkei 225": "^N225", "China 50": "XIN9.FGI", "BTC-USD": "BTC-USD", "ETH-USD": "ETH-USD", "ETH-EUR": "ETH-EUR", 
        "Gold": "GC=F", "Silber": "SI=F", "Öl": "BZ=F", "VIX": "^VIX", "EUR/TRY": "EURTRY=X"
        
    }
    m_cols = st.columns(6)
    for i, (n, s) in enumerate(m_tickers.items()):
        try:
            val = yf.Ticker(s).fast_info.last_price
            m_cols[i % 6].metric(n, f"{val:,.2f}")
        except: m_cols[i % 6].metric(n, "Err")

    st.divider()
    df_base = load_data()

    if not df_base.empty:
        p_info = get_prices_info(df_base['ticker'].tolist(), df_base['typ'].tolist(), base_currency)
        df = df_base.copy()
        df['Kurs_Aktuell'] = df['ticker'].str.lower().apply(lambda x: p_info.get(x, {}).get('price', 0))
        df['Rate'] = df['ticker'].str.lower().apply(lambda x: p_info.get(x, {}).get('rate', 1.0))
        df['Gesamtwert'] = df['menge'] * df['Kurs_Aktuell']
        df['Investiert'] = df['menge'] * df['kaufpreis'] * df['Rate']
        df['Profit'] = df['Gesamtwert'] - df['Investiert']
        df['Profit_Perc'] = (df['Profit'] / df['Investiert'] * 100).fillna(0)

        # ÜBERSICHT (MIT GESAMTSUMME)
        st.title(f"💰 Portfolio: {df['Gesamtwert'].sum():,.2f} {curr_symbol}")
        
        t1, t2, t3, t4 = st.tabs(["🌍 Übersicht", "📈 Aktien", "₿ Krypto", "📊 ETFs"])
        with t1:
            st.dataframe(df[['name', 'ticker', 'menge', 'kaufpreis', 'Kurs_Aktuell', 'Gesamtwert', 'Profit']], use_container_width=True)

        def show_class(category):
            sub = df[df['typ'] == category]
            if not sub.empty:
                # Bereichs-Summen oben
                c1, c2, c3 = st.columns(3)
                c1.metric(f"Wert {category}", f"{sub['Gesamtwert'].sum():,.2f} {curr_symbol}")
                c2.metric("Profit/Verlust", f"{sub['Profit'].sum():,.2f} {curr_symbol}", f"{(sub['Profit'].sum()/sub['Investiert'].sum()*100):+.2f}%")
                c3.metric("Investiert", f"{sub['Investiert'].sum():,.2f} {curr_symbol}")
                
                st.divider()

                for idx, row in sub.iterrows():
                    # Expander mit G/V Info im Titel
                    with st.expander(f"📌 {row['name']} ({row['ticker']}) | G/V: {row['Profit']:,.2f} {curr_symbol} ({row['Profit_Perc']:+.2f}%)"):
                        
                        # ALLES IN EINER ZEILE (6 Spalten für maximale Übersicht)
                        d1, d2, d3, d4, d5, d6 = st.columns([1, 1.5, 1.5, 1.5, 1, 1])
                        
                        d1.write(f"**Anzahl:** {row['menge']}")
                        d2.write(f"**EK:** {row['kaufpreis']:.2f} {curr_symbol}")
                        d3.write(f"**Invest:** {row['Investiert']:,.2f} {curr_symbol}")
                        d4.write(f"**Wert:** {row['Gesamtwert']:,.2f} {curr_symbol}")
                        
                        # Bearbeiten Button (Popover für sauberes UI)
                        with d5:
                            with st.popover("📝"):
                                with st.form(f"edit_{idx}"):
                                    st.write(f"Ändere {row['name']}")
                                    new_m = st.number_input("Menge", value=float(row['menge']))
                                    new_e = st.number_input("Kaufpreis", value=float(row['kaufpreis']))
                                    if st.form_submit_button("Speichern"):
                                        df_base.at[idx, 'menge'] = new_m
                                        df_base.at[idx, 'kaufpreis'] = new_e
                                        save_data(df_base)
                                        st.rerun()

                        # Löschen Button
                        with d6:
                            if st.button("🗑️", key=f"del_{idx}"):
                                save_data(df_base.drop(idx))
                                st.rerun()
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

    # --- TERMINAL (SPEICHERT JETZT RICHTIG) ---
    # --- TERMINAL (TICKER-SUCHE INNERHALB DES CHARTS AKTIVIERT) ---
    # --- TERMINAL (MIT VOLLER ZEICHEN-TOOLBAR) ---
    st.markdown("---")
    st.header("🖼️ Multi-Chart Terminal")
    
    if "saved_tickers" not in st.session_state:
        if os.path.exists(chart_config_file): 
            st.session_state.saved_tickers = pd.read_csv(chart_config_file)['ticker'].tolist()
        else: 
            st.session_state.saved_tickers = ["BINANCE:BTCUSDT"] * 16

    tv_cols = st.columns(cols_layout)
    current_tickers = []
    
    for i in range(num_charts):
        with tv_cols[i % cols_layout]:
            val = st.session_state.saved_tickers[i] if i < len(st.session_state.saved_tickers) else "BINANCE:BTCUSDT"
            t_in = st.text_input(f"Fenster {i+1}", value=val, key=f"tv_input_{i}")
            current_tickers.append(t_in)
            
            # DAS VOLLE WIDGET MIT TOOLBAR
            components.html(f"""
            <div id="tv_{i}" style="height:500px;"></div>
            <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
            <script type="text/javascript">
            new TradingView.widget({{
              "autosize": true,
              "symbol": "{t_in}",
              "interval": "D",
              "timezone": "Europe/Berlin",
              "theme": "dark",
              "style": "1",
              "locale": "de",
              "enable_publishing": false,
              "hide_side_toolbar": false,     // ZEIGT DIE ZEICHEN-TOOLS LINKS
              "allow_symbol_change": true,    // ERMÖGLICHT SUCHE IM CHART
              "save_image": true,             // ERMÖGLICHT SCREENSHOTS
              "details": true,
              "hotlist": true,
              "calendar": true,
              "show_popup_button": true,      // ERMÖGLICHT GROSSANSICHT
              "popup_width": "1000",
              "popup_height": "650",
              "container_id": "tv_{i}"
            }});
            </script>
            """, height=510)

    if st.button("💾 Layout speichern & Feierabend"):
        st.session_state.saved_tickers = current_tickers
        pd.DataFrame({"ticker": current_tickers}).to_csv(chart_config_file, index=False)
        st.success("✅ Alles sicher gespeichert. Schönen Feierabend!")
