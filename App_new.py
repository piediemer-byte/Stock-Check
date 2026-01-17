import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. KI-FUNKTIONEN (LIVE-SCAN MIT KGV-FILTER) ---
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
        "Tech/KI": ["NVDA", "MSFT", "GOOGL", "AMD", "ASML", "TSM", "AVGO", "PLTR", "ORCL"],
        "Verteidigung": ["LMT", "RTX", "NOC", "GD", "RHM.DE", "HENS.DE", "BAESY", "LHX", "SAFR.PA"],
        "Energie": ["XOM", "CVX", "SHEL", "BP", "TTE", "RWE.DE", "EON.DE", "NEE", "ENGI.PA"],
        "Pharma": ["PFE", "JNJ", "ABBV", "LLY", "NVO", "MRK", "AZN", "GSK", "BAYN.DE"]
    }
    
    candidates = sector_pool.get(sector_key, [])
    results = []
    
    for s in candidates:
        try:
            t = yf.Ticker(s)
            info = t.info
            
            # 1. Fundamentaler Check (KGV)
            pe_ratio = info.get('forwardPE') or info.get('trailingPE')
            if pe_ratio and pe_ratio > 45: continue # Zu teure Aktien aussortieren
            
            # 2. Analysten Check
            rec = info.get('recommendationMean', 3.0)
            if rec > 2.4: continue # Nur klare Kaufempfehlungen
            
            price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
            target = info.get('targetMedianPrice', price)
            upside = ((target / price) - 1) * 100 if price > 0 else 0
            
            # 3. Technischer Check
            hist = t.history(period="1mo")
            rsi = calculate_rsi(hist).iloc[-1]
            
            results.append({
                "Symbol": s,
                "Name": info.get('shortName', s),
                "Preis (€)": round(price * eur_val, 2),
                "KGV": round(pe_ratio, 1) if pe_ratio else "N/A",
                "Upside": round(upside, 1),
                "RSI": round(rsi, 1),
                "Rating": rec,
                "Status": "🔥 Top Pick" if rec <= 1.8 and upside > 15 else "Kaufen"
            })
        except: continue
    
    return pd.DataFrame(results).sort_values(by="Rating")

# --- 2. LAYOUT & STYLING ---
st.set_page_config(page_title="KI Stock Intelligence Pro", layout="wide")
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .section-header { background: linear-gradient(90deg, #00d1ff, #bb86fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.8em; font-weight: bold; margin: 25px 0 10px 0; border-bottom: 1px solid #333; }
    .thumb-box { background: #161b22; padding: 20px; border-radius: 15px; border: 1px solid #333; text-align: center; }
    .news-card { background: #1c2128; padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #bb86fc; font-size: 0.9em; }
</style>
""", unsafe_allow_html=True)

# --- 3. DASHBOARD ---
st.title("🛡️ KI Stock Intelligence: Expert Mode")
search_query = st.text_input("Ticker analysieren:", value="AAPL").upper()
eur_usd = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

try:
    ticker = yf.Ticker(search_query)
    df = ticker.history(period="1y")
    info = ticker.info
    curr_p_eur = df['Close'].iloc[-1] * eur_usd

    # SIDEBAR TOOLS
    st.sidebar.header("Chart Analyse")
    show_rsi = st.sidebar.checkbox("RSI Oszillator", value=True)
    show_sma50 = st.sidebar.checkbox("SMA 50 (Blau)")
    show_sma200 = st.sidebar.checkbox("SMA 200 (Rot)")

    # TOP LEISTE
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        st.subheader(f"{info.get('longName', search_query)}")
        st.write(f"Sektor: {info.get('sector', 'N/A')} | Branche: {info.get('industry', 'N/A')}")
    
    with c2:
        st.metric("Preis (€)", f"{curr_p_eur:.2f} €", f"{((df['Close'].iloc[-1]/df['Close'].iloc[-2])-1)*100:.2f}%")
    
    with c3:
        rec_val = info.get('recommendationMean', 3.0)
        if rec_val <= 2.2:
            st.markdown("<div class='thumb-box'><h2 style='margin:0;'>👍</h2><span style='color:#00ff00'>KAUFEN</span></div>", unsafe_allow_html=True)
        elif rec_val >= 3.2:
            st.markdown("<div class='thumb-box'><h2 style='margin:0;'>👎</h2><span style='color:#ff4b4b'>MEIDEN</span></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='thumb-box'><h2 style='margin:0;'>✊</h2><span style='color:orange'>HALTEN</span></div>", unsafe_allow_html=True)

    # CHART
    fig = make_subplots(rows=2 if show_rsi else 1, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3] if show_rsi else [1], vertical_spacing=0.05)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Kurs"), row=1, col=1)
    if show_sma50: fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(50).mean(), name="SMA 50", line=dict(color='#00d1ff')), row=1, col=1)
    if show_sma200: fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(200).mean(), name="SMA 200", line=dict(color='#ff4b4b')), row=1, col=1)
    if show_rsi:
        fig.add_trace(go.Scatter(x=df.index, y=calculate_rsi(df), name="RSI", line=dict(color='#bb86fc')), row=2, col=1)
        fig.add_hrect(y0=70, y1=100, fillcolor="red", opacity=0.1, row=2, col=1)
        fig.add_hrect(y0=0, y1=30, fillcolor="green", opacity=0.1, row=2, col=1)
    fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig, use_container_width=True)

    # UNTERER BEREICH: PROGNOSEN & NEWS
    st.markdown('<p class="section-header">🔍 Prognosen & Marktsentiment</p>', unsafe_allow_html=True)
    cl, cr = st.columns(2)
    with cl:
        st.subheader("Kursziele & Risiko")
        t_med = info.get('targetMedianPrice', 0) * eur_usd
        st.write(f"Analysten-Ziel: **{t_med:.2f} €** (+{((t_med/curr_p_eur)-1)*100:.1f}%)")
        risk = st.number_input("Dein Risiko (€)", value=100)
        stop = st.number_input("Stop-Loss (€)", value=curr_p_eur * 0.90)
        if curr_p_eur > stop:
            st.info(f"Empfohlene Menge: **{int(risk/(curr_p_eur-stop))} Aktien**")

    with cr:
        st.subheader("Live Newsfeed")
        for n in ticker.news[:4]:
            st.markdown(f"<div class='news-card'><a href='{n['link']}' target='_blank' style='color:#00d1ff; text-decoration:none;'>{n['title']}</a></div>", unsafe_allow_html=True)

    # KI SEKTOR-SCANNER
    st.markdown('<p class="section-header">✨ KI-Sektor-Scouts (Live-Analyse)</p>', unsafe_allow_html=True)
    sel_sector = st.radio("Sektor live filtern:", ["Tech/KI", "Verteidigung", "Energie", "Pharma"], horizontal=True)
    with st.spinner("KI filtert nach Bewertung (KGV) und Empfehlungen..."):
        scan = live_ki_sector_scan(sel_sector, eur_usd)
        if not scan.empty:
            st.dataframe(scan, use_container_width=True, hide_index=True)
        else:
            st.info("Aktuell keine Aktien mit gutem KGV und Kauf-Rating in diesem Sektor gefunden.")

except Exception as e:
    st.error(f"Fehler: {e}")
