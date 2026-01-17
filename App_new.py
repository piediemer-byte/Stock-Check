import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. KI-FUNKTIONEN ---
def calculate_rsi(data, window=14):
    if len(data) < window + 1: return pd.Series([50]*len(data))
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=3600)
def live_ki_sector_scan(sector_key, eur_val):
    sector_pool = {
        "Tech/KI": ["NVDA", "MSFT", "GOOGL", "AMD", "ASML", "TSM", "AVGO", "PLTR"],
        "Verteidigung": ["LMT", "RTX", "NOC", "RHM.DE", "HENS.DE", "LHX"],
        "Energie": ["XOM", "CVX", "SHEL", "BP", "RWE.DE", "EON.DE"],
        "Pharma": ["PFE", "JNJ", "ABBV", "LLY", "NVO", "BAYN.DE"]
    }
    candidates = sector_pool.get(sector_key, [])
    results = []
    for s in candidates:
        try:
            t = yf.Ticker(s)
            info = t.info
            pe = info.get('forwardPE') or info.get('trailingPE')
            if pe and pe > 45: continue
            rec = info.get('recommendationMean', 3.0)
            if rec > 2.5: continue
            price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
            results.append({
                "Symbol": s, "Name": info.get('shortName', s),
                "Preis (€)": round(price * eur_val, 2), "KGV": round(pe, 1) if pe else "N/A",
                "Div (%)": round((info.get('dividendYield', 0) or 0)*100, 2), "Rating": rec
            })
        except: continue
    return pd.DataFrame(results).sort_values(by="Rating")

# --- 2. LAYOUT & CONFIG ---
st.set_page_config(page_title="StockIntelligence Ultra", layout="wide")
if 'period' not in st.session_state: st.session_state.period = '1y'

st.markdown("""
<style>
    .section-header { background: linear-gradient(90deg, #00d1ff, #bb86fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.8em; font-weight: bold; margin: 20px 0; border-bottom: 1px solid #333; }
    .metric-container { background: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #333; }
</style>
""", unsafe_allow_html=True)

# --- 3. ANALYSE-LOGIK ---
st.title("🛡️ StockIntelligence Pro: All-in-One")
search_query = st.text_input("Ticker eingeben (z.B. AAPL, RHM.DE):", value="AAPL").upper()
eur_usd = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

try:
    ticker = yf.Ticker(search_query)
    info = ticker.info
    
    # --- KENNZAHLEN-LEISTE ---
    st.markdown('<p class="section-header">📊 Aktuelle Kennzahlen</p>', unsafe_allow_html=True)
    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
    
    # Daten holen
    hist_all = ticker.history(period="2y")
    curr_p = hist_all['Close'].iloc[-1]
    pe_val = info.get('forwardPE') or info.get('trailingPE', 'N/A')
    div_val = (info.get('dividendYield', 0) or 0) * 100
    marge_val = (info.get('profitMargins', 0) or 0) * 100

    m_col1.metric("Kurs (€)", f"{curr_p * eur_usd:.2f} €")
    m_col2.metric("KGV", f"{pe_val}")
    m_col3.metric("Dividende", f"{div_val:.2f} %")
    m_col4.metric("Gewinnmarge", f"{marge_val:.1f} %")
    
    rec_val = info.get('recommendationMean', 3.0)
    with m_col5:
        if rec_val <= 2.2: st.markdown("### 👍 <span style='color:green;font-size:0.6em;'>BUY</span>", unsafe_allow_html=True)
        elif rec_val >= 3.2: st.markdown("### 👎 <span style='color:red;font-size:0.6em;'>SELL</span>", unsafe_allow_html=True)
        else: st.markdown("### ✊ <span style='color:orange;font-size:0.6em;'>HOLD</span>", unsafe_allow_html=True)

    # --- ZEITACHSEN ---
    t_cols = st.columns(8)
    periods = {"1T":"1d", "1W":"5d", "1M":"1mo", "6M":"6mo", "1J":"1y"}
    for i, (label, p_key) in enumerate(periods.items()):
        if t_cols[i].button(label, key=f"t_{p_key}", type="primary" if st.session_state.period == p_key else "secondary"):
            st.session_state.period = p_key
            st.rerun()

    # Chart Daten
    p_map = {"1d":"1m", "5d":"5m", "1mo":"1d", "6mo":"1d", "1y":"1d"}
    plot_df = ticker.history(period=st.session_state.period, interval=p_map[st.session_state.period])
    
    # --- CHART ---
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name="Kurs"), row=1, col=1)
    
    # Platzhalter für SMAs (werden über Checkboxen gesteuert)
    fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
    
    # --- CHECKBOXEN UNTER DEM CHART ---
    c_box1, c_box2, c_box3 = st.columns(3)
    s50 = c_box1.checkbox("SMA 50 (Trend kurz)")
    s200 = c_box2.checkbox("SMA 200 (Trend lang)")
    show_rsi = c_box3.checkbox("RSI Oszillator anzeigen", value=True)

    if s50:
        sma50 = hist_all['Close'].rolling(50).mean().tail(len(plot_df))
        fig.add_trace(go.Scatter(x=plot_df.index, y=sma50, name="SMA 50", line=dict(color='#00d1ff')), row=1, col=1)
    if s200:
        sma200 = hist_all['Close'].rolling(200).mean().tail(len(plot_df))
        fig.add_trace(go.Scatter(x=plot_df.index, y=sma200, name="SMA 200", line=dict(color='#ff4b4b')), row=1, col=1)
    if show_rsi:
        rsi_vals = calculate_rsi(hist_all).tail(len(plot_df))
        fig.add_trace(go.Scatter(x=plot_df.index, y=rsi_vals, name="RSI", line=dict(color='#bb86fc')), row=2, col=1)
        fig.add_hrect(y0=70, y1=100, fillcolor="red", opacity=0.1, row=2, col=1)
        fig.add_hrect(y0=0, y1=30, fillcolor="green", opacity=0.1, row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)

    # --- NEWS & PROGNOSEN ---
    st.markdown('<p class="section-header">🔍 Markt-Sentiment & News</p>', unsafe_allow_html=True)
    nl, nr = st.columns(2)
    with nl:
        st.subheader("Kursziel & Prognose")
        target = info.get('targetMedianPrice', 0) * eur_usd
        st.write(f"Analysten-Ziel: **{target:.2f} €**")
        risk = st.number_input("Dein Risiko (€)", value=100)
        stop = st.number_input("Stop-Loss (€)", value=curr_p * eur_usd * 0.9)
        if (curr_p * eur_usd) > stop:
            st.success(f"Empfohlene Menge: **{int(risk/((curr_p*eur_usd)-stop))} Stück**")
    with nr:
        st.subheader("Aktuelle News")
        for n in ticker.news[:3]:
            st.write(f"🔗 [{n['title']}]({n['link']})")

    # --- KI SEKTOR SCAN ---
    st.markdown('<p class="section-header">✨ KI-Sektor Empfehlungen (Live-Scan)</p>', unsafe_allow_html=True)
    sel_sec = st.radio("Sektor wählen:", ["Tech/KI", "Verteidigung", "Energie", "Pharma"], horizontal=True)
    scan_res = live_ki_sector_scan(sel_sec, eur_usd)
    st.dataframe(scan_res, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Fehler beim Laden: {e}")
