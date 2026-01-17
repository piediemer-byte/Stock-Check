import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. ERWEITERTE KI-ANALYSE ---
def get_ki_analysis(ticker_obj, eur_val):
    inf = ticker_obj.info
    hist_mo = ticker_obj.history(period="1mo")
    if hist_mo.empty: return "➡️", pd.DataFrame(), 50, "Datenfehler"
    
    curr_p_usd = hist_mo['Close'].iloc[-1]
    
    # Fundamental-Daten
    marge = inf.get('operatingMargins', 0)
    rev_growth = inf.get('revenueGrowth', 0)
    debt_to_equity = inf.get('debtToEquity', 100) / 100
    target_usd = inf.get('targetMedianPrice', curr_p_usd)
    
    # Technischer RSI-Check
    rsi_vals = calculate_rsi(ticker_obj.history(period="3mo"))
    current_rsi = rsi_vals.iloc[-1] if not rsi_vals.empty else 50
    
    reasons = []
    fund_score = 50
    if marge > 0.15: fund_score += 15; reasons.append(f"Top Marge ({marge*100:.1f}%)")
    else: fund_score -= 10; reasons.append("Margendruck")
    if rev_growth > 0.05: fund_score += 10; reasons.append("Wachstum ok")
    if current_rsi > 70: fund_score -= 15; reasons.append("⚠️ RSI Überkauft")
    elif current_rsi < 30: fund_score += 15; reasons.append("🚀 RSI Überverkauft")

    trend = "⬆️" if fund_score >= 60 else "⬇️" if fund_score <= 40 else "➡️"
    status = "Bullish" if trend == "⬆️" else "Bearish" if trend == "⬇️" else "Neutral"
    explanation = f"{status}: {', '.join(reasons)}."

    # Prognose Simulation (in Euro)
    vol = hist_mo['Close'].pct_change().std()
    days = ["Morgen", "+2 Tage", "+3 Tage", "+4 Tage", "+5 Tage"]
    preds = []
    for i in range(1, 6):
        drift = (target_usd - curr_p_usd) / 25 * i * (fund_score / 50)
        p_usd = curr_p_usd + drift + np.random.normal(0, vol * curr_p_usd)
        preds.append({"Zeit": days[i-1], "Kurs (€)": round(p_usd * eur_val, 2)})
    
    return trend, pd.DataFrame(preds), fund_score, explanation

def calculate_rsi(data, window=14):
    if len(data) < window + 1: return pd.Series([50]*len(data))
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

# --- 2. UI CONFIG ---
st.set_page_config(page_title="AI Stock Pro Euro", layout="wide")
if 'period' not in st.session_state: st.session_state.period = '1y'

st.markdown("""
<style>
    .stHorizontalBlock { gap: 0.1rem; }
    .stButton > button { width: 100%; border-radius: 4px; height: 35px; font-size: 0.8em; }
    .section-header { background: linear-gradient(90deg, #00d1ff, #bb86fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.4em; font-weight: bold; margin: 10px 0; }
    .prog-box { background: #161b22; padding: 10px; border-radius: 8px; border-left: 5px solid #bb86fc; margin-bottom: 5px; font-size: 0.85em;}
</style>
""", unsafe_allow_html=True)

# --- 3. APP LOGIK ---
st.title("🛡️ StockIntelligence AI (Euro Edition)")
query = st.text_input("Ticker Symbol:", value="AAPL").upper()
eur_usd_rate = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

try:
    ticker = yf.Ticker(query)
    info = ticker.info
    
    # Zeitachsen Buttons
    p_cols = st.columns(5)
    for i, (l, k) in enumerate([("1T", "1d"), ("1W", "5d"), ("1M", "1mo"), ("6M", "6mo"), ("1J", "1y")]):
        if p_cols[i].button(l, key=f"p_{k}", type="primary" if st.session_state.period == k else "secondary"):
            st.session_state.period = k
            st.rerun()

    # Daten abrufen
    p_map = {"1d":"1m", "5d":"5m", "1mo":"1d", "6mo":"1d", "1y":"1d"}
    hist = ticker.history(period=st.session_state.period, interval=p_map[st.session_state.period])
    full_hist = ticker.history(period="2y")

    if not hist.empty:
        # Währungsumrechnung für den Chart-DataFrame
        for col in ['Open', 'High', 'Low', 'Close']:
            hist[col] = hist[col] * eur_usd_rate

        # KENNZAHLEN
        m1, m2, m3, m4 = st.columns(4)
        curr_eur = hist['Close'].iloc[-1]
        perf = ((hist['Close'].iloc[-1] / hist['Close'].iloc[0]) - 1) * 100
        trend, preds, score, explanation_text = get_ki_analysis(ticker, eur_usd_rate)
        
        m1.metric("Kurs (€)", f"{curr_eur:.2f} €", f"{perf:.2f} %")
        m2.metric("KGV", f"{info.get('forwardPE', 'N/A')}")
        m3.metric("Dividende (€)", f"{info.get('dividendRate', 0) * eur_usd_rate:.2f} €")
        m4.metric("KI-Trend", trend, f"Score: {score}", help=explanation_text)

        # --- CHART ---
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name="Kurs (€)"), row=1, col=1)
        
        st.write("---")
        cb1, cb2, cb3 = st.columns(3)
        s50 = cb1.checkbox("SMA 50")
        s200 = cb2.checkbox("SMA 200")
        rsi_on = cb3.checkbox("RSI", value=True)

        if s50:
            sma50 = (full_hist['Close'] * eur_usd_rate).rolling(50).mean().reindex(hist.index, method='pad')
            fig.add_trace(go.Scatter(x=hist.index, y=sma50, name="SMA 50", line=dict(color='#00d1ff', width=1.5)), row=1, col=1)
        if s200:
            sma200 = (full_hist['Close'] * eur_usd_rate).rolling(200).mean().reindex(hist.index, method='pad')
            fig.add_trace(go.Scatter(x=hist.index, y=sma200, name="SMA 200", line=dict(color='#ff4b4b', width=1.5)), row=1, col=1)

        if rsi_on:
            rsi = calculate_rsi(full_hist).reindex(hist.index, method='pad')
            fig.add_trace(go.Scatter(x=hist.index, y=rsi, name="RSI", line=dict(color='#bb86fc')), row=2, col=1)
            fig.add_hrect(y0=70, y1=100, fillcolor="red", opacity=0.1, row=2, col=1)
            fig.add_hrect(y0=0, y1=30, fillcolor="green", opacity=0.1, row=2, col=1)
            fig.update_yaxes(range=[0, 100], row=2, col=1)

        fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # --- PROGNOSE & ERLÄUTERUNG ---
        st.markdown('<p class="section-header">🔮 KI-Prognose & Analyse-Details</p>', unsafe_allow_html=True)
        c_p, c_r = st.columns(2)
        with c_p:
            st.info(f"**KI-Analyse:** {explanation_text}")
            for _, r in preds.iterrows():
                st.markdown(f"<div class='prog-box'><b>{r['Zeit']}:</b> {r['Kurs (€)']} €</div>", unsafe_allow_html=True)
        with c_r:
            st.write("**Risiko-Rechner**")
            max_v = st.number_input("Max. Risiko (€)", value=100.0)
            stop_l = st.number_input("Stop-Loss (€)", value=curr_eur*0.95)
            if stop_l < curr_eur:
                st.success(f"Menge: **{int(max_v / (curr_eur - stop_l))} Stück**")

except Exception as e:
    st.error(f"Fehler: {e}")
