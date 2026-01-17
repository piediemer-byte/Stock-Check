import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. ERWEITERTE KI-LOGIK (NEWS, PROGNOSEN, VOLUMEN, BILANZ) ---
def get_advanced_ki_analysis(ticker_obj, eur_val):
    inf = ticker_obj.info
    hist_1m = ticker_obj.history(period="1mo")
    if hist_1m.empty: return "➡️", 50, "Keine Daten"
    
    # --- A. BILANZ (25%) ---
    marge = inf.get('operatingMargins', 0)
    score_bilanz = 15 if marge > 0.15 else (-10 if marge < 0.05 else 0)
    
    # --- B. PROGNOSEN (25%) ---
    curr_p = hist_1m['Close'].iloc[-1]
    target = inf.get('targetMedianPrice', curr_p)
    upside = (target / curr_p) - 1
    score_prognose = 15 if upside > 0.10 else (-10 if upside < -0.05 else 5)
    
    # --- C. VOLUMEN (25%) ---
    avg_vol = hist_1m['Volume'].mean()
    curr_vol = hist_1m['Volume'].iloc[-1]
    # Positiv, wenn Volumen bei steigenden Kursen hoch ist
    score_vol = 15 if (curr_vol > avg_vol * 1.2 and hist_1m['Close'].iloc[-1] > hist_1m['Open'].iloc[-1]) else 0
    
    # --- D. NEWS SENTIMENT (25%) ---
    news = ticker_obj.news
    sentiment_score = 0
    news_titles = []
    if news:
        positive_words = ['buy', 'growth', 'upgraded', 'profit', 'beats', 'bull']
        negative_words = ['sell', 'risk', 'downsized', 'loss', 'misses', 'bear']
        for n in news[:5]: # Prüfe die letzten 5 News
            title = n['title'].lower()
            news_titles.append(n['title'])
            if any(w in title for w in positive_words): sentiment_score += 5
            if any(w in title for w in negative_words): sentiment_score -= 5
    
    # GESAMTSCORE (Start bei 50)
    total_score = 50 + score_bilanz + score_prognose + score_vol + sentiment_score
    total_score = max(0, min(100, total_score))
    
    # TREND-PFEIL
    if total_score >= 65: trend = "⬆️"
    elif total_score <= 35: trend = "⬇️"
    else: trend = "➡️"
    
    # DETAILLIERTE BEGRÜNDUNG
    details = (
        f"**KI-Zusammensetzung (Score: {total_score}):**\n"
        f"- **Bilanz:** {'Stark' if score_bilanz > 0 else 'Neutral/Schwach'}\n"
        f"- **Analysten:** Target {target:.2f} (Upside: {upside*100:.1f}%)\n"
        f"- **Volumen:** {'Auffällig hoch' if score_vol > 0 else 'Normal'}\n"
        f"- **News:** {len(news_titles)} aktuelle Meldungen analysiert."
    )
    
    return trend, total_score, details

# --- 2. APP SETUP ---
st.set_page_config(page_title="KI-Stock-Intelligence", layout="wide")
if 'period' not in st.session_state: st.session_state.period = '1y'

st.markdown("""
<style>
    .stMetric { background: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    .explanation-card { background: #0d1117; padding: 20px; border-radius: 10px; border-top: 4px solid #bb86fc; margin-top: 20px; }
    .news-box { font-size: 0.8em; color: #8b949e; margin-bottom: 5px; border-bottom: 1px solid #30363d; padding-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 3. DASHBOARD ---
st.title("🛡️ StockIntelligence AI Pro")
query = st.text_input("Ticker eingeben:", value="AAPL").upper()
eur_usd = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

try:
    ticker = yf.Ticker(query)
    info = ticker.info
    
    # Zeitachsen-Buttons
    p_cols = st.columns(5)
    for i, (l, k) in enumerate([("1T", "1d"), ("1W", "5d"), ("1M", "1mo"), ("6M", "6mo"), ("1J", "1y")]):
        if p_cols[i].button(l, key=f"btn_{k}", type="primary" if st.session_state.period == k else "secondary"):
            st.session_state.period = k
            st.rerun()

    # Daten abrufen
    hist = ticker.history(period=st.session_state.period)
    if not hist.empty:
        # Umrechnung
        hist_eur = hist.copy()
        for c in ['Open', 'High', 'Low', 'Close']: hist_eur[c] *= eur_usd
        
        # KI-Check
        trend, score, ki_details = get_advanced_ki_analysis(ticker, eur_usd)
        
        # Metrics
        m1, m2, m3, m4 = st.columns(4)
        end_p = hist_eur['Close'].iloc[-1]
        perf = ((end_p / hist_eur['Close'].iloc[0]) - 1) * 100
        
        with m1:
            st.metric("Kurs (€)", f"{end_p:.2f} €", f"{perf:.2f} %")
            st.caption(f"Original: {hist['Close'].iloc[-1]:.2f} {info.get('currency', 'USD')}")
        m2.metric("KGV (Forward)", info.get('forwardPE', 'N/A'))
        m3.metric("Marge (%)", f"{info.get('operatingMargins', 0)*100:.1f} %")
        m4.metric("KI-Trend", trend, f"Score: {score}", help=ki_details)

        # Chart
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=hist_eur.index, open=hist_eur['Open'], high=hist_eur['High'], low=hist_eur['Low'], close=hist_eur['Close'], name="Candle"), row=1, col=1)
        
        v_colors = ['green' if hist_eur['Close'][i] >= hist_eur['Open'][i] else 'red' for i in range(len(hist_eur))]
        fig.add_trace(go.Bar(x=hist_eur.index, y=hist_eur['Volume'], marker_color=v_colors, opacity=0.4, name="Volumen"), row=2, col=1)
        
        fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)

        # Erläuterung & News
        st.markdown("### 🔍 KI-Hintergrundanalyse")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"<div class='explanation-card'>{ki_details}</div>", unsafe_allow_html=True)
        with c2:
            st.write("**Aktuelle Schlagzeilen:**")
            for n in ticker.news[:3]:
                st.markdown(f"<div class='news-box'>• {n['title']}</div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Fehler: {e}")
