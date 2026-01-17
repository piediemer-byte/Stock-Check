import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. FUNKTIONEN ---
def calculate_rsi(data, window=14):
    if len(data) < window + 1: return pd.Series([50]*len(data))
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def update_period(p):
    st.session_state.period = p

@st.cache_data(ttl=3600)
def get_ki_strong_buys(sector_key, eur_val):
    sector_pool = {
        "Tech/KI": ["NVDA", "MSFT", "GOOGL", "AMD", "ASML", "TSM", "AVGO", "PLTR"],
        "Verteidigung": ["RHM.DE", "HENS.DE", "LMT", "RTX", "NOC", "GD"],
        "Energie": ["XOM", "CVX", "SHEL", "RWE.DE", "EON.DE"],
        "Pharma": ["LLY", "NVO", "ABBV", "JNJ", "BAYN.DE"]
    }
    res = []
    for s in sector_pool.get(sector_key, []):
        try:
            t = yf.Ticker(s)
            inf = t.info
            rec = inf.get('recommendationMean', 3.0)
            pe = inf.get('forwardPE') or inf.get('trailingPE')
            if rec <= 2.2 and (pe is None or pe < 45):
                res.append({
                    "Symbol": s, "Name": inf.get('shortName', s),
                    "Preis (€)": round(inf.get('currentPrice', 0) * eur_val, 2),
                    "Div/Aktie (€)": round(inf.get('dividendRate', 0) * eur_val, 2),
                    "KGV": round(pe, 1) if pe else "N/A",
                    "Rating": "🔥 Strong Buy" if rec <= 1.7 else "✅ Buy"
                })
        except: continue
    return pd.DataFrame(res)

# --- 2. CONFIG & STYLE ---
st.set_page_config(page_title="StockIntelligence AI", layout="wide")
if 'period' not in st.session_state: st.session_state.period = '1y'

st.markdown("""
<style>
    .stButton > button { width: 100%; border-radius: 8px; font-weight: bold; height: 42px; }
    .section-header { background: linear-gradient(90deg, #00d1ff, #bb86fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.6em; font-weight: bold; margin: 15px 0; }
    .ki-badge { text-align:center; border:2px solid; border-radius:10px; padding:8px; font-weight:bold; }
</style>
""", unsafe_allow_html=True)

# --- 3. DATEN LADEN ---
st.title("🛡️ StockIntelligence Pro")
query = st.text_input("Ticker-Suche:", value="AAPL").upper()
eur_usd = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

try:
    ticker = yf.Ticker(query)
    info = ticker.info
    
    # Smartphone Zeitachsen Buttons
    st.write("**Zeitraum wählen:**")
    p_cols = st.columns(5)
    periods = [("1T", "1d"), ("1W", "5d"), ("1M", "1mo"), ("6M", "6mo"), ("1J", "1y")]
    for i, (lab, pk) in enumerate(periods):
        p_cols[i].button(lab, key=f"p_{pk}", on_click=update_period, args=(pk,), 
                         type="primary" if st.session_state.period == pk else "secondary")

    # Daten-Abruf
    p_map = {"1d":"1m", "5d":"5m", "1mo":"1d", "6mo":"1d", "1y":"1d"}
    hist = ticker.history(period=st.session_state.period, interval=p_map[st.session_state.period])
    full_hist = ticker.history(period="2y")

    if not hist.empty:
        # --- KENNZAHLEN MIT TOOLTIP ---
        st.markdown('<p class="section-header">📊 Kennzahlen & Performance</p>', unsafe_allow_html=True)
        m1, m2 = st.columns(2)
        m3, m4 = st.columns(2)
        
        start_price = hist['Close'].iloc[0]
        end_price = hist['Close'].iloc[-1]
        perf_pct = ((end_price / start_price) - 1) * 100
        
        m1.metric(f"Preis (€) - {st.session_state.period}", 
                  f"{end_price * eur_usd:.2f} €", 
                  f"{perf_pct:.2f} %",
                  help="Aktueller Kurs in Euro und die prozentuale Veränderung im gewählten Zeitraum.")
        
        pe_val = info.get('forwardPE', 'N/A')
        m2.metric("KGV (Forward)", f"{pe_val}", 
                  help="Das Kurs-Gewinn-Verhältnis gibt an, das Wievielfache des erwarteten Gewinns die Aktie kostet. Unter 20 gilt oft als günstig.")
        
        m3.metric("Div/Aktie (€)", f"{info.get('dividendRate', 0) * eur_usd:.2f} €",
                  help="Die jährlich zu erwartende Auszahlung pro gehaltener Aktie in Euro.")
        
        with m4:
            rec = info.get('recommendationMean', 3.0)
            color = "#00ff00" if rec <= 2.2 else "#ff4b4b" if rec >= 3.2 else "#ffa500"
            label = "BUY" if rec <= 2.2 else "SELL" if rec >= 3.2 else "HOLD"
            st.markdown(f"<div class='ki-badge' style='border-color:{color}; color:{color};'>KI-RATING: {label}</div>", unsafe_allow_html=True)

        # --- CHART ---
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name="Kurs"), row=1, col=1)
        
        # --- CHECKBOXEN UNTER CHART MIT TOOLTIP ---
        st.write("---")
        cb1, cb2, cb3 = st.columns(3)
        s50 = cb1.checkbox("SMA 50", help="Gleitender Durchschnitt der letzten 50 Tage. Zeigt den kurzfristigen Trend.")
        s200 = cb2.checkbox("SMA 200", help="Langfristiger Trend-Indikator. Kurs darüber = Bullish, Kurs darunter = Bearish.")
        rsi_on = cb3.checkbox("RSI", value=True, help="Relative Strength Index: Über 70 = Überkauft (Vorsicht), Unter 30 = Überverkauft (Chance).")

        if s50:
            sma50 = full_hist['Close'].rolling(50).mean().tail(len(hist))
            fig.add_trace(go.Scatter(x=hist.index, y=sma50, name="SMA 50", line=dict(color='#00d1ff')), row=1, col=1)
        if s200:
            sma200 = full_hist['Close'].rolling(200).mean().tail(len(hist))
            fig.add_trace(go.Scatter(x=hist.index, y=sma200, name="SMA 200", line=dict(color='#ff4b4b')), row=1, col=1)
        if rsi_on:
            rsi_vals = calculate_rsi(full_hist).tail(len(hist))
            fig.add_trace(go.Scatter(x=hist.index, y=rsi_vals, name="RSI", line=dict(color='#bb86fc')), row=2, col=1)
            fig.add_hrect(y0=70, y1=100, fillcolor="red", opacity=0.1, row=2, col=1)
            fig.add_hrect(y0=0, y1=30, fillcolor="green", opacity=0.1, row=2, col=1)

        fig.update_layout(template="plotly_dark", height=450, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # --- BOTTOM ---
        st.markdown('<p class="section-header">🔍 Markt-Sentiment</p>', unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        with col_a:
            target = info.get('targetMedianPrice', 0) * eur_usd
            st.write(f"Analysten-Kursziel: **{target:.2f} €**")
            risk = st.number_input("Dein Risiko in €", value=100)
            st.caption("Berechnung basiert auf einem fiktiven 10% Stop-Loss vom aktuellen Kurs.")
        with col_b:
            for n in ticker.news[:3]:
                st.markdown(f"• [{n['title']}]({n['link']})")

        st.write("---")
        sec = st.radio("Sektor-Scanner (KI Strong Buys):", ["Tech/KI", "Verteidigung", "Energie", "Pharma"], horizontal=True)
        st.dataframe(get_ki_strong_buys(sec, eur_usd), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Fehler: {e}")
