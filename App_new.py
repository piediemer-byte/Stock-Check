import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. ERWEITERTE KI-ANALYSE (FUNDAMENTAL + RSI) ---
def get_ki_analysis(ticker_obj, eur_val):
    inf = ticker_obj.info
    hist = ticker_obj.history(period="1mo")
    if hist.empty: return "➡️", pd.DataFrame(), 50, "Keine Daten"
    
    curr_p = hist['Close'].iloc[-1]
    
    # Fundamental-Check
    marge = inf.get('operatingMargins', 0)
    rev_growth = inf.get('revenueGrowth', 0)
    debt_to_equity = inf.get('debtToEquity', 100) / 100
    target = inf.get('targetMedianPrice', curr_p)
    
    # Technischer RSI-Check
    rsi_vals = calculate_rsi(ticker_obj.history(period="3mo"))
    current_rsi = rsi_vals.iloc[-1] if not rsi_vals.empty else 50
    
    # Score & Begründung
    reasons = []
    fund_score = 50
    
    # Bewertung Bilanz
    if marge > 0.15: fund_score += 15; reasons.append(f"Top Marge ({marge*100:.1f}%)")
    else: fund_score -= 10; reasons.append("Margendruck")
        
    if rev_growth > 0.05: fund_score += 10; reasons.append("Wachstum ok")
    
    # Bewertung RSI (Technik)
    if current_rsi > 70:
        fund_score -= 15
        reasons.append(f"⚠️ Überkauft (RSI: {current_rsi:.1f})")
    elif current_rsi < 30:
        fund_score += 15
        reasons.append(f"🚀 Überverkauft (RSI: {current_rsi:.1f})")
    else:
        reasons.append(f"RSI neutral ({current_rsi:.1f})")

    # Trend-Logik
    if fund_score >= 65 and target > curr_p:
        trend = "⬆️"
        status = "BULLISH: Bilanz & Technik signalisieren Stärke."
    elif fund_score <= 35:
        trend = "⬇️"
        status = "BEARISH: Warnsignale bei Bilanz oder Überhitzung."
    else:
        trend = "➡️"
        status = "NEUTRAL: Abwarten empfohlen."

    full_reason = f"{status} Details: {', '.join(reasons)}."

    # 5-Tage Prognose Simulation
    volatility = hist['Close'].pct_change().std()
    days = ["Morgen", "In 2 Tagen", "In 3 Tagen", "In 4 Tagen", "In 5 Tagen"]
    predictions = []
    for i in range(1, 6):
        # Drift korrigiert durch Fund-Score und RSI-Druck
        drift = (target - curr_p) / 25 * i * (fund_score / 50)
        pred_p = curr_p + drift + np.random.normal(0, volatility * curr_p)
        predictions.append({"Zeit": days[i-1], "Kurs (€)": round(pred_p * eur_val, 2)})
    
    return trend, pd.DataFrame(predictions), fund_score, full_reason

def calculate_rsi(data, window=14):
    if len(data) < window + 1: return pd.Series([50]*len(data))
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

# --- 2. UI & LAYOUT ---
st.set_page_config(page_title="AI Stock Analyst", layout="wide")
if 'period' not in st.session_state: st.session_state.period = '1y'

st.markdown("""
<style>
    .stHorizontalBlock { gap: 0.1rem; }
    .stButton > button { width: 100%; border-radius: 4px; font-size: 0.8em; height: 35px; }
    .section-header { background: linear-gradient(90deg, #00d1ff, #bb86fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.4em; font-weight: bold; margin: 10px 0; }
    .prog-box { background: #161b22; padding: 10px; border-radius: 8px; border-left: 5px solid #bb86fc; margin-bottom: 5px; font-size: 0.85em;}
</style>
""", unsafe_allow_html=True)

# --- 3. DASHBOARD ---
st.title("🛡️ StockIntelligence AI")
query = st.text_input("Ticker eingeben:", value="AAPL").upper()
eur_usd = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

