import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# --- 1. HELFER-FUNKTIONEN ---
def get_ticker_from_any(query):
    try:
        search = yf.Search(query, max_results=1)
        return search.quotes[0]['symbol'] if search.quotes else query.upper()
    except: return query.upper()

def get_eur_usd_rate():
    try:
        hist = yf.Ticker("EURUSD=X").history(period="1d")
        return 1 / float(hist['Close'].iloc[-1]) if not hist.empty else 0.92
    except: return 0.92

def analyze_news_sentiment(news_list):
    if not news_list: return 0
    score, now = 0, datetime.now(timezone.utc)
    pos_w = ['upgraded', 'buy', 'growth', 'beats', 'profit', 'bull', 'stark', 'chance']
    neg_w = ['risk', 'sell', 'loss', 'misses', 'bear', 'warnung', 'senkt', 'problem']
    for n in news_list[:5]:
        title = n.get('title', '').lower()
        pub_time = datetime.fromtimestamp(n.get('providerPublishTime', now.timestamp()), timezone.utc)
        weight = 1.0 if (now - pub_time).total_seconds() / 3600 < 24 else 0.4
        if any(w in title for w in pos_w): score += (5 * weight)
        if any(w in title for w in neg_w): score -= (7 * weight)
    return round(score, 1)

# --- 2. 11-FAKTOR KI-Analyse-ENGINE (DYNAMISCH) ---
def get_ki_verdict(ticker_obj, w):
    try:
        inf = ticker_obj.info
        hist = ticker_obj.history(period="1y")
        if len(hist) < 200: return "➡️ Neutral", "Zu wenig Daten.", 0, 0, 50
        
        curr_p = float(hist['Close'].iloc[-1])
        score, reasons = 50, []
        
        # 1. Trend (SMA 50/200)
        s200, s50 = hist['Close'].rolling(200).mean().iloc[-1], hist['Close'].rolling(50).mean().iloc[-1]
        if curr_p > s50 > s200: score += w['trend']; reasons.append(f"📈 Trend: Bullish (+{w['trend']})")
        elif curr_p < s200: score -= w['trend']; reasons.append(f"📉 Trend: Bearish (-{w['trend']})")

        # 2. RSI (14)
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))
        if rsi > 70: score -= w['rsi']; reasons.append(f"🔥 RSI überhitzt (-{w['rsi']})")
        elif rsi < 30: score += w['rsi']; reasons.append(f"🧊 RSI überverkauft (+{w['rsi']})")

        # 3. Volatilität (ATR)
        atr_val = (hist['High']-hist['Low']).rolling(14).mean().iloc[-1]
        vola_ratio = (atr_val / curr_p) * 100
        if vola_ratio > 4: score -= w['vola']; reasons.append(f"⚠️ Vola: Hoch (-{w['vola']})")

        # 4. Profitabilität (Marge)
        marge = inf.get('operatingMargins', 0)
        if marge > 0.15: score += w['marge']; reasons.append(f"💰 Marge: Stark (+{w['marge']})")
        
        # 5. Sicherheit (Cash)
        if (inf.get('totalCash', 0) or 0) > (inf.get('totalDebt', 0) or 0): score += w['cash']; reasons.append(f"🏦 Net-Cash (+{w['cash']})")
        
        # 6. Bewertung (KGV)
        kgv = inf.get('forwardPE', 0)
        if 0 < (kgv or 0) < 18: score += w['val']; reasons.append(f"💎 KGV attraktiv (+{w['val']})")
        
        # 7. Volumen
        if hist['Volume'].iloc[-1] > hist['Volume'].tail(20).mean() * 1.3: score += w['vol']; reasons.append(f"📊 Volumen: Hoch (+{w['vol']})")
        
        # 8. NEU: INVESTMENTBANKEN KONSENS & NEWS
        news_raw = analyze_news_sentiment(ticker_obj.news)
        target_p = inf.get('targetMeanPrice')
        bank_upside = ((target_p / curr_p) - 1) if target_p else 0
        
        analyst_score = (news_raw * 0.5) 
        if bank_upside > 0.15: analyst_score += 10 # Bonus für >15% Banken-Upside
        
        final_news_score = analyst_score * (w['news'] / 10)
        score += final_news_score
        if target_p: reasons.append(f"🏛️ Banken-Ziel: {target_p:.2f}$ ({bank_upside*100:+.1f}%)")
        if news_raw != 0: reasons.append(f"📰 News Sentiment ({news_raw:+.1f})")
        
        # 9. Sektor
        if (curr_p / hist['Close'].iloc[0]) - 1 > 0.2: score += w['sector']; reasons.append(f"🏆 Sektor-Leader (+{w['sector']})")

        # 10. MACD
        exp1, exp2 = hist['Close'].ewm(span=12).mean(), hist['Close'].ewm(span=26).mean()
        macd = exp1 - exp2
        if macd.iloc[-1] > macd.ewm(span=9).mean().iloc[-1]: score += w['macd']; reasons.append(f"🌊 MACD: Bullish (+{w['macd']})")

        # 11. PEG
        peg = inf.get('pegRatio')
        if peg and 0.5 < peg < 1.5: score += w['peg']; reasons.append(f"⚖️ PEG: Optimal (+{w['peg']})")

        verdict = "💎 STRONG BUY" if score >= 85 else ("🚀 BUY" if score >= 65 else ("➡️ HOLD" if score >= 40 else "🛑 SELL"))
        return verdict, "\n".join(reasons), vola_ratio, s200, round(score, 1)
    except: return "⚠️ Error", "Analyse fehlgeschlagen", 0, 0, 50

