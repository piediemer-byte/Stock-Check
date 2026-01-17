import streamlit as st
import yfinance as yf
import pandas as pd

# --- 1. KI-ENGINE (Fokus: Technik & Fundament) ---
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
    if len(hist) < 200: return "➡️ Neutral", "Zu wenig Daten für Analyse."
    
    curr_p = float(hist['Close'].iloc[-1])
    s50 = float(hist['Close'].rolling(50).mean().iloc[-1])
    s200 = float(hist['Close'].rolling(200).mean().iloc[-1])
    rsi_val = calculate_rsi(hist)
    
    marge = inf.get('operatingMargins', 0)
    kgv = inf.get('forwardPE', 0)
    cash = inf.get('totalCash', 0)
    debt = inf.get('totalDebt', 0)
    
    score = 50
    reasons = []
    
    if curr_p > s50 and s50 > s200: score += 15; reasons.append("🚀 Golden Setup: Bullisher Trend.")
    if cash > debt: score += 10; reasons.append("💰 Net-Cash: Starke Vermögenslage.")
    if 0 < kgv < 18: score += 10; reasons.append(f"💎 KGV ({kgv:.1f}) attraktiv.")
    if rsi_val < 35: score += 15; reasons.append("📉 RSI: Überverkauft (Kaufzone).")

    verdict = "🚀 STRONG BUY" if score >= 70 else ("🛑 SELL" if score <= 35 else "➡️ HOLD")
    return verdict, "\n".join(reasons)

# --- 2. UI SETUP ---
st.set_page_config(page_title="StockAI Mobile Pro", layout="centered")
st.markdown("""
<style>
    .status-card { background: #0d1117; padding: 12px; border-radius: 10px; border-left: 5px solid #3d5afe; margin-bottom: 15px; font-size: 0.85em; white-space: pre-wrap; }
    .calc-box { background: #161b22; padding: 15px; border-radius: 12px; border: 1px solid #30363d; }
    .bear-box { background: #2d0d0d; padding: 12px; border-radius: 10px; border-left: 5px solid #ff1744; font-size: 0.85em; color: #ffcdd2; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 3. APP ---
st.title("🛡️ StockAI Intelligence")
ticker_input = st.text_input("Symbol:", value="AAPL").upper()
eur_usd_rate = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

if 'p' not in st.session_state: st.session_state.p = '1mo'
c1, c2, c3 = st.columns(3)
if c1.button("1T"): st.session_state.p = '1d'
if c2.button("1W"): st.session_state.p = '5d'
if c3.button("1M"): st.session_state.p = '1mo'

try:
    ticker = yf.Ticker(ticker_input)
    hist_p = ticker.history(period=st.session_state.p)
    
    if not hist_p.empty:
        curr_usd = hist_p['Close'].iloc[-1]
        curr_eur = curr_usd * eur_usd_rate
        perf = ((curr_usd / hist_p['Close'].iloc[0]) - 1) * 100
        
        # Kurs Metrics
        col_a, col_b = st.columns(2)
        col_a.metric("Kurs (€)", f"{curr_eur:.2f} €", f"{perf:.2f}%")
        col_b.metric("Kurs ($)", f"{curr_usd:.2f} $")
        
        # KI Analyse
        verdict, reasons = get_ki_verdict(ticker)
        st.subheader(f"KI-Urteil: {verdict}")
        st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
        
        # --- ORDER PLANER (MIT ALLEN ERGEBNISSEN) ---
        st.subheader("🛡️ Order- & Profit-Planer")
        with st.container():
            st.markdown("<div class='calc-box'>", unsafe_allow_html=True)
            invest_input = st.number_input("Gewünschtes Investment (€)", value=1000.0, step=100.0)
            
            risk_pct = st.slider("Risiko bis Stop-Loss (%)", 1.0, 20.0, 5.0)
            target_pct = st.slider("Ziel bis Take-Profit (%)", 1.0, 50.0, 15.0)
            
            # Berechnungen
            stücke = int(invest_input // curr_eur)
            reales_invest = stücke * curr_eur
            sl_preis = curr_eur * (1 - (risk_pct / 100))
            tp_preis = curr_eur * (1 + (target_pct / 100))
            
            risk_eur = reales_invest * (risk_pct / 100)
            profit_eur = reales_invest * (target_pct / 100)
            crv = target_pct / risk_pct if risk_pct > 0 else 0
            
            # Ergebnisanzeige
            st.divider()
            st.write(f"📊 **Kaufmenge:** {stücke} Stück")
            st.write(f"💰 **Effektives Investment:** {reales_invest:.2f} €")
            
            st.error(f"📍 **STOP-LOSS bei: {sl_preis:.2f} €**")
            st.write(f"📉 Risiko im Ernstfall: -{risk_eur:.2f} €")
            
            st.success(f"🎯 **TAKE-PROFIT bei: {tp_preis:.2f} €**")
            st.write(f"📈 Potenzieller Gewinn: +{profit_eur:.2f} €")
            
            st.info(f"⚖️ **Chance-Risiko-Verhältnis (CRV): {crv:.2f}**")
            st.markdown("</div>", unsafe_allow_html=True)

        # Glossar & Bearish
        st.divider()
        with st.expander("📚 Bearishe Warnsignale & Erklärung"):
            st.markdown("""
            <b>⚠️ Bearishe Warnsignale:</b>
            <div class='bear-box'>
            • <b>Death Cross:</b> SMA 50 fällt unter SMA 200.<br>
            • <b>Double Top:</b> Kurs scheitert wiederholt am Widerstand.<br>
            • <b>RSI Divergenz:</b> Kurs steigt, aber Indikator fällt bereits.
            </div>
            """, unsafe_allow_html=True)

except Exception as e:
    st.error(f"Fehler: {e}")
