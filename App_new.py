import streamlit as st
import yfinance as yf
import pandas as pd

# --- 1. KI-ENGINE (SMART ANALYST MIT SENTIMENT) ---
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def get_ki_verdict(ticker_obj, eur_val):
    inf = ticker_obj.info
    hist = ticker_obj.history(period="1y")
    if hist.empty: return "➡️ Neutral", "Keine Daten", 50, []
    
    curr_p = hist['Close'].iloc[-1]
    prev_p = hist['Close'].iloc[-2]
    sma50 = hist['Close'].rolling(50).mean().iloc[-1]
    sma200 = hist['Close'].rolling(200).mean().iloc[-1]
    rsi = calculate_rsi(hist).iloc[-1]
    
    # Fundamentaldaten
    kgv = inf.get('forwardPE', 0)
    bgv = inf.get('bookValue', 0)
    kbv = curr_p / bgv if bgv and bgv > 0 else 0
    
    score = 50
    reasons = []
    
    # Technische Analyse & SMA
    if prev_p < sma50 and curr_p > sma50: score += 15; reasons.append("⚡ SMA 50 Breakout!")
    if rsi < 30: score += 15; reasons.append("🚀 RSI: Überverkauft (Chance)")
    elif rsi > 70: score -= 15; reasons.append("⚠️ RSI: Überkauft (Risiko)")
    
    # Fundamentale Analyse
    if 0 < kgv < 15: score += 10; reasons.append(f"💎 KGV ({kgv:.1f}) attraktiv")
    if 0 < kbv < 1.2: score += 10; reasons.append(f"🏢 Substanzstark (KBV {kbv:.1f})")

    # News Sentiment Analyse
    news = ticker_obj.news[:5]
    news_analysis = []
    pos_words = ['upgraded', 'buy', 'growth', 'profit', 'beats', 'stark', 'bull']
    neg_words = ['risk', 'sell', 'loss', 'misses', 'bear', 'sinkt', 'warnung']
    
    for n in news:
        title = n['title'].lower()
        sentiment = "⚪ Neutral"
        color = "#8b949e"
        if any(w in title for w in pos_words):
            sentiment = "🟢 Positiv"
            color = "#00e676"
            score += 5
        elif any(w in title for w in neg_words):
            sentiment = "🔴 Negativ"
            color = "#ff1744"
            score -= 7
        news_analysis.append({'title': n['title'], 'sentiment': sentiment, 'color': color})

    verdict = "🚀 STRONG BUY" if score >= 65 else ("🛑 SELL" if score <= 35 else "➡️ HOLD")
    return verdict, "\n".join(reasons), rsi, news_analysis

# --- 2. UI SETUP ---
st.set_page_config(page_title="StockAI Sentiment", layout="centered")

st.markdown("""
<style>
    .status-card { background: #0d1117; padding: 15px; border-radius: 12px; border-left: 5px solid #3d5afe; margin-bottom: 15px; font-size: 0.85em; white-space: pre-wrap; }
    .news-box { padding: 10px; border-radius: 8px; background: #161b22; margin-bottom: 8px; border: 1px solid #30363d; }
    .edu-box { background: #1c1c1c; padding: 15px; border-radius: 10px; font-size: 0.8em; color: #d1d1d1; }
</style>
""", unsafe_allow_html=True)

# --- 3. APP ---
st.title("🛡️ StockAI Pro")
ticker_input = st.text_input("Symbol (z.B. TSLA):", value="AAPL").upper()
eur_usd_rate = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

if 'p' not in st.session_state: st.session_state.p = '1mo'
c1, c2, c3 = st.columns(3)
if c1.button("1 Tag"): st.session_state.p = '1d'
if c2.button("1 Woche"): st.session_state.p = '5d'
if c3.button("1 Monat"): st.session_state.p = '1mo'

try:
    ticker = yf.Ticker(ticker_input)
    hist_p = ticker.history(period=st.session_state.p)
    
    if not hist_p.empty:
        curr_usd = hist_p['Close'].iloc[-1]
        curr_eur = curr_usd * eur_usd_rate
        perf = ((curr_usd / hist_p['Close'].iloc[0]) - 1) * 100
        
        # Performance Header
        m1, m2 = st.columns(2)
        m1.metric("Euro Kurs", f"{curr_eur:.2f} €", f"{perf:.2f}%")
        m2.metric("Dollar Kurs", f"{curr_usd:.2f} $")
        
        # KI Urteil
        verdict, reasons, rsi_val, news_data = get_ki_verdict(ticker, eur_usd_rate)
        st.subheader(f"KI-Urteil: {verdict}")
        st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
        
        # Risiko & Stop-Loss
        st.subheader("🛡️ Order-Rechner")
        invest = st.number_input("Dein Invest (€)", value=1000.0)
        risk = st.slider("Risiko (%)", 1, 15, 5)
        stücke = int(invest // curr_eur)
        stop_loss = curr_eur * (1 - (risk/100))
        st.success(f"Kaufmenge: {stücke} Stück | Stop-Loss: {stop_loss:.2f} €")

        # News Sentiment
        st.subheader("📰 News Sentiment")
        for n in news_data:
            st.markdown(f"""<div class='news-box'>
                <span style='color:{n['color']}; font-weight:bold;'>{n['sentiment']}</span><br>
                <span style='font-size:0.85em;'>{n['title']}</span>
            </div>""", unsafe_allow_html=True)

        # Glossar
        st.divider()
        with st.expander("📚 Glossar: KGV, BGV & RSI"):
            st.markdown("""<div class='edu-box'>
            <b>KGV:</b> Kurs-Gewinn-Verhältnis. < 15 ist oft günstig.<br><br>
            <b>BGV / KBV:</b> Substanzwert. Ein KBV < 1.2 zeigt, dass die Aktie nah am realen Sachwert gehandelt wird.<br><br>
            <b>RSI:</b> Relative Stärke. < 30 ist 'überverkauft' (Kaufsignal), > 70 'überkauft' (Verkaufsignal).
            </div>""", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Fehler: {e}")
