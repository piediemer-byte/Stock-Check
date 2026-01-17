import streamlit as st
import yfinance as yf
import pandas as pd

# --- 1. KI-ENGINE (KERN-ANALYSE) ---
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
    if len(hist) < 200: return "➡️ Neutral", "Zu wenig Daten für SMA-Analyse.", 0
    
    curr_p = float(hist['Close'].iloc[-1])
    # SMA & RSI
    s50 = float(hist['Close'].rolling(50).mean().iloc[-1])
    s200 = float(hist['Close'].rolling(200).mean().iloc[-1])
    rsi_val = calculate_rsi(hist)
    
    # Volumen Check
    avg_vol = hist['Volume'].tail(20).mean()
    curr_vol = hist['Volume'].iloc[-1]
    
    # Fundamentaldaten
    kgv = inf.get('forwardPE', 0)
    bgv = inf.get('bookValue', 0)
    kbv = curr_p / bgv if bgv and bgv > 0 else 0
    marge = inf.get('operatingMargins', 0)
    
    score = 50
    reasons = []
    
    # --- LOGIK-AUFSCHLÜSSELUNG ---
    # 1. Bilanz & Marge
    if marge > 0.15: score += 15; reasons.append(f"💰 Starke Bilanz: Marge ({marge*100:.1f}%) ist hoch.")
    # 2. Bewertung (KGV/BGV)
    if 0 < kgv < 15: score += 10; reasons.append(f"💎 KGV ({kgv:.1f}) attraktiv.")
    if 0 < kbv < 1.2: score += 10; reasons.append(f"🏢 Hoher Substanzwert (KBV: {kbv:.1f}).")
    # 3. RSI (Technik)
    if rsi_val < 35: score += 15; reasons.append(f"🚀 RSI ({rsi_val:.1f}): Überverkauft (Kaufchance).")
    elif rsi_val > 65: score -= 15; reasons.append(f"⚠️ RSI ({rsi_val:.1f}): Überhitzt.")
    # 4. Handelsvolumen
    if curr_vol > avg_vol * 1.3: score += 10; reasons.append("📊 Volumen: Starkes Interesse (Breakout-Potenzial).")

    verdict = "🚀 STRONG BUY" if score >= 65 else ("🛑 SELL" if score <= 35 else "➡️ HOLD")
    return verdict, "\n".join(reasons)

# --- 2. UI SETUP ---
st.set_page_config(page_title="StockAI Core", layout="centered")
st.markdown("<style>.status-card { background: #0d1117; padding: 12px; border-radius: 10px; border-left: 5px solid #3d5afe; margin-bottom: 15px; font-size: 0.85em; white-space: pre-wrap; } .edu-box { background: #1c1c1c; padding: 12px; border-radius: 10px; font-size: 0.8em; color: #d1d1d1; }</style>", unsafe_allow_html=True)

# --- 3. APP ---
st.title("🛡️ StockAI Intelligence")
ticker_input = st.text_input("Symbol:", value="AAPL").upper()
eur_usd_rate = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

# Zeitachsen
if 'p' not in st.session_state: st.session_state.p = '1mo'
c1, c2, c3 = st.columns(3)
if c1.button("1T"): st.session_state.p = '1d'
if c2.button("1W"): st.session_state.p = '5d'
if c3.button("1M"): st.session_state.p = '1mo'

try:
    ticker = yf.Ticker(ticker_input)
    hist_p = ticker.history(period=st.session_state.p)
    
    if not hist_p.empty:
        curr_eur = hist_p['Close'].iloc[-1] * eur_usd_rate
        perf = ((hist_p['Close'].iloc[-1] / hist_p['Close'].iloc[0]) - 1) * 100
        
        st.metric("Kurs (€)", f"{curr_eur:.2f} €", f"{perf:.2f}%")
        
        # KI-Analyse
        verdict, reasons = get_ki_verdict(ticker)
        st.subheader(f"KI: {verdict}")
        st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
        
        # RECHNER
        st.subheader("🛡️ Risiko- & Order-Planer")
        invest = st.number_input("Budget (€)", value=1000.0, step=100.0)
        risk = st.slider("Risiko (%)", 1, 15, 5)
        
        stücke = int(invest // curr_eur)
        stop_l = curr_eur * (1 - (risk/100))
        st.success(f"**{stücke} Stück** | Stop-Loss: **{stop_l:.2f} €**")

        # GLOSSAR
        st.divider()
        with st.expander("📚 Erklärung der Kennzahlen"):
            st.markdown("""<div class='edu-box'>
            <b>Bilanz (Marge):</b> Zeigt, wie viel Gewinn vom Umsatz bleibt. >15% ist exzellent.<br>
            <b>KGV:</b> Bewertung zum Gewinn. Niedrig = günstig.<br>
            <b>BGV / KBV:</b> Substanzwert. Zeigt den Wert des Firmeninventars pro Aktie.<br>
            <b>RSI:</b> Misst die Dynamik. <35 ist günstig, >65 ist teuer.<br>
            <b>Volumen:</b> Bestätigt Trends. Hohes Volumen bei steigenden Kursen ist ein starkes Signal.
            </div>""", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Fehler: {e}")
