import streamlit as st
import yfinance as yf
import pandas as pd

# --- 1. KI-ENGINE (SMART ANALYST) ---
def get_ki_verdict(ticker_obj, eur_val):
    inf = ticker_obj.info
    hist = ticker_obj.history(period="1y") # 1 Jahr für stabilere SMA-Berechnung
    if hist.empty: return "➡️ Neutral", "Keine Daten", 0
    
    curr_p = hist['Close'].iloc[-1]
    prev_p = hist['Close'].iloc[-2]
    sma50 = hist['Close'].rolling(50).mean()
    sma200 = hist['Close'].rolling(200).mean()
    
    curr_sma50 = sma50.iloc[-1]
    curr_sma200 = sma200.iloc[-1]
    
    # Fundamentaldaten
    kgv = inf.get('forwardPE', 0)
    bgv = inf.get('bookValue', 0)
    kbv = curr_p / bgv if bgv and bgv > 0 else 0
    marge = inf.get('operatingMargins', 0)
    target = inf.get('targetMedianPrice', curr_p)
    recommend = inf.get('recommendationKey', 'none').replace('_', ' ')
    
    score = 50
    reasons = []
    
    # 1. SMA BREAKOUT CHECK
    if prev_p < curr_sma50 and curr_p > curr_sma50:
        score += 20
        reasons.append("⚡ SMA 50 BREAKOUT: Kurs hat den 50-Tage-Schnitt nach oben durchbrochen!")
    elif curr_p > curr_sma200:
        score += 10
        reasons.append("📈 BULLISH: Kurs hält sich stabil über dem SMA 200.")
    elif curr_p < curr_sma200:
        score -= 15
        reasons.append("📉 BEARISH: Kurs unter dem SMA 200 (Langzeittrend negativ).")
        
    # 2. BEWERTUNG (KGV/BGV)
    if 0 < kgv < 18:
        score += 10
        reasons.append(f"💎 Bewertung: KGV ({kgv:.1f}) attraktiv für die Branche.")
    if 0 < kbv < 1.2:
        score += 10
        reasons.append(f"🏢 Substanz: KBV ({kbv:.1f}) deutet auf Unterbewertung hin.")
        
    # 3. ANALYSTEN & NEWS
    if "buy" in recommend:
        score += 15
        reasons.append(f"📊 Analysten-Rating: '{recommend.upper()}' Konsens.")
    
    upside = (target / curr_p - 1) * 100
    if upside > 15:
        score += 10
        reasons.append(f"🎯 Kursziel: Potential von {upside:.1f}% bis zum Target.")

    # Finales Urteil
    if score >= 65: verdict = "🚀 STRONG BUY"
    elif score <= 35: verdict = "🛑 SELL / AVOID"
    else: verdict = "➡️ HOLD / WATCH"
    
    return verdict, "\n".join(reasons)

# --- 2. UI SETUP ---
st.set_page_config(page_title="StockAI Mobile", layout="centered")

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.6rem !important; }
    .stButton > button { width: 100%; border-radius: 8px; height: 45px; font-weight: bold; background-color: #3d5afe; color: white; }
    .status-card { background: #161b22; padding: 15px; border-radius: 12px; border-left: 5px solid #00e676; margin-bottom: 20px; white-space: pre-wrap; font-size: 0.9em; }
    .calc-box { background: #0d1117; padding: 15px; border-radius: 12px; border: 1px solid #30363d; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 3. APP LOGIK ---
st.title("🛡️ StockAI Mobile")
ticker_input = st.text_input("Ticker Symbol:", value="AAPL").upper()
eur_usd_rate = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

# Zeitachsen-Buttons
if 'p' not in st.session_state: st.session_state.p = '1mo'
c1, c2, c3 = st.columns(3)
if c1.button("1 Tag"): st.session_state.p = '1d'
if c2.button("1 Woche"): st.session_state.p = '5d'
if c3.button("1 Monat"): st.session_state.p = '1mo'

try:
    ticker = yf.Ticker(ticker_input)
    info = ticker.info
    
    # Preis-Daten
    hist_p = ticker.history(period=st.session_state.p)
    if not hist_p.empty:
        curr_usd = hist_p['Close'].iloc[-1]
        curr_eur = curr_usd * eur_usd_rate
        start_p = hist_p['Close'].iloc[0]
        perf = ((curr_usd / start_p) - 1) * 100
        
        # --- KURS-DISPLAY ---
        st.subheader("Kurs-Check")
        m1, m2 = st.columns(2)
        m1.metric("Euro", f"{curr_eur:.2f} €", f"{perf:.2f}%")
        m2.metric("Dollar", f"{curr_usd:.2f} $")
        
        st.divider()

        # --- KI ANALYSE ---
        verdict, reasons = get_ki_verdict(ticker, eur_usd_rate)
        st.markdown(f"### KI-Rating: {verdict}")
        st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
        
        # --- RISIKO & STÜCKZAHL RECHNER ---
        st.subheader("🛡️ Order- & Risiko-Rechner")
        with st.container():
            st.markdown("<div class='calc-box'>", unsafe_allow_html=True)
            invest = st.number_input("Geplantes Investment (€)", value=1000.0, step=50.0)
            risk_pct = st.slider("Max. akzeptierter Verlust (%)", 1, 15, 5)
            
            # Berechnungen
            stücke = int(invest // curr_eur)
            tatsächliches_invest = stücke * curr_eur
            stop_loss_eur = curr_eur * (1 - (risk_pct / 100))
            max_verlust = tatsächliches_invest * (risk_pct / 100)
            
            st.write(f"📊 **Kaufmenge: {stücke} Stück**")
            st.write(f"💰 Effektives Invest: {tatsächliches_invest:.2f} €")
            st.error(f"📍 **Stop-Loss setzen bei: {stop_loss_eur:.2f} €**")
            st.info(f"📉 Risiko bei Auslösung: -{max_verlust:.2f} €")
            st.markdown("</div>", unsafe_allow_html=True)

        st.divider()
        st.write("**Fundamentale Kurz-Übersicht:**")
        st.write(f"• KGV: {info.get('forwardPE', 'N/A')} | BGV: {info.get('bookValue', 'N/A')}")
        st.write(f"• Marge: {info.get('operatingMargins', 0)*100:.1f}%")

except Exception as e:
    st.error(f"Fehler: {e}")
