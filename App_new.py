import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. KI-FUNKTIONEN (DYNAMISCHER STRONG BUY SCAN) ---
def calculate_rsi(data, window=14):
    if len(data) < window + 1: return pd.Series([50]*len(data))
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=3600)
def get_ki_strong_buys(sector_key, eur_val):
    sector_pool = {
        "Tech/KI": ["NVDA", "MSFT", "GOOGL", "AMD", "ASML", "TSM", "AVGO", "PLTR", "SAP.DE"],
        "Verteidigung": ["LMT", "RTX", "NOC", "RHM.DE", "HENS.DE", "BA.L", "SAFR.PA"],
        "Energie": ["XOM", "CVX", "SHEL", "BP", "RWE.DE", "EON.DE", "NEE"],
        "Pharma": ["PFE", "JNJ", "ABBV", "LLY", "NVO", "BAYN.DE", "SANO.PA"]
    }
    candidates = sector_pool.get(sector_key, [])
    results = []
    
    for s in candidates:
        try:
            t = yf.Ticker(s)
            info = t.info
            # KI-Filter: Strong Buy Rating (<= 2.0) & KGV < 45
            rec = info.get('recommendationMean', 3.0)
            pe = info.get('forwardPE') or info.get('trailingPE')
            
            if rec <= 2.2 and (pe is None or pe < 45):
                price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
                div_yield = (info.get('dividendYield', 0) or 0) * 100
                div_amt = info.get('dividendRate', 0) # Jährliche Auszahlung pro Aktie
                
                results.append({
                    "Symbol": s,
                    "Name": info.get('shortName', s),
                    "Preis (€)": round(price * eur_val, 2),
                    "Div/Aktie (€)": round(div_amt * eur_val, 2) if div_amt else 0.0,
                    "Rendite (%)": round(div_yield, 2),
                    "KGV": round(pe, 1) if pe else "N/A",
                    "KI-Rating": "🔥 Strong Buy" if rec <= 1.7 else "✅ Buy"
                })
        except: continue
    return pd.DataFrame(results).sort_values(by="Preis (€)")

# --- 2. LAYOUT & CONFIG ---
st.set_page_config(page_title="StockIntelligence AI Pro", layout="wide")
if 'period' not in st.session_state: st.session_state.period = '1y'

