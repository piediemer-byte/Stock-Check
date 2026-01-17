import streamlit as st
import yfinance as yf
import pandas as pd

# --- 1. ERWEITERTE KI-ENGINE ---
def calculate_rsi(data, window=14):
    if len(data) < window + 1: return 50
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / (loss + 1e-9)
    return (100 - (100 / (1 + rs))).iloc[-1]

def get_ki_verdict(ticker_obj):
    inf = ticker_obj.info
    hist = ticker_obj.history(period="1y")
    if len(hist) < 200: return "➡️ Neutral", "Zu wenig Daten für SMA-Check."
    
    curr_p = float(hist['Close'].iloc[-1])
    # SMA Linien
    s50 = float(hist['Close'].rolling(50).mean().iloc[-1])
    s200 = float(hist['Close'].rolling(200).mean().iloc[-1])
    
    # Fundamentaldaten (Bilanz & Vermögen)
    marge = inf.get('operatingMargins', 0)
    cash = inf.get('totalCash', 0)
    debt = inf.get('totalDebt', 0)
    kgv = inf.get('forwardPE', 0)
    
    # Prognosen
    target = inf.get('targetMedianPrice', curr_p)
    upside = (target / curr_p - 1) * 100
    
    score = 50
    reasons = []
    
    # A. Technische Analyse (SMA)
    if curr_p > s50 and s50 > s200:
        score += 15; reasons.append("🚀 Golden Setup: Kurs > SMA 50 > SMA 200.")
    elif curr_p < s200:
        score -= 10; reasons.append("📉 Trend-Warnung: Kurs unter SMA 200.")

    # B. Fundamentalanalyse (Bilanz/Vermögen)
    if cash > debt:
        score += 10; reasons.append("💰 Vermögen: Mehr Cash als Schulden (Net-Cash).")
    if marge > 0.15:
        score += 10; reasons.append(f"📊 Bilanz: Hohe Marge ({marge*100:.1f}%).")
    
    # C. Bewertung & Prognose
    if 0 < kgv < 18:
        score += 10; reasons.append(f"💎 KGV ({kgv:.1f}) ist attraktiv.")
    if upside > 15:
        score += 10; reasons.append(f"🎯 Prognose: Analystenziel +{upside:.1f}% Upside.")

    verdict = "🚀 STRONG BUY" if score >= 70 else ("🛑 SELL" if score <= 35 else "➡️ HOLD")
    return verdict, "\n".join(reasons)

# --- 2. UI SETUP ---
st.set_page_config(page_title="StockAI DeepAnalysis", layout="centered")
st.markdown("<style>.status-card { background: #0d1117; padding: 12px; border-radius: 10px; border-left: 5px solid #3d5afe; margin-bottom: 15px; font-size: 0.85em; white-space: pre-wrap; } .calc-box { background: #161b22; padding: 15px; border-radius: 12px; border: 1px solid #30363d; }</style>", unsafe_allow_html=True)

# --- 3. APP ---
st.title("🛡️ StockAI Intelligence")
ticker_input = st.text_input("Symbol:", value="AAPL").upper()
eur_usd_rate = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

# Zeitachsen
c1, c2, c3 = st.columns(3)
if 'p' not in st.session_state: st.session_state.p = '1mo'
if c1.button("1T"): st.session_state.p = '1d'
if c2.button("1W"): st.session_state.p = '5d'
if c3.button("1M"): st.session_state.p = '1mo'

try:
    ticker = yf.Ticker(ticker_input)
    hist_p = ticker.history(period=st.session_state.p)
    
    if not hist_p.empty:
        curr_usd = hist_p['Close'].iloc[-1]
        curr_eur = curr_usd * eur_usd_rate
        # Prozentuale Entwicklung für den Zeitraum
        perf = ((curr_usd / hist_p['Close'].iloc[0]) - 1) * 100
        
        # Header Metrics mit Zeitachsen-Performance
        m1, m2 = st.columns(2)
        m1.metric("Kurs (€)", f"{curr_eur:.2f} €", f"{perf:.2f}%")
        m2.metric("Kurs ($)", f"{curr_usd:.2f} $")
        
        # KI-Analyse
        verdict, reasons = get_ki_verdict(ticker)
        st.subheader(f"KI: {verdict}")
        st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
        
        # --- ORDER & PROFIT PLANER ---
        st.subheader("🛡️ Order- & Profit-Planer")
        with st.container():
            st.markdown("<div class='calc-box'>", unsafe_allow_html=True)
            invest = st.number_input("Investment (€)", value=1000.0, step=100.0)
            
            col_l, col_r = st.columns(2)
            risk_pct = col_l.number_input("Stop-Loss (%)", value=5.0)
            target_pct = col_r.number_input("Take-Profit (%)", value=15.0)
            
            stücke = int(invest // curr_eur)
            eff_invest = stücke * curr_eur
            sl_preis = curr_eur * (1 - (risk_pct / 100))
            tp_preis = curr_eur * (1 + (target_pct / 100))
            
            crv = target_pct / risk_pct if risk_pct > 0 else 0
            
            st.divider()
            st.write(f"📊 **{stücke} Stück** | **Effektives Invest:** {eff_invest:.2f} €")
            st.error(f"📍 **STOP-LOSS:** {sl_preis:.2f} €")
            st.success(f"🎯 **TAKE-PROFIT:** {tp_preis:.2f} €")
            st.info(f"⚖️ **CRV:** {crv:.2f}")
            st.markdown("</div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Fehler: {e}")
