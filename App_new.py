import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. KI-ANALYSE MIT VOLUMEN-CHECK ---
def get_ki_analysis(ticker_obj, eur_val):
    inf = ticker_obj.info
    hist_mo = ticker_obj.history(period="1mo")
    if hist_mo.empty: return "➡️", pd.DataFrame(), 50, "Keine Daten"
    
    curr_p_usd = hist_mo['Close'].iloc[-1]
    vol_avg = hist_mo['Volume'].mean()
    curr_vol = hist_mo['Volume'].iloc[-1]
    
    # Faktoren
    marge = inf.get('operatingMargins', 0)
    rsi_vals = calculate_rsi(ticker_obj.history(period="3mo"))
    current_rsi = rsi_vals.iloc[-1] if not rsi_vals.empty else 50
    
    reasons = []
    fund_score = 50
    
    # 1. Bilanz (30%)
    if marge > 0.15: 
        fund_score += 15
        reasons.append(f"Bilanz: Stark (Marge {marge*100:.1f}%)")
    else: 
        fund_score -= 10
        reasons.append("Bilanz: Margendruck")
        
    # 2. RSI Technik (30%)
    if current_rsi > 70: fund_score -= 15; reasons.append(f"RSI: Überkauft ({current_rsi:.1f})")
    elif current_rsi < 30: fund_score += 15; reasons.append(f"RSI: Chance ({current_rsi:.1f})")
    
    # 3. NEU: Volumen-Bestätigung (40%)
    if curr_vol > vol_avg * 1.2 and hist_mo['Close'].iloc[-1] > hist_mo['Open'].iloc[-1]:
        fund_score += 15
        reasons.append("Volumen: Starker Kaufdruck")
    elif curr_vol > vol_avg * 1.2:
        fund_score -= 10
        reasons.append("Volumen: Hoher Verkaufsdruck")

    trend = "⬆️" if fund_score >= 65 else "⬇️" if fund_score <= 35 else "➡️"
    
    composition = (
        f"**KI-Analyse Zusammensetzung:**\n"
        f"- **Fundamentaldaten:** {reasons[0]}\n"
        f"- **Technik:** {reasons[1]}\n"
        f"- **Bestätigung:** {reasons[2] if len(reasons)>2 else 'Volumen neutral'}\n"
        f"- **Gesamt-Konfidenz:** {fund_score}/100"
    )

    # 5-Tage Prognose (Euro)
    vol_std = hist_mo['Close'].pct_change().std()
    target_usd = inf.get('targetMedianPrice', curr_p_usd)
    preds = []
    for i in range(1, 6):
        drift = (target_usd - curr_p_usd) / 25 * i * (fund_score / 50)
        p_usd = curr_p_usd + drift + np.random.normal(0, vol_std * curr_p_usd)
        preds.append({"Zeit": f"+{i} Tag(e)", "Kurs (€)": round(p_usd * eur_val, 2)})
    
    return trend, pd.DataFrame(preds), fund_score, composition

def calculate_rsi(data, window=14):
    if len(data) < window + 1: return pd.Series([50]*len(data))
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

# --- 2. UI CONFIG ---
st.set_page_config(page_title="StockIntelligence Pro", layout="wide")
if 'period' not in st.session_state: st.session_state.period = '1y'

st.markdown("""
<style>
    .stButton > button { width: 100%; border-radius: 4px; height: 35px; font-weight: bold; }
    .section-header { background: linear-gradient(90deg, #00d1ff, #bb86fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.4em; font-weight: bold; margin: 15px 0; }
    .explanation-card { background: #111; padding: 15px; border-radius: 8px; border-top: 3px solid #00d1ff; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- 3. DASHBOARD ---
st.title("🛡️ StockIntelligence AI")
query = st.text_input("Symbol:", value="AAPL").upper()
eur_usd_rate = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

try:
    ticker = yf.Ticker(query)
    info = ticker.info
    
    # Zeitachsen
    p_cols = st.columns(5)
    for i, (l, k) in enumerate([("1T", "1d"), ("1W", "5d"), ("1M", "1mo"), ("6M", "6mo"), ("1J", "1y")]):
        if p_cols[i].button(l, key=f"p_{pk}", type="primary" if st.session_state.period == k else "secondary"):
            st.session_state.period = k
            st.rerun()

    p_map = {"1d":"1m", "5d":"5m", "1mo":"1d", "6mo":"1d", "1y":"1d"}
    hist = ticker.history(period=st.session_state.period, interval=p_map[st.session_state.period])
    full_hist = ticker.history(period="2y")

    if not hist.empty:
        # Umrechnung
        for col in ['Open', 'High', 'Low', 'Close']: hist[col] *= eur_usd_rate

        # Metrics
        m1, m2, m3, m4 = st.columns(4)
        curr_eur = hist['Close'].iloc[-1]
        trend, preds, score, comp_text = get_ki_analysis(ticker, eur_usd_rate)
        
        m1.metric("Kurs (€)", f"{curr_eur:.2f} €")
        m2.metric("KGV", f"{info.get('forwardPE', 'N/A')}")
        m3.metric("Dividende", f"{info.get('dividendRate', 0)*eur_usd_rate:.2f} €")
        m4.metric("KI-Trend", trend, f"Score: {score}", help=comp_text)

        # --- 3-STUFIGER CHART ---
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                           row_heights=[0.5, 0.2, 0.3], vertical_spacing=0.03)
        
        # 1. Candlesticks
        fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name="Kurs"), row=1, col=1)
        
        # 2. Volumen (Balken)
        colors = ['green' if hist['Close'][i] >= hist['Open'][i] else 'red' for i in range(len(hist))]
        fig.add_trace(go.Bar(x=hist.index, y=hist['Volume'], name="Volumen", marker_color=colors, opacity=0.5), row=2, col=1)
        
        # 3. RSI
        rsi = calculate_rsi(full_hist).reindex(hist.index, method='pad')
        fig.add_trace(go.Scatter(x=hist.index, y=rsi, name="RSI", line=dict(color='#bb86fc')), row=3, col=1)
        fig.add_hrect(y0=70, y1=100, fillcolor="red", opacity=0.1, row=3, col=1)
        fig.add_hrect(y0=0, y1=30, fillcolor="green", opacity=0.1, row=3, col=1)

        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)

        # --- UNTEN ---
        st.markdown('<p class="section-header">🔮 KI-Zusammensetzung & Prognose</p>', unsafe_allow_html=True)
        cl, cr = st.columns(2)
        with cl:
            st.markdown(f"<div class='explanation-card'>{comp_text}</div>", unsafe_allow_html=True)
            st.dataframe(preds, hide_index=True)
        with cr:
            st.write("**Risiko-Check**")
            max_v = st.number_input("Verlustlimit (€)", value=100.0)
            stop_l = st.number_input("Stop-Loss (€)", value=curr_eur*0.95)
            if stop_l < curr_eur:
                st.success(f"Kaufmenge: **{int(max_v / (curr_eur - stop_l))} Stück**")

except Exception as e:
    st.error(f"Fehler: {e}")