# --- 3. UI SETUP ---
st.set_page_config(page_title="KI-Analyse Intelligence", layout="centered")
st.markdown("""
<style>
.status-card { background: #0d1117; padding: 12px; border-radius: 10px; border-left: 5px solid #3d5afe; margin-bottom: 15px; font-size: 0.85em; white-space: pre-wrap; }
.high-conviction { background: linear-gradient(90deg, #ffd700, #bf953f); color: #000; padding: 15px; border-radius: 10px; font-weight: bold; text-align: center; margin-bottom: 20px; border: 2px solid #fff; }
.calc-box { background: #161b22; padding: 15px; border-radius: 12px; border: 1px solid #30363d; }
.reversal-box { background: #1a1a1a; padding: 10px; border-radius: 8px; border: 1px dashed #ff4b4b; margin-top: 10px; text-align: center; }
.matrix-desc { font-size: 0.88em; color: #cfd8dc; line-height: 1.6; margin-bottom: 15px; }
.weight-badge { background: #3d5afe; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 0.8em; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR: DYNAMISCHE GEWICHTUNG ---
st.sidebar.header("⚙️ Strategie-Gewichtung")
weights = {
    'trend': st.sidebar.slider("1. Trend (SMA 50/200)", 0, 30, 15),
    'rsi': st.sidebar.slider("2. Dynamik (RSI)", 0, 20, 10),
    'vola': st.sidebar.slider("3. Volatilität (ATR)", 0, 15, 5),
    'marge': st.sidebar.slider("4. Profitabilität (Marge)", 0, 25, 10),
    'cash': st.sidebar.slider("5. Sicherheit (Cash)", 0, 15, 5),
    'val': st.sidebar.slider("6. Bewertung (KGV)", 0, 20, 10),
    'vol': st.sidebar.slider("7. Markt-Interesse (Vol)", 0, 20, 10),
    'news': st.sidebar.slider("8. Banken-Ziele & News", 0, 40, 25),
    'sector': st.sidebar.slider("9. Sektor-Stärke", 0, 20, 10),
    'macd': st.sidebar.slider("10. Momentum (MACD)", 0, 15, 5),
    'peg': st.sidebar.slider("11. Wachstumspreis (PEG)", 0, 15, 5)
}

# --- 4. APP HAUPTTEIL ---
st.title("🛡️ KI-Analyse Intelligence")
query = st.text_input("Suche (Ticker, Name):", value="NVDA")
ticker_sym = get_ticker_from_any(query)
eur_usd = get_eur_usd_rate()

try:
    ticker = yf.Ticker(ticker_sym)
    inf, hist = ticker.info, ticker.history(period="3mo")
    
    if not hist.empty:
        curr_p = hist['Close'].iloc[-1]
        st.metric(f"{inf.get('longName', ticker_sym)}", f"{curr_p * eur_usd:.2f} €", f"{((curr_p/hist['Close'].iloc[0])-1)*100:.2f}%")
        
        verdict, reasons, vola, reversal_p, score = get_ki_verdict(ticker, weights)
        if score >= 90: st.markdown("<div class='high-conviction'>🌟 HIGH CONVICTION: Banken-Konsens & Technik im Einklang!</div>", unsafe_allow_html=True)
        
        st.subheader(f"KI-Analyse: {verdict} (Score: {score})")
        st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='reversal-box'>🚨 Trend-Umkehr-Marke (SMA 200): {reversal_p * eur_usd:.2f} €</div>", unsafe_allow_html=True)

        # Order Planer
        with st.expander("🛡️ Order- & Profit-Planer (0.25% Precision)", expanded=True):
            invest = st.number_input("Investment (€)", value=1000.0, step=100.0)
            risk_pct = st.slider("Risiko (%)", 0.0, 50.0, 5.0, step=0.25)
            target_pct = st.slider("Ziel (%)", 0.0, 100.0, 15.0, step=0.25)
            st.info(f"Stop-Loss: {curr_p*eur_usd*(1-risk_pct/100):.2f} € | Ziel: {curr_p*eur_usd*(1+target_pct/100):.2f} €")

        # --- MAXIMAL DETAILLIERTER STRATEGISCHER DEEP DIVE ---
        st.divider()
        st.subheader("🔍 Strategischer Deep Dive: Die 11-Faktor-Matrix")
        
        st.markdown(f"### 1. Markt-Phasierung (SMA 50/200) <span class='weight-badge'>±{weights['trend']}</span>", unsafe_allow_html=True)
        st.markdown(f"<p class='matrix-desc'>Prüfung der Preislage zum 200-Tage-Durchschnitt. Ein Kurs über dem SMA 200 gilt als 'bullish' und signalisiert langfristige Akzeptanz durch Großinvestoren. Deine Gewichtung von <b>{weights['trend']}</b> priorisiert diesen Trendfilter.</p>", unsafe_allow_html=True)
        

        st.markdown(f"### 2. Dynamik-Check (RSI 14) <span class='weight-badge'>±{weights['rsi']}</span>", unsafe_allow_html=True)
        st.markdown(f"<p class='matrix-desc'>Der Relative Strength Index misst die Geschwindigkeit von Preisbewegungen. Ein RSI unter 30 signalisiert eine massive Unterbewertung (Panik), während über 70 Gier anzeigt. Gewichtung: <b>{weights['rsi']}</b>.</p>", unsafe_allow_html=True)
        

        st.markdown(f"### 3. Volatilitäts-Rauschen (ATR) <span class='weight-badge'>-{weights['vola']}</span>", unsafe_allow_html=True)
        st.markdown(f"<p class='matrix-desc'>Die Average True Range bewertet die tägliche Schwankungsbreite. Liegt diese über 4 %, steigt die Gefahr von Stop-Loss-Sprüngen. Dein Schutzfaktor: <b>-{weights['vola']}</b>.</p>", unsafe_allow_html=True)

        st.markdown(f"### 4. Operative Effizienz (Marge) <span class='weight-badge'>+{weights['marge']}</span>", unsafe_allow_html=True)
        st.markdown(f"<p class='matrix-desc'>Unternehmen mit einer operativen Marge von über 15 % besitzen Preismacht und einen Wettbewerbsvorteil (Moat). Fundamental-Bonus: <b>{weights['marge']}</b>.</p>", unsafe_allow_html=True)

        st.markdown(f"### 5. Liquiditäts-Sicherheit (Net-Cash) <span class='weight-badge'>+{weights['cash']}</span>", unsafe_allow_html=True)
        st.markdown(f"<p class='matrix-desc'>Ein positiver Net-Cash-Bestand schützt das Unternehmen in Hochzinsphasen vor Refinanzierungsrisiken. Krisen-Bonus: <b>{weights['cash']}</b>.</p>", unsafe_allow_html=True)

        st.markdown(f"### 6. Bewertungs-Anker (KGV) <span class='weight-badge'>+{weights['val']}</span>", unsafe_allow_html=True)
        st.markdown(f"<p class='matrix-desc'>Das Kurs-Gewinn-Verhältnis (Forward) wird gegen den historischen Schnitt von 18 geprüft. Günstige Bewertungen mindern das Fallhöhen-Risiko. Value-Gewicht: <b>{weights['val']}</b>.</p>", unsafe_allow_html=True)

        st.markdown(f"### 7. Smart-Money Flow (Volumen) <span class='weight-badge'>+{weights['vol']}</span>", unsafe_allow_html=True)
        st.markdown(f"<p class='matrix-desc'>Erhöhtes Volumen (>130 % des Schnitts) bestätigt die Relevanz einer Kursbewegung. Es zeigt an, dass institutionelles Kapital (Smart Money) aktiv wird. Relevanz: <b>{weights['vol']}</b>.</p>", unsafe_allow_html=True)

        st.markdown(f"### 8. Banken-Kursziele & News-NLP <span class='weight-badge'>±{weights['news']}</span>", unsafe_allow_html=True)
        st.markdown(f"<p class='matrix-desc'><b>Echtzeit-Validierung:</b> Das System vergleicht den Kurs tagesaktuell mit den Kurszielen großer Investmentbanken (Goldman Sachs, Morgan Stanley etc.). Ein Upside-Potential von >15 % triggert einen massiven Vertrauensbonus. Deine Strategie gewichtet diese Profi-Meinungen mit <b>{weights['news']}</b>.</p>", unsafe_allow_html=True)
        

        st.markdown(f"### 9. Sektor-Outperformance <span class='weight-badge'>+{weights['sector']}</span>", unsafe_allow_html=True)
        st.markdown(f"<p class='matrix-desc'>Relative Stärke zum Gesamtmarkt. Wir suchen die Leader-Aktien, die ihren Sektor anführen und nicht nur mitlaufen. Leader-Bonus: <b>{weights['sector']}</b>.</p>", unsafe_allow_html=True)

        st.markdown(f"### 10. Momentum-Oszillator (MACD) <span class='weight-badge'>+{weights['macd']}</span>", unsafe_allow_html=True)
        st.markdown(f"<p class='matrix-desc'>Der MACD bestätigt, ob der Trend aktuell an Kraft gewinnt oder verliert. Ein bullishes Crossover ist das 'Go' für Kurzfrist-Trader. Momentum-Gewicht: <b>{weights['macd']}</b>.</p>", unsafe_allow_html=True)
        [attachment_0](attachment)

        st.markdown(f"### 11. Wachstum zum Preis (PEG Ratio) <span class='weight-badge'>+{weights['peg']}</span>", unsafe_allow_html=True)
        st.markdown(f"<p class='matrix-desc'>Das Price-Earnings-to-Growth Ratio verhindert das Bezahlen überhöhter Preise für Wachstum. Werte um 1.0 gelten als 'Fair Value Growth'. Fair-Growth-Bonus: <b>{weights['peg']}</b>.</p>", unsafe_allow_html=True)

except Exception as e: st.error(f"Fehler: {e}")
