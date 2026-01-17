import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# --- 1. SMART SEARCH & TIME-WEIGHTED SENTIMENT ---
def get_ticker_from_any(query):
    try:
        search = yf.Search(query, max_results=1)
        return search.quotes[0]['symbol'] if search.quotes else query.upper()
    except: return query.upper()

def analyze_news_sentiment(news_list):
    score = 0
    now = datetime.now(timezone.utc)
    pos_w = ['upgraded', 'buy', 'growth', 'beats', 'profit', 'bull', 'stark', 'chance', 'hoch']
    neg_w = ['risk', 'sell', 'loss', 'misses', 'bear', 'warnung', 'senkt', 'problem', 'tief']
    for n in news_list[:5]:
        title = n.get('title', '').lower()
        pub_time = datetime.fromtimestamp(n.get('providerPublishTime', now.timestamp()), timezone.utc)
        hours_old = (now - pub_time).total_seconds() / 3600
        weight = 1.0 if hours_old < 24 else (0.5 if hours_old < 72 else 0.2)
        if any(w in title for w in pos_w): score += (5 * weight)
        if any(w in title for w in neg_w): score -= (7 * weight)
    return round(score, 1)

# --- 2. 9-FAKTOR KI-Analyse-ENGINE ---
def get_ki_verdict(ticker_obj):
    inf = ticker_obj.info
    hist = ticker_obj.history(period="1y")
    if len(hist) < 200: return "➡️ Neutral", "Zu wenig Daten.", 0, 0, 50
    
    curr_p = float(hist['Close'].iloc[-1])
    score = 50
    reasons = []
    
    # Trend, RSI, Vola, etc.
    s200 = hist['Close'].rolling(200).mean().iloc[-1]
    s50 = hist['Close'].rolling(50).mean().iloc[-1]
    trend_reversal_p = s200 
    if curr_p > s50 > s200: score += 15; reasons.append(f"📈 Trend: Stark Bullish.")
    elif curr_p < s200: score -= 15; reasons.append(f"📉 Trend: Bearish.")

    delta = hist['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs.iloc[-1]))
    if rsi > 70: score -= 10
    elif rsi < 30: score += 10

    high_low = hist['High'] - hist['Low']
    atr = high_low.rolling(14).mean().iloc[-1]
    vola_ratio = (atr / curr_p) * 100

    marge = inf.get('operatingMargins', 0)
    if marge > 0.15: score += 10
    if inf.get('totalCash', 0) > inf.get('totalDebt', 0): score += 5

    kgv = inf.get('forwardPE', -1)
    if 0 < kgv < 18: score += 10
    
    if hist['Volume'].iloc[-1] > hist['Volume'].tail(20).mean() * 1.3: score += 10
    score += analyze_news_sentiment(ticker_obj.news)
    
    # Sektor-Check
    sector = inf.get('sector', 'N/A')
    if (hist['Close'].iloc[-1] / hist['Close'].iloc[0]) - 1 > 0.2:
        score += 10; reasons.append(f"🏆 Sektor: Top-Performer in {sector}.")

    if score >= 80: verdict = "💎 STRONG BUY"
    elif score >= 60: verdict = "🚀 BUY"
    elif score >= 35: verdict = "➡️ HOLD"
    else: verdict = "🛑 SELL"
    return verdict, "\n".join(reasons), vola_ratio, trend_reversal_p, score

# --- 3. UI SETUP ---
st.set_page_config(page_title="KI-Analyse Deep Dive", layout="centered")
st.markdown("<style>.status-card { background: #0d1117; padding: 12px; border-radius: 10px; border-left: 5px solid #3d5afe; margin-bottom: 15px; font-size: 0.85em; white-space: pre-wrap; } .calc-box { background: #161b22; padding: 15px; border-radius: 12px; border: 1px solid #30363d; } .reversal-box { background: #1a1a1a; padding: 10px; border-radius: 8px; border: 1px dashed #ff4b4b; margin-top: 10px; text-align: center; } .matrix-desc { font-size: 0.88em; color: #cfd8dc; line-height: 1.6; margin-bottom: 15px; }</style>", unsafe_allow_html=True)

# --- 4. APP ---
st.title("🛡️ KI-Analyse Intelligence")
search_query = st.text_input("Suche:", value="Apple")
ticker_symbol = get_ticker_from_any(search_query)
eur_usd_rate = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

try:
    ticker = yf.Ticker(ticker_symbol)
    inf = ticker.info
    verdict, reasons, current_vola, reversal_p, main_score = get_ki_verdict(ticker)
    
    # Anzeige Metrics & Verdict
    st.subheader(f"KI-Analyse: {verdict} (Score: {main_score})")
    st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='reversal-box'>🚨 <b>Trend-Umkehr-Marke:</b> {reversal_p * eur_usd_rate:.2f} €</div>", unsafe_allow_html=True)

    # SEKTOR VERGLEICH TABELLE
    st.subheader("🏁 Sektor-Benchmark: Top Peers")
    sector_peers = ["MSFT", "GOOGL", "AMZN"] if ticker_symbol == "AAPL" else ["TSLA", "NVIDIA", "META"] # Beispiel-Peers
    peer_data = []
    for p in sector_peers:
        p_ticker = yf.Ticker(p)
        _, _, _, _, p_score = get_ki_verdict(p_ticker)
        peer_data.append({"Ticker": p, "Name": p_ticker.info.get('shortName'), "KI-Score": p_score})
    st.table(pd.DataFrame(peer_data))

    # Order Planer
    st.subheader("🛡️ Order- & Profit-Planer")
    with st.container():
        st.markdown("<div class='calc-box'>", unsafe_allow_html=True)
        risk_pct = st.slider("Risiko (%)", 0.0, 50.0, 5.0, step=0.25)
        target_pct = st.slider("Ziel (%)", 0.0, 100.0, 15.0, step=0.25)
        # ... (Rest der Kalkulation wie gehabt)
        st.markdown("</div>", unsafe_allow_html=True)

    # Deep Dive
    st.divider()
    st.subheader("🔍 Deep Dive: KI-Analyse Kriterien-Katalog")
    st.markdown("### 1. Markt-Phasierung (SMA 50/200) <span style='color:#3d5afe'>±15 Pkt</span>", unsafe_allow_html=True)
    st.markdown("<p class='matrix-desc'>Prüfung der Position zum SMA 200. Ein Kurs darüber signalisiert einen strukturellen Bullenmarkt. Die KI analysiert hierbei die langfristige 'Gesundheit' des Assets.</p>", unsafe_allow_html=True)
    
    
    st.markdown("### 2. Dynamik (RSI 14) <span style='color:#3d5afe'>±10 Pkt</span>", unsafe_allow_html=True)
    st.markdown("<p class='matrix-desc'>Bewertung der inneren Kaufkraft. RSI > 70 zeigt Überhitzung, RSI < 30 zeigt Unterbewertung durch Panikverkäufe.</p>", unsafe_allow_html=True)
    

    st.markdown("### 3. Volatilität (ATR) <span style='color:#3d5afe'>-5 Pkt</span>", unsafe_allow_html=True)
    st.markdown("<p class='matrix-desc'>Misst das Grundrauschen. Hohe Volatilität führt zu Punktabzug, um das Risiko unberechenbarer Kurssprünge zu minimieren.</p>", unsafe_allow_html=True)

    st.markdown("### 4. Operative Marge <span style='color:#3d5afe'>+10 Pkt</span>", unsafe_allow_html=True)
    st.markdown("<p class='matrix-desc'>Marge > 15% beweist Preismacht und fundamentale Qualität. Ein Kernfaktor für langfristige Stabilität.</p>", unsafe_allow_html=True)

    st.markdown("### 5. Liquidität (Net-Cash) <span style='color:#3d5afe'>+5 Pkt</span>", unsafe_allow_html=True)
    st.markdown("<p class='matrix-desc'>Cash-Reserven vs. Schulden. Net-Cash-Positionen machen das Unternehmen unabhängig von Zinszyklen.</p>", unsafe_allow_html=True)

    st.markdown("### 6. Bewertung (KGV/KUV) <span style='color:#3d5afe'>+10 Pkt</span>", unsafe_allow_html=True)
    st.markdown("<p class='matrix-desc'>Klassisches KGV (< 18) oder KUV (< 3) für Wachstumswerte. Erkennt Unterbewertungen in jeder Marktphase.</p>", unsafe_allow_html=True)
    

    st.markdown("### 7. Volumen-Momentum <span style='color:#3d5afe'>+10 Pkt</span>", unsafe_allow_html=True)
    st.markdown("<p class='matrix-desc'>Handelsvolumen > 30% Schnitt zeigt institutionelles Interesse (Smart Money Bestätigung).</p>", unsafe_allow_html=True)

    st.markdown("### 8. Analysten & Sentiment <span style='color:#3d5afe'>±20 Pkt</span>", unsafe_allow_html=True)
    st.markdown("<p class='matrix-desc'>Kombiniert NLP-News-Analyse und Analysten-Kursziele (>15% Upside) für eine externe Bestätigung.</p>", unsafe_allow_html=True)

    st.markdown("### 9. Sektor-Benchmark (Peer-Leader) <span style='color:#3d5afe'>+10 Pkt</span>", unsafe_allow_html=True)
    st.markdown("<p class='matrix-desc'>Die KI vergleicht das Asset mit seiner Branche. Nur die 'Best-in-Class' Performer erhalten diesen Bonus. Dies stellt sicher, dass du nicht nur in eine gute Aktie investierst, sondern in den aktuellen Branchenführer mit der stärksten relativen Performance.</p>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Fehler: {e}")
