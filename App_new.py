import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. KI-ANALYSE FUNKTION ---
def get_ki_analysis(ticker_obj, eur_val):
    inf = ticker_obj.info
    hist_mo = ticker_obj.history(period="1mo")
    if hist_mo.empty: return "➡️", pd.DataFrame(), 50, "Keine Daten"
    
    curr_p_usd = hist_mo['Close'].iloc[-1]
    marge = inf.get('operatingMargins', 0)
    target_usd = inf.get('targetMedianPrice', curr_p_usd)
    
    # Simple Score Logik
    fund_score = 50
    reasons = []
    if marge > 0.15: fund_score += 15; reasons.append(f"Marge: {marge*100:.1f}%")
    else: fund_score -= 10; reasons.append("Margendruck")
    
    trend = "⬆️" if fund_score >= 60 else "⬇️" if fund_score <= 40 else "➡️"
    
    composition = f"**Analyse-Basis:** {', '.join(reasons)}. Basierend auf Fundamentaldaten und Analystenziel."

    # 5-Tage Prognose
    vol_std = hist_mo['Close'].pct_change().std()
    preds = []
    last_date = hist_mo.index[-1]
    for i in range(1, 6):
        drift = (target_usd - curr_p_usd) / 25 * i * (fund_score / 50)
        p_usd = curr_p_usd + drift + np.random.normal(0, vol_std * curr_p_usd)
        preds.append({
            "Datum": last_date + pd.Timedelta(days=i),
            "Zeit": f"+{i} Tag(e)", 
            "Kurs (€)": round(p_usd * eur_val, 2)
        })
    return trend, pd.DataFrame(preds), fund_score, composition

# --- 2. UI CONFIG ---
st.set_page_config(page_title="Performance Pro", layout="wide")
if 'period' not in st.session_state: st.session_state.period = '1y'

st.markdown("""
<style>
    .stButton > button { width: 100%; border-radius: 4px; height: 35px; font-weight: bold; }
    .section-header { background: linear-gradient(90deg, #00d1ff, #bb86fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.4em; font-weight: bold; margin: 10px 0; }
    .explanation-card { background: #111; padding: 15px; border-radius: 8px; border-left: 5px solid #00d1ff; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- 3. DASHBOARD ---
st.title("🛡️ StockIntelligence Performance")
query = st.text_input("Ticker Symbol:", value="AAPL").upper()
eur_usd_rate = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

try:
    ticker = yf.Ticker(query)
    info = ticker.info
    
    # Zeitachsen Buttons nebeneinander
    p_cols = st.columns(5)
    for i, (l, k) in enumerate([("1T", "1d"), ("1W", "5d"), ("1M", "1mo"), ("6M", "6mo"), ("1J", "1y")]):
        if p_cols[i].button(l, key=f"p_{k}", type="primary" if st.session_state.period == k else "secondary"):
            st.session_state.period = k
            st.rerun()

    p_map = {"1d":"1m", "5d":"5m", "1mo":"1d", "6mo":"1d", "1y":"1d"}
    hist = ticker.history(period=st.session_state.period, interval=p_map[st.session_state.period])

    if not hist.empty:
        # Währungsumrechnung
        for col in ['Open', 'High', 'Low', 'Close']: hist[col] *= eur_usd_rate

        # --- PERFORMANCE BERECHNUNG ---
        start_p = hist['Close'].iloc[0]
        end_p = hist['Close'].iloc[-1]
        diff_pct = ((end_p / start_p) - 1) * 100

        # Metrics
        m1, m2, m3, m4 = st.columns(4)
        trend, preds, score, comp_text = get_ki_analysis(ticker, eur_usd_rate)
        
        m1.metric("Kurs (€)", f"{end_p:.2f} €", f"{diff_pct:.2f} % ({st.session_state.period})")
        m2.metric("KGV", f"{info.get('forwardPE', 'N/A')}")
        m3.metric("Div (€)", f"{info.get('dividendRate', 0)*eur_usd_rate:.2f} €")
        m4.metric("KI-Trend", trend, f"Score: {score}", help=comp_text)

        # --- CANDLESTICK & VOLUMEN CHART ---
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                           row_heights=[0.7, 0.3], vertical_spacing=0.03)
        
        # 1. Candlesticks
        fig.add_trace(go.Candlestick(
            x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], 
            name="Kurs (€)", increasing_line_color='#00ff00', decreasing_line_color='#ff4b4b'
        ), row=1, col=1)
        
        # Prognose-Linie
        prog_x = [hist.index[-1]] + list(preds['Datum'])
        prog_y = [end_p] + list(preds['Kurs (€)'])
        fig.add_trace(go.Scatter(x=prog_x, y=prog_y, name="KI-Prognose", line=dict(color='#bb86fc', width=2, dash='dot')), row=1, col=1)
        
        # 2. Volumen
        colors = ['green' if hist['Close'][i] >= hist['Open'][i] else 'red' for i in range(len(hist))]
        fig.add_trace(go.Bar(x=hist.index, y=hist['Volume'], name="Volumen", marker_color=colors, opacity=0.4), row=2, col=1)

        fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)

        # --- UNTEN ---
        st.markdown('<p class="section-header">🔮 Zusammensetzung & Prognose</p>', unsafe_allow_html=True)
        cl, cr = st.columns(2)
        with cl:
            st.markdown(f"<div class='explanation-card'>{comp_text}</div>", unsafe_allow_html=True)
            st.dataframe(preds[["Zeit", "Kurs (€)"]], hide_index=True)
        with cr:
            st.write("**Risiko-Check**")
            max_v = st.number_input("Max. Risiko (€)", value=100.0)
            stop_l = st.number_input("Stop-Loss (€)", value=end_p*0.95)
            if stop_l < end_p:
                st.success(f"Menge: **{int(max_v / (end_p - stop_l))} Stück**")

except Exception as e:
    st.error(f"Fehler: {e}")