st.markdown("""
<style>
    .section-header { background: linear-gradient(90deg, #00d1ff, #bb86fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.8em; font-weight: bold; margin: 20px 0; border-bottom: 1px solid #333; }
    .metric-card { background: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #333; text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- 3. DASHBOARD LOGIK ---
st.title("🚀 KI Stock Intelligence Pro")
search_query = st.text_input("Aktie suchen:", value="AAPL").upper()
eur_usd = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

try:
    ticker = yf.Ticker(search_query)
    info = ticker.info
    hist_2y = ticker.history(period="2y")
    curr_p = hist_2y['Close'].iloc[-1]
    
    # --- KENNZAHLEN ---
    st.markdown('<p class="section-header">📊 Kennzahlen & Live-Check</p>', unsafe_allow_html=True)
    k1, k2, k3, k4, k5 = st.columns(5)
    
    pe_ratio = info.get('forwardPE') or info.get('trailingPE', 'N/A')
    div_per_share = info.get('dividendRate', 0) # Auszahlung in USD
    div_yield = (info.get('dividendYield', 0) or 0) * 100
    
    k1.metric("Preis (€)", f"{curr_p * eur_usd:.2f} €")
    k2.metric("KGV", f"{pe_ratio}")
    k3.metric("Div/Aktie (€)", f"{div_per_share * eur_usd:.2f} €")
    k4.metric("Rendite (%)", f"{div_yield:.2f} %")
    
    with k5:
        rec_val = info.get('recommendationMean', 3.0)
        if rec_val <= 2.2: st.markdown("### 👍 <span style='color:#00ff00;'>BUY</span>", unsafe_allow_html=True)
        elif rec_val >= 3.2: st.markdown("### 👎 <span style='color:#ff4b4b;'>SELL</span>", unsafe_allow_html=True)
        else: st.markdown("### ✊ <span style='color:orange;'>HOLD</span>", unsafe_allow_html=True)

    # --- ZEITACHSEN & CHART ---
    t_cols = st.columns(8)
    for label, p_key in {"1T":"1d", "1W":"5d", "1M":"1mo", "6M":"6mo", "1J":"1y"}.items():
        if t_cols[list({"1T":"1d", "1W":"5d", "1M":"1mo", "6M":"6mo", "1J":"1y"}.keys()).index(label)].button(label):
            st.session_state.period = p_key
            st.rerun()

    p_map = {"1d":"1m", "5d":"5m", "1mo":"1d", "6mo":"1d", "1y":"1d"}
    plot_df = ticker.history(period=st.session_state.period, interval=p_map[st.session_state.period])
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name="Kurs"), row=1, col=1)
    fig.update_layout(template="plotly_dark", height=450, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig, use_container_width=True)

    # --- SMA & RSI CHECKBOXEN (UNTER CHART) ---
    st.write("---")
    cb1, cb2, cb3 = st.columns(3)
    s50 = cb1.checkbox("SMA 50 (Blau)")
    s200 = cb2.checkbox("SMA 200 (Rot)")
    show_rsi = cb3.checkbox("RSI Oszillator", value=True)

    # Indikatoren hinzufügen falls gewählt
    if s50:
        sma50 = hist_2y['Close'].rolling(50).mean().tail(len(plot_df))
        fig.add_trace(go.Scatter(x=plot_df.index, y=sma50, name="SMA 50", line=dict(color='#00d1ff')), row=1, col=1)
    if s200:
        sma200 = hist_2y['Close'].rolling(200).mean().tail(len(plot_df))
        fig.add_trace(go.Scatter(x=plot_df.index, y=sma200, name="SMA 200", line=dict(color='#ff4b4b')), row=1, col=1)
    if show_rsi:
        rsi = calculate_rsi(hist_2y).tail(len(plot_df))
        fig.add_trace(go.Scatter(x=plot_df.index, y=rsi, name="RSI", line=dict(color='#bb86fc')), row=2, col=1)
        fig.add_hrect(y0=70, y1=100, fillcolor="red", opacity=0.1, row=2, col=1)
        fig.add_hrect(y0=0, y1=30, fillcolor="green", opacity=0.1, row=2, col=1)
    
    if s50 or s200 or show_rsi: st.rerun() # Chart Refresh bei Klick

    # --- UNTERER BEREICH: NEWS & PROGNOSEN ---
    st.markdown('<p class="section-header">🔍 Markt-Insights & News</p>', unsafe_allow_html=True)
    cl, cr = st.columns(2)
    with cl:
        st.subheader("Kursziele & Prognosen")
        target = info.get('targetMedianPrice', 0) * eur_usd
        st.write(f"Zentrales Analystenziel: **{target:.2f} €**")
        risk = st.number_input("Dein Risiko (€)", value=100)
        stop = st.number_input("Stop-Loss (€)", value=curr_p * eur_usd * 0.95)
        if (curr_p * eur_usd) > stop:
            st.success(f"Kauf-Empfehlung: **{int(risk/((curr_p*eur_usd)-stop))} Aktien**")
    with cr:
        st.subheader("Newsfeed")
        for n in ticker.news[:3]:
            st.markdown(f"🔹 [{n['title']}]({n['link']})")

    # --- KI STRONG BUY SEKTOR SCAN ---
    st.markdown('<p class="section-header">✨ KI Strong Buy Sektor-Scanner</p>', unsafe_allow_html=True)
    sel_sec = st.radio("Sektor live filtern:", ["Tech/KI", "Verteidigung", "Energie", "Pharma"], horizontal=True)
    scan_results = get_ki_strong_buys(sel_sec, eur_usd)
    if not scan_results.empty:
        st.dataframe(scan_results, use_container_width=True, hide_index=True)
    else:
        st.info("Aktuell keine 'Strong Buy' Titel mit gesundem KGV in diesem Sektor gefunden.")

except Exception as e:
    st.error(f"Fehler: {e}")
