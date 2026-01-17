import streamlit as st
import yfinance as yf
import pandas as pd

# --- 1. KI-ENGINE (SMART ANALYST) ---
def calculate_rsi(data, window=14):
    if len(data) < window: return 50
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
    # SMA Berechnung
    sma50 = hist['Close'].rolling(50).mean().iloc[-1]
    sma200 = hist['Close'].rolling(200).mean().iloc[-1]
    rsi_val = calculate_rsi(hist)
    
    # Fundamentaldaten
    kgv = inf.get('forwardPE', 0)
    bgv = inf.get('bookValue', 0)
    kbv = curr_p / bgv if bgv and bgv > 0 else 0
    
    score = 50
    reasons = []
    
    # Technische Prüfung
    if prev_p < sma50 and curr_p > sma50: score += 15; reasons.append("⚡ SMA 50 Breakout!")
    if rsi_val < 35: score += 15; reasons.append(f"🚀 RSI ({rsi_val:.1f}): Überverkauft")
    elif rsi_val > 65: score -= 15; reasons.append(f"⚠️ RSI ({rsi_val:.1f}): Überhitzt")
    
    if 0 < kgv < 15: score += 10; reasons.append("💎 KGV attraktiv")
    if 0 < kbv < 1.2: score += 10; reasons.append("🏢 Hoher Substanzwert")

    # NEWS SENTIMENT (Robuster Zugriff)
    raw_news = ticker_obj.news[:5]
    news_analysis = []
    pos_words = ['upgraded', 'buy', 'growth', 'profit', 'beats', 'stark', 'bull', 'kauf', 'anstieg']
    neg_words = ['risk', 'sell', 'loss', 'misses', 'bear', 'sinkt', 'warnung', 'verlust', 'senkt']
    
    for n in raw_news:
        # Fehler-Fix: Nutze .get() für title
        t = n.get('title', 'Kein Titel verfügbar')
        t_low = t.lower()
        sentiment = "⚪ Neutral"
        color = "#8b949e"
        
        if any(w in t_low for w in pos_words):
            sentiment = "🟢 Positiv"; color = "#00e676"; score += 5
        elif any(w in t_low for w in neg_words):
            sentiment = "🔴 Negativ"; color = "#ff1744"; score -= 7
            
        news_analysis.append({'title': t, 'sentiment': sentiment, 'color': color})

    verdict = "🚀 STRONG BUY" if score >= 65 else ("🛑 SELL" if score <= 35 else "➡️ HOLD")
    return verdict, "\n".join(reasons), rsi_val, news_analysis

# --- 2. UI SETUP ---
st.set_page_config(page_title="StockAI Fix", layout="centered")

st.markdown("""
<style>
    .status-card { background: #0d1117; padding: 12px; border-radius: 10px; border-left: 5px solid #3d5afe; margin-bottom: 15px; font-size: 0.85em; white-space: pre-wrap; }
    .news-box { padding: 8px; border-radius: 8px; background: #161b22; margin-bottom: 8px; border: 1px solid #30363d; font-size: 0.8em; }
    .edu-box { background: #1c1c1c; padding: 12px; border-radius: 10px; font-size: 0.85em; color: #d1d1d1; line-height: 1.4; }
</style>
""", unsafe_allow_html=True)

# --- 3. DASHBOARD ---
st.title("🛡️ StockAI Mobile")
ticker_input = st.text_input("Symbol (z.B. AAPL, TSLA):", value="AAPL").upper()
eur_usd_rate = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

# Zeitachsen-Buttons
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
        
        # Header Metrics
        m1, m2 = st.columns(2)
        m1.metric("Kurs (€)", f"{curr_eur:.2f} €", f"{perf:.2f}%")
        m2.metric("Kurs ($)", f"{curr_usd:.2f} $")
        
        # KI Analyse
        verdict, reasons, rsi_val, news_data = get_ki_verdict(ticker, eur_usd_rate)
        st.subheader(f"KI: {verdict}")
        st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
        
        # Order Rechner
        st.subheader("🛡️ Order-Rechner")
        invest = st.number_input("Budget (€)", value=1000.0, step=100.0)
        risk = st.slider("Risiko (%)", 1, 15, 5)
        stücke = int(invest // curr_eur)
        stop_loss = curr_eur * (1 - (risk/100))
        st.success(f"**{stücke} Stück** kaufen | Stop bei **{stop_loss:.2f} €**")

        # News
        st.subheader("📰 News Sentiment")
        if news_data:
            for n in news_data:
                st.markdown(f"""<div class='news-box'>
                    <span style='color:{n['color']}; font-weight:bold;'>{n['sentiment']}</span><br>
                    {n['title']}
                </div>""", unsafe_allow_html=True)
        else:
            st.write("Keine News gefunden.")

        # Glossar
        st.divider()
        with st.expander("📚 Erklärung: KGV, BGV & RSI"):
            st.markdown("""<div class='edu-box'>
            <b>KGV:</b> Wie teuer ist die Aktie im Verhältnis zum Gewinn? < 15 ist oft günstig.<br><br>
            <b>BGV / KBV:</b> Substanzwert. Ein KBV < 1.2 zeigt, dass man fast nur den reinen Firmenwert ohne Aufschlag zahlt.<br><br>
            <b>RSI:</b> Oszillator von 0-100. Unter 30 ist die Aktie 'ausverkauft' (Chance), über 70 ist sie 'heißgelaufen' (Gefahr).
            </div>""", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Fehler bei {ticker_input}: {e}")
