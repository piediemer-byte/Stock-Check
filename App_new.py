import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. FUNKTIONEN ---
def calculate_rsi(data, window=14):
    if len(data) < window: return pd.Series()
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 2. KONFIGURATION & STYLING ---
st.set_page_config(page_title="StockIntelligence Pro", layout="wide")

st.markdown("""
<style>
    .main { background-color: #0e1117; color: white; }
    div[data-testid="stMetric"] { background-color: #000; border: 1px solid #333; padding: 15px; border-radius: 10px; }
    
    /* Styling für die nahtlosen Favoriten-Pillen */
    [data-testid="column"] { gap: 0rem !important; }
    
    /* Linker Teil der Pille (Ticker) */
    div.stButton > button[kind="secondary"] {
        border-radius: 20px 0 0 20px !important;
        border-right: none !important;
        background-color: #1e1e1e;
        height: 35px;
    }
    
    /* Rechter Teil der Pille (X) */
    div.stButton > button[kind="primary"] {
        border-radius: 0 20px 20px 0 !important;
        background-color: #1e1e1e;
        color: #ef5350 !important;
        border-left: 1px solid #444 !important;
        height: 35px;
        margin-left: -2px;
    }

    .target-box { background-color: #1e1e1e; padding: 20px; border-radius: 12px; border: 1px solid #333; }
</style>
""", unsafe_allow_html=True)

# --- 3. SESSION STATE ---
if 'watchlist' not in st.session_state: st.session_state.watchlist = ["RIOT", "AAPL", "MSFT"]
if 'search_query' not in st.session_state: st.session_state.search_query = "RIOT"
if 'period' not in st.session_state: st.session_state.period = '1y'

# --- 4. HEADER & SUCHE ---
st.title("📈 StockIntelligence Pro")

col_search, col_add, col_clear = st.columns([4, 0.5, 0.8])
search_input = col_search.text_input("Ticker suchen:", value=st.session_state.search_query, key="main_search").strip().upper()

if col_add.button("⭐"):
    if search_input and search_input not in st.session_state.watchlist:
        st.session_state.watchlist.append(search_input)
        st.rerun()

if col_clear.button("🗑️ Alle"):
    st.session_state.watchlist = []
    st.rerun()

# --- FAVORITEN-TAGS (INTEGRIERT) ---
if st.session_state.watchlist:
    # Raster für die Tags (4 pro Zeile)
    for i in range(0, len(st.session_state.watchlist), 4):
        row = st.session_state.watchlist[i:i+4]
        # Erzeuge Paare von Spalten für jede Pille
        cols = st.columns([2, 0.6, 2, 0.6, 2, 0.6, 2, 0.6])
        for idx, symbol in enumerate(row):
            with cols[idx*2]:
                if st.button(symbol, key=f"n_{symbol}", use_container_width=True, kind="secondary"):
                    st.session_state.search_query = symbol
                    st.rerun()
            with cols[idx*2 + 1]:
                if st.button("×", key=f"x_{symbol}", use_container_width=True, kind="primary"):
                    st.session_state.watchlist.remove(symbol)
                    st.rerun()

st.write("---")
mode = st.radio("Menü:", ["Analyse", "Prognosen", "Strong Buy", "Positionsrechner"], horizontal=True)

# Währung & API
eur_usd = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)
ticker = yf.Ticker(search_input)

# --- 5. HAUPTLOGIK ---
if mode == "Analyse" and search_input:
    try:
        # Immer 2 Jahre laden um SMA-Fehler bei 1T/1W zu vermeiden
        df_full = ticker.history(period="2y", interval="1d")
        if not df_full.empty:
            info = ticker.info
            st.subheader(f"{info.get('longName', search_input)}")
            
            # Zeit-Buttons mit Highlight
            t_cols = st.columns(5)
            periods = [("1T", "1d"), ("1W", "5d"), ("1M", "1mo"), ("6M", "6mo"), ("1J", "1y")]
            for i, (label, p) in enumerate(periods):
                if t_cols[i].button(label, key=f"z_{p}", type="primary" if st.session_state.period == p else "secondary", use_container_width=True):
                    st.session_state.period = p
                    st.rerun()

            # Indikatoren berechnen
            df_full['SMA50'] = df_full['Close'].rolling(50).mean()
            df_full['SMA200'] = df_full['Close'].rolling(200).mean()
            df_full['RSI'] = calculate_rsi(df_full)

            # Chart-Ausschnitt wählen
            days_map = {"1d": 2, "5d": 7, "1mo": 30, "6mo": 180, "1y": 365}
            plot_df = df_full.tail(days_map.get(st.session_state.period, 365))

            # Metriken
            m1, m2, m3, m4, m5 = st.columns(5)
            curr_p = info.get('currentPrice') or df_full['Close'].iloc[-1]
            m1.metric("Preis (€)", f"{curr_p * eur_usd:.2f} €")
            m2.metric("RSI", f"{df_full['RSI'].iloc[-1]:.1f}")
            m3.metric("KGV", f"{info.get('forwardPE', 'N/A')}")
            m4.metric("Dividende", f"{(info.get('dividendYield', 0) or 0)*100:.2f} %")
            
            rating = info.get('recommendationMean', 3.0)
            rec_text, rec_color = ("👍 Strong Buy", "normal") if rating <= 2.0 else ("✅ Buy", "normal") if rating <= 2.5 else ("➡️ Hold", "off")
            m5.metric("Rating", rec_text, delta_color=rec_color)

            # Chart
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name="Kurs"), row=1, col=1)
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA50'], name="SMA 50", line=dict(color='#00d1ff', width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA200'], name="SMA 200", line=dict(color='#ff4b4b', width=1.2)), row=1, col=1)
            fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['Volume'], name="Volumen", marker_color='#333'), row=2, col=1)
            fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False, margin=dict(t=10,b=10,l=0,r=0))
            st.plotly_chart(fig, use_container_width=True)
    except: st.error("Fehler beim Laden der Daten.")

elif mode == "Prognosen":
    info = ticker.info
    st.subheader(f"🎯 Analysten-Ziele für {search_input}")
    target = info.get('targetMeanPrice', 0)
    current = info.get('currentPrice', 1)
    if target > 0:
        diff = ((target/current)-1)*100
        st.markdown(f'<div class="target-box"><h4>Zielpreis: {target*eur_usd:.2f} €</h4><p>Potenzial: <span style="color:{"#00ff00" if diff>0 else "#ff4b4b"}">{diff:.2f} %</span></p></div>', unsafe_allow_html=True)
    else: st.info("Keine Kursziele verfügbar.")

elif mode == "Strong Buy":
    st.info("Scanner für Top-Ratings wird geladen...")
    # (Scanner Logik hier einfügen wie in vorherigen Versionen)

elif mode == "Positionsrechner":
    st.subheader("🧮 Risiko-Planer")
    entry = st.number_input("Einstieg (€)", value=100.0)
    stop = st.number_input("Stop Loss (€)", value=90.0)
    risk = st.number_input("Risiko (€)", value=50.0)
    if entry > stop: st.success(f"Menge: {int(risk/(entry-stop))} Stück")
