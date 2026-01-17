import streamlit as st
import yfinance as yf
import pandas as pd

# --- 1. KI-ENGINE ---
def calculate_rsi(data, window=14):
    if len(data) < window + 1: return 50
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / (loss + 1e-9)
    return (100 - (100 / (1 + rs))).iloc[-1]

def get_ki_verdict(ticker_obj, eur_val):
    inf = ticker_obj.info
    hist = ticker_obj.history(period="1y")
    if len(hist) < 200: return "➡️ Neutral", "Zu wenig Daten", 50, [], 0, 0
    
    curr_p = float(hist['Close'].iloc[-1])
    prev_p = float(hist['Close'].iloc[-2])
    
    s50 = float(hist['Close'].rolling(50).mean().iloc[-1])
    s50_p = float(hist['Close'].rolling(50).mean().iloc[-2])
    s200 = float(hist['Close'].rolling(200).mean().iloc[-1])
    
    rsi_val = calculate_rsi(hist)
    target_usd = inf.get('targetMedianPrice', curr_p)
    
    score = 50
    reasons = []
    
    # SMA & Trend
    if prev_p < s50_p and curr_p > s50:
        score += 20; reasons.append("⚡ SMA 50 BREAKOUT!")
    elif curr_p > s200:
        score += 10; reasons.append("📈 Trend: Über SMA 200.")
        
    dist_200 = ((curr_p / s200) - 1) * 100
    if dist_200 > 15: score -= 10; reasons.append(f"⚠️ Heißgelaufen: {dist_200:.1f}% über SMA 200.")

    if rsi_val < 35: score += 15; reasons.append("🚀 RSI: Überverkauft.")
    
    # News Sentiment
    raw_news = ticker_obj.news[:3]
    news_analysis = []
    for n in raw_news:
        t = n.get('title', 'Kein Titel')
        sent, col = "⚪ Neutral", "#8b949e"
        if any(w in t.lower() for w in ['upgraded', 'buy', 'growth', 'beats']): sent, col = "🟢 Positiv", "#00e676"; score += 5
        elif any(w in t.lower() for w in ['risk', 'sell', 'loss', 'misses']): sent, col = "🔴 Negativ", "#ff1744"; score -= 7
        news_analysis.append({'title': t, 'sentiment': sent, 'color': col})

    verdict = "🚀 STRONG BUY" if score >= 65 else ("🛑 SELL" if score <= 35 else "➡️ HOLD")
    return verdict, "\n".join(reasons), rsi_val, news_analysis, dist_200, target_usd

# --- 2. UI SETUP ---
st.set_page_config(page_title="StockAI Profit", layout="centered")
st.markdown("<style>.status-card { background: #0d1117; padding: 12px; border-radius: 10px; border-left: 5px solid #3d5afe; margin-bottom: 15px; font-size: 0.85em; white-space: pre-wrap; } .news-box { padding: 8px; border-radius: 8px; background: #161b22; margin-bottom: 8px; border: 1px solid #30363d; font-size: 0.8em; } .profit-card { background: #002b1c; padding: 12px; border-radius: 10px; border: 1px solid #00e676; color: #00e676; margin-top: 10px; }</style>", unsafe_allow_html=True)

# --- 3. APP ---
st.title("🛡️ StockAI Mobile")
ticker_input = st.text_input("Symbol:", value="AAPL").upper()
eur_usd_rate = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

c1, c2, c3 = st.columns(3)
if 'p' not in st.session_state: st.session_state.p = '1mo'
if c1.button("1T"): st.session_state.p = '1d'
if c2.button("1W"): st.session_state.p = '5d'
if c3.button("1M"): st.session_state.p = '1mo'

try:
    ticker = yf.Ticker(ticker_input)
    hist_p = ticker.history(period=st.session_state.p)
    
    if not hist_p.empty:
        curr_eur = hist_p['Close'].iloc[-1] * eur_usd_rate
        
        # KI-Analyse
        verdict, reasons, rsi_v, news_d, d200, target_u = get_ki_verdict(ticker, eur_usd_rate)
        target_e = target_u * eur_usd_rate
        
        st.metric("Kurs (€)", f"{curr_eur:.2f} €", f"{((hist_p['Close'].iloc[-1]/hist_p['Close'].iloc[0])-1)*100:.2f}%")
        st.subheader(f"KI: {verdict}")
        st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
        
        # ORDER-PLANER & GEWINN-CHANCE
        st.subheader("🛡️ Order- & Profit-Planer")
        invest = st.number_input("Budget (€)", value=1000.0, step=100.0)
        risk = st.slider("Stop-Loss Risiko (%)", 1, 15, 5)
        
        stücke = int(invest // curr_eur)
        stop_l = curr_eur * (1 - (risk/100))
        
        # Potenzielle Gewinnberechnung
        pot_gewinn = (target_e - curr_eur) * stücke
        pot_perf = ((target_e / curr_eur) - 1) * 100
        
        st.success(f"**{stücke} Stück** | Stop: **{stop_l:.2f} €**")
        
        if pot_gewinn > 0:
            st.markdown(f"""<div class='profit-card'>
                <b>🎯 Kursziel-Chance:</b><br>
                Ziel: {target_e:.2f} € (+{pot_perf:.1f}%)<br>
                Potenzial: <b>+{pot_gewinn:.2f} €</b>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("Kurs liegt aktuell über dem Analysten-Ziel.")

        # NEWS
        st.subheader("📰 Sentiment")
        for n in news_d:
            st.markdown(f"<div class='news-box'><span style='color:{n['color']}; font-weight:bold;'>{n['sentiment']}</span><br>{n['title']}</div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Fehler: {e}")
