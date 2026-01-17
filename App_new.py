import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# --- 1. RSI BERECHNUNG ---
def calculate_rsi(data, window=14):
    if len(data) < window: return pd.Series()
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 2. APP KONFIGURATION ---
st.set_page_config(page_title="StockIntelligence Pro", layout="wide")

st.markdown("""
<style>
    .main { background-color: #0e1117; color: white; }
    div[data-testid="stMetric"] {
        background-color: #000000;
        border: 1px solid #333;
        padding: 15px;
        border-radius: 10px;
        color: white;
    }
    .news-box { background-color: #1e1e1e; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #bb86fc; }
    
    /* Styling für Watchlist Buttons */
    .stButton > button {
        border-radius: 15px;
        background-color: #1e1e1e;
        color: white;
        border: 1px solid #444;
    }
    /* Lösch-Buttons (X) Styling */
    .stButton > button[kind="secondary"] {
        color: #ff4b4b;
        border: 1px solid #333;
        font-size: 0.7em;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. SESSION STATE ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["RIOT", "BTC-USD", "AAPL"]
if 'period' not in st.session_state:
    st.session_state.period = '1y'
if 'current_symbol' not in st.session_state:
    st.session_state.current_symbol = "RIOT"

# --- 4. HEADER & SUCHE ---
st.title("📈 StockIntelligence")

col_search, col_add = st.columns([4, 1])
search_input = col_search.text_input("Aktie oder ISIN suchen:", value=st.session_state.current_symbol).strip().upper()

if col_add.button("⭐ +"):
    if search_input not in st.session_state.watchlist:
        st.session_state.watchlist.append(search_input)
        st.rerun()

# --- DYNAMISCHE WATCHLIST MIT EINZEL-LÖSCHFUNKTION ---
if st.session_state.watchlist:
    st.write("Favoriten:")
    # Wir erstellen für jedes Symbol zwei kleine Spalten (Symbol + Lösch-X)
    for symbol_wl in st.session_state.watchlist:
        col1, col2 = st.columns([3, 1])
        if col1.button(f"📊 {symbol_wl}", key=f"select_{symbol_wl}", use_container_width=True):
            st.session_state.current_symbol = symbol_wl
            st.rerun()
        if col2.button(f"X", key=f"del_{symbol_wl}", use_container_width=True):
            st.session_state.watchlist.remove(symbol_wl)
            st.rerun()
    
    if st.button("🗑️ Alle löschen", use_container_width=True):
        st.session_state.watchlist = []
        st.rerun()

st.write("---")
mode = st.radio("Bereich wählen:", ["Analyse", "Prognosen", "Positionsrechner"], horizontal=True)

# --- 5. DATEN-LOGIK ---
active_symbol = st.session_state.current_symbol if search_input == st.session_state.current_symbol else search_input

if active_symbol:
    try:
        ticker = yf.Ticker(active_symbol)
        info = ticker.info
        
        eur_usd_ticker = yf.Ticker("EURUSD=X")
        usd_to_eur_rate = 1 / eur_usd_ticker.info.get('regularMarketPrice', 1.09)

        if mode == "Analyse":
            st.subheader(f"{info.get('longName', active_symbol)}")
            
            # Zeit-Buttons
            t_cols = st.columns(5)
            periods = [("1T", "1d"), ("1W", "5d"), ("1M", "1mo"), ("6M", "6mo"), ("1J", "1y")]
            for i, (label, p) in enumerate(periods):
                btn_type = "primary" if st.session_state.period == p else "secondary"
                if t_cols[i].button(label, key=f"t_{p}", type=btn_type, use_container_width=True):
                    st.session_state.period = p
                    st.rerun()

            interval = "1m" if st.session_state.period == "1d" else "1d"
            df = ticker.history(period=st.session_state.period, interval=interval)

            if not df.empty:
                price_usd = info.get('currentPrice') or df['Close'].iloc[-1]
                price_eur = price_usd * usd_to_eur_rate
                pe_ratio = info.get('forwardPE') or info.get('trailingPE')
                df['RSI'] = calculate_rsi(df)
                current_rsi = df['RSI'].iloc[-1] if not df['RSI'].dropna().empty else 50.0
                change_pct = ((price_usd - df['Open'].iloc[0]) / df['Open'].iloc[0]) * 100

                # Metrics mit Tooltips
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("USD", f"{price_usd:.2f} $", f"{change_pct:.2f}%")
                m2.metric("EUR", f"{price_eur:.2f} €", f"{change_pct:.2f}%")
                m3.metric("KGV", f"{pe_ratio:.2f}" if pe_ratio else "N/A", help="Kurs-Gewinn-Verhältnis")
                m4.metric("RSI", f"{current_rsi:.1f}", help="Relative Strength Index")

                # Chart
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Kurs"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name="RSI", line=dict(color='#bb86fc')), row=2, col=1)
                fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)

        elif mode == "Prognosen":
            st.subheader(f"🎯 Prognosen & News: {active_symbol}")
            # ... News & Prognose Logik wie zuvor
            st.subheader("📰 News")
            for item in ticker.news[:5]:
                st.markdown(f'<div class="news-box"><a href="{item["link"]}" target="_blank" style="color:#bb86fc; text-decoration:none; font-weight:bold;">{item["title"]}</a></div>', unsafe_allow_html=True)

        elif mode == "Positionsrechner":
            st.subheader("🧮 Risiko-Planer")
            # ... Rechner Logik wie zuvor

    except Exception as e:
        st.error(f"Ticker Fehler: {e}")