try:
    ticker = yf.Ticker(query)
    info = ticker.info
    
    # Zeitachsen Buttons (Mobile optimized)
    p_cols = st.columns(5)
    for i, (lab, pk) in enumerate([("1T", "1d"), ("1W", "5d"), ("1M", "1mo"), ("6M", "6mo"), ("1J", "1y")]):
        if p_cols[i].button(lab, key=f"p_{pk}", type="primary" if st.session_state.period == pk else "secondary"):
            st.session_state.period = pk
            st.rerun()

    hist = ticker.history(period=st.session_state.period)
    full_hist = ticker.history(period="2y")

    if not hist.empty:
        st.markdown('<p class="section-header">📊 Kennzahlen & KI-Check</p>', unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        end_p = hist['Close'].iloc[-1]
        perf = ((end_p / hist['Close'].iloc[0]) - 1) * 100
        
        m1.metric("Preis (€)", f"{end_p * eur_usd:.2f} €", f"{perf:.2f} %")
        m2.metric("KGV (Fwd)", f"{info.get('forwardPE', 'N/A')}", help="KGV basierend auf Prognosen.")
        m3.metric("Div/Aktie (€)", f"{info.get('dividendRate', 0) * eur_usd:.2f} €", help="Auszahlung pro Aktie.")
        
        # KI Analyse mit Tooltip
        trend, predictions, score, reason_text = get_ki_analysis(ticker, eur_usd)
        with m4:
            st.metric("KI-Trend", trend, f"Score: {score}", help=reason_text)

        # Chart Sektion
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name="Kurs"), row=1, col=1)
        
        st.write("---")
        cb1, cb2, cb3 = st.columns(3)
        s50 = cb1.checkbox("SMA 50")
        s200 = cb2.checkbox("SMA 200")
        rsi_on = cb3.checkbox("RSI", value=True)

        if s50: fig.add_trace(go.Scatter(x=hist.index, y=full_hist['Close'].rolling(50).mean().tail(len(hist)), name="SMA 50", line=dict(color='#00d1ff')), row=1, col=1)
        if s200: fig.add_trace(go.Scatter(x=hist.index, y=full_hist['Close'].rolling(200).mean().tail(len(hist)), name="SMA 200", line=dict(color='#ff4b4b')), row=1, col=1)
        if rsi_on:
            fig.add_trace(go.Scatter(x=hist.index, y=calculate_rsi(full_hist).tail(len(hist)), name="RSI", line=dict(color='#bb86fc')), row=2, col=1)
            fig.add_hrect(y0=70, y1=100, fillcolor="red", opacity=0.1, row=2, col=1); fig.add_hrect(y0=0, y1=30, fillcolor="green", opacity=0.1, row=2, col=1)

        fig.update_layout(template="plotly_dark", height=400, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # Prognose & Risiko
        st.markdown('<p class="section-header">🔮 KI-Prognose & Risiko</p>', unsafe_allow_html=True)
        c_p, c_r = st.columns(2)
        with c_p:
            st.caption(f"Begründung: {reason_text}")
            for _, r in predictions.iterrows():
                st.markdown(f"<div class='prog-box'><b>{r['Zeit']}:</b> {r['Kurs (€)']} €</div>", unsafe_allow_html=True)
        with c_r:
            st.write("**Risiko-Rechner**")
            max_v = st.number_input("Verlustlimit (€)", value=100.0)
            stop_l = st.number_input("Stop-Loss bei (€)", value=(end_p*eur_usd)*0.95)
            if stop_l < (end_p*eur_usd):
                shares = int(max_v / ((end_p*eur_usd) - stop_l))
                st.success(f"Empfohlene Menge: **{shares} Stück**\nInvest: {shares*(end_p*eur_usd):.2f} €")

except Exception as e:
    st.error(f"Fehler: {e}")
