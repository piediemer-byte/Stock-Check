import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. KI-ANALYSE (Logik für Erläuterung & Tabelle) ---
def get_ki_analysis(ticker_obj, eur_val):
    inf = ticker_obj.info
    hist_mo = ticker_obj.history(period="1mo")
    if hist_mo.empty: return "➡️", pd.DataFrame(), 50, "Keine Daten"
    
    curr_p_usd = hist_mo['Close'].iloc[-1]
    marge = inf.get('operatingMargins', 0)
    target_usd = inf.get('targetMedianPrice', curr_p_usd)
    currency_symbol = inf.get('currency', 'USD')
    
    fund_score = 50
    reasons = []
    if marge > 0.15: fund_score += 15; reasons.append(f"Marge: {marge*100:.1f}%")
    else: fund_score -= 10; reasons.append("Margendruck")
    
    trend = "⬆️" if fund_score >= 60 else "⬇️" if fund_score <= 40 else "➡️"
    explanation = (f"**Analyse:** Bilanz-Check ({reasons[0]}) kombiniert mit dem "
                   f"Analystenziel von {target_usd:.2f} {currency_symbol}.")

    # 5-Tage Prognose (Euro)
    vol_std = hist_mo['Close'].pct_change().std()
    preds = []
    for i in range(1, 6):
        drift = (target_usd - curr_p_usd) / 25 * i * (fund_score / 50)
        p_usd = curr_p_usd + drift + np.random.normal(0, vol_std * curr_p_usd)
        preds.append({"Zeit": f"+{i} Tag(e)", "Kurs (€)": round(p_usd * eur_val, 2)})
    return trend, pd.DataFrame(preds), fund_score, explanation

# --- 2. UI CONFIG ---
st.set_page_config(page_title="Candle Pro Multi-Currency", layout="wide")
if 'period' not in st.session_state: st.session_state.period = '1y'

st.markdown("""
<style>
    .stButton > button { width: 100%; border-radius: 4px; height: 35px; font-weight: bold; }
    .section-header { background: linear-gradient(90deg, #00d1ff, #bb86fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.4em; font-weight: bold; margin: 15px 0; }
    .explanation-card { background: #111; padding: 15px; border-radius: 8px; border-left: 5px solid #00d1ff; margin-bottom: 20px; font-size: 0.9em; }
    .original-currency { font-size: 0.85em; color: #888; margin-top: -15px; }
</style>
""", unsafe_allow_html=True)

# --- 3. APP ---
st.title("🛡️ StockIntelligence Pro")
query = st.text_input("Ticker Symbol (z.B. AAPL, TSLA, SAP.DE):", value="AAPL").upper()
eur_usd_rate = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

try:
    ticker = yf.Ticker(query)
    info = ticker.info
    currency = info.get('currency', 'USD')
    
    # Zeitachsen Buttons
    p_cols = st.columns(5)
    for i, (l, k) in enumerate([("1T", "1d"), ("1W", "5d"), ("1M", "1mo"), ("6M", "6mo"), ("1J", "1y")]):
        if p_cols[i].button(l, key=f"p_{k}", type="primary" if st.session_state.period == k else "secondary"):
            st.session_state.period = k
            st.rerun()

    p_map = {"1d":"1m", "5d":"5m", "1mo":"1d", "6mo":"1d", "1y":"1d"}
    hist_orig = ticker.history(period=st.session_state.period, interval=p_map[st.session_state.period])

    if not hist_orig.empty:
        # Kopie für Euro-Umrechnung erstellen
        hist_eur = hist_orig.copy()
        for col in ['Open', 'High', 'Low', 'Close']: hist_eur[col] *= eur_usd_rate

        # Performance-Berechnung (Euro-Basis)
        start_val = hist_eur['Close'].iloc[0]
        end_val = hist_eur['Close'].iloc[-1]
        perf_pct = ((end_val / start_val) - 1) * 100
        
        # Originalkurs für die Anzeige
        orig_price = hist_orig['Close'].iloc[-1]

        # Metrics
        m1, m2, m3, m4 = st.columns(4)
        trend, preds, score, explanation_text = get_ki_analysis(ticker, eur_usd_rate)
        
        with m1:
            st.metric("Kurs (€)", f"{end_val:.2f} €", f"{perf_pct:.2f} % ({st.session_state.period})")
            st.markdown(f"<div class='original-currency'>Original: {orig_price:.2f} {currency}</div>", unsafe_allow_html=True)
            
        m2.metric("KGV", f"{info.get('forwardPE', 'N/A')}")
        m3.metric("Dividende (€)", f"{info.get('dividendRate', 0)*eur_usd_rate:.2f} €")
        m4.metric("KI-Trend", trend, f"Score: {score}", help=explanation_text)

        # --- CANDLESTICK CHART (Euro) ---
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.03)
        
        fig.add_trace(go.Candlestick(
            x=hist_eur.index, open=hist_eur['Open'], high=hist_eur['High'], low=hist_eur['Low'], close=hist_eur['Close'], 
            name="Euro Candles", increasing_line_color='#00ff00', decreasing_line_color='#ff4b4b'
        ), row=1, col=1)
        
        vol_colors = ['#00ff00' if hist_eur['Close'][i] >= hist_eur['Open'][i] else '#ff4b4b' for i in range(len(hist_eur))]
        fig.add_trace(go.Bar(x=hist_eur.index, y=hist_eur['Volume'], name="Volumen", marker_color=vol_colors, opacity=0.4), row=2, col=1)

        fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)

        # --- UNTEN: ERLÄUTERUNG & TABELLE ---
        st.markdown('<p class="section-header">🔮 Analyse-Zusammensetzung & Prognose</p>', unsafe_allow_html=True)
        cl, cr = st.columns(2)
        with cl:
            st.markdown(f"<div class='explanation-card'>{explanation_text}</div>", unsafe_allow_html=True)
            st.dataframe(preds, hide_index=True, use_container_width=True)
        with cr:
            st.write("**Risiko-Rechner (in Euro)**")
            max_v = st.number_input("Max. Risiko (€)", value=100.0)
            stop_l = st.number_input("Stop-Loss (€)", value=end_val*0.95)
            if stop_l < end_val:
                st.success(f"Menge: **{int(max_v / (end_val - stop_l))} Stück**")

except Exception as e:
    st.error(f"Fehler: {e}")
