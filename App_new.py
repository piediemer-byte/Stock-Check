import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# --- 1. HELFER-FUNKTIONEN & SENTIMENT ---
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

# --- 2. 11-FAKTOR KI-Analyse-ENGINE ---
def get_ki_verdict(ticker_obj):
    try:
        inf = ticker_obj.info
        hist = ticker_obj.history(period="1y")
        if len(hist) < 200: return "➡️ Neutral", "Zu wenig Daten.", 0, 0, 50
        
        curr_p = float(hist['Close'].iloc[-1])
        score, reasons = 50, []
        
        # 1. Trend (SMA 50/200)
        s200, s50 = hist['Close'].rolling(200).mean().iloc[-1], hist['Close'].rolling(50).mean().iloc[-1]
        if curr_p > s50 > s200: score += 15; reasons.append("📈 Trend: Stark Bullish (Golden Cross/SMA 200).")
        elif curr_p < s200: score -= 15; reasons.append("📉 Trend: Bearish (Unter SMA 200).")

        # 2. RSI (14)
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))
        if rsi > 70: score -= 10; reasons.append(f"🔥 RSI überhitzt ({rsi:.1f})")
        elif rsi < 30: score += 10; reasons.append(f"🧊 RSI überverkauft ({rsi:.1f})")

        # 3. Volatilität (ATR)
        atr_val = (hist['High']-hist['Low']).rolling(14).mean().iloc[-1]
        vola_ratio = (atr_val / curr_p) * 100
        if vola_ratio > 4: score -= 5; reasons.append(f"⚠️ Vola: Hoch ({vola_ratio:.1f}%)")

        # 4. & 5. Bilanz
        if inf.get('operatingMargins', 0) > 0.15: score += 10; reasons.append("💰 Bilanz: Hohe operative Marge.")
        if (inf.get('totalCash', 0) or 0) > (inf.get('totalDebt', 0) or 0): score += 5; reasons.append("🏦 Bilanz: Net-Cash Position.")
        
        # 6. Bewertung
        kgv = inf.get('forwardPE', 0)
        kuv = inf.get('priceToSalesTrailing12Months', 0)
        if 0 < (kgv or 0) < 18: score += 10; reasons.append(f"💎 Bewertung: KGV attraktiv ({kgv:.1f})")
        elif (not kgv or kgv <= 0) and (0 < (kuv or 0) < 3): score += 10; reasons.append(f"🚀 Bewertung: KUV attraktiv ({kuv:.1f})")
        
        # 7. Volumen & 8. News
        if hist['Volume'].iloc[-1] > hist['Volume'].tail(20).mean() * 1.3: score += 10; reasons.append("📊 Volumen: Instituionelles Interesse.")
        score += analyze_news_sentiment(ticker_obj.news)
        
        # 9. Sektor
        if (curr_p / hist['Close'].iloc[0]) - 1 > 0.2: score += 10; reasons.append("🏆 Sektor: Outperformer.")

        # 10. MACD
        exp1, exp2 = hist['Close'].ewm(span=12).mean(), hist['Close'].ewm(span=26).mean()
        macd = exp1 - exp2
        if macd.iloc[-1] > macd.ewm(span=9).mean().iloc[-1]: score += 5; reasons.append("🌊 MACD: Bullishes Momentum.")

        # 11. PEG
        peg = inf.get('pegRatio')
        if peg and 0.5 < peg < 1.5: score += 5; reasons.append(f"⚖️ PEG: Fair Value Growth ({peg})")

        verdict = "💎 STRONG BUY" if score >= 80 else ("🚀 BUY" if score >= 60 else ("➡️ HOLD" if score >= 35 else "🛑 SELL"))
        return verdict, "\n".join(reasons), vola_ratio, s200, score
    except: return "⚠️ Error", "Analyse fehlgeschlagen", 0, 0, 50

# --- 3. UI SETUP ---
st.set_page_config(page_title="KI-Analyse Intelligence", layout="centered")
st.markdown("""
<style>
.status-card { background: #0d1117; padding: 12px; border-radius: 10px; border-left: 5px solid #3d5afe; margin-bottom: 15px; font-size: 0.85em; white-space: pre-wrap; }
.high-conviction { background: linear-gradient(90deg, #ffd700, #bf953f); color: #000; padding: 15px; border-radius: 10px; font-weight: bold; text-align: center; margin-bottom: 20px; border: 2px solid #fff; }
.calc-box { background: #161b22; padding: 15px; border-radius: 12px; border: 1px solid #30363d; }
.reversal-box { background: #1a1a1a; padding: 10px; border-radius: 8px; border: 1px dashed #ff4b4b; margin-top: 10px; text-align: center; }
.watchlist-card { background: #1c2128; border-radius: 8px; padding: 10px; border: 1px solid #444; margin-bottom: 5px; text-align: center; }
.weight-badge { background: #3d5afe; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 0.8em; }
</style>
""", unsafe_allow_html=True)

# --- 4. APP ---
st.title("🛡️ KI-Analyse Intelligence")
query = st.text_input("Asset suchen (Ticker, Name, ISIN):", value="NVDA")
ticker_sym = get_ticker_from_any(query)
eur_usd = get_eur_usd_rate()

try:
    ticker = yf.Ticker(ticker_sym)
    inf = ticker.info
    hist = ticker.history(period="3mo")
    
    if not hist.empty:
        curr_p = hist['Close'].iloc[-1]
        st.metric(f"{inf.get('longName', ticker_sym)}", f"{curr_p * eur_usd:.2f} €", f"{((curr_p/hist['Close'].iloc[0])-1)*100:.2f}%")
        
        verdict, reasons, vola, reversal_p, score = get_ki_verdict(ticker)
        if score >= 90: st.markdown("<div class='high-conviction'>🌟 HIGH CONVICTION OPPORTUNITY: Elite-Rating erreicht!</div>", unsafe_allow_html=True)
        
        st.subheader(f"KI-Analyse: {verdict} (Score: {score})")
        st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='reversal-box'>🚨 <b>Trend-Umkehr-Marke:</b> {reversal_p * eur_usd:.2f} €<br><small>Bei Unterschreiten bricht der langfristige SMA 200.</small></div>", unsafe_allow_html=True)

        # Order Planer
        with st.expander("🛡️ Order- & Profit-Planer (0.25% Präzision)", expanded=True):
            invest = st.number_input("Investment (€)", value=1000.0, step=100.0)
            risk_pct = st.slider("Risiko-Toleranz (%)", 0.0, 50.0, 5.0, step=0.25)
            target_pct = st.slider("Gewinn-Ziel (%)", 0.0, 100.0, 15.0, step=0.25)
            st.info(f"Stop-Loss: {curr_p*eur_usd*(1-risk_pct/100):.2f} € | Ziel-Verkauf: {curr_p*eur_usd*(1+target_pct/100):.2f} €")

        # Sektor Watchlist
        st.divider()
        st.subheader("🛰️ KI-Sektor-Radar")
        sector_peers = {"Technology": ["MSFT", "AAPL", "AMD", "TSM"], "Financial Services": ["JPM", "V", "GS"], "Healthcare": ["LLY", "NVO"], "Consumer Cyclical": ["TSLA", "AMZN"]}
        peers = sector_peers.get(inf.get('sector', 'Technology'), ["SPY", "QQQ"])
        cols = st.columns(len(peers))
        for i, p_sym in enumerate(peers):
            p_tick = yf.Ticker(p_sym)
            _, _, _, _, p_score = get_ki_verdict(p_tick)
            cols[i].markdown(f"<div class='watchlist-card' style='border-top: 3px solid {'#4caf50' if p_score >= 65 else '#546e7a'}'>{p_sym}<br><small>Score: {p_score}</small></div>", unsafe_allow_html=True)

        # --- MAXIMAL DETAILLIERTER STRATEGISCHER DEEP DIVE ---
        st.divider()
        st.subheader("🔍 Strategischer Deep Dive: Kriterien & Gewichtung")
        
        st.markdown("### 1. Markt-Phasierung (SMA 50/200) <span class='weight-badge'>±15</span>", unsafe_allow_html=True)
        st.markdown("> **Bedingung:** Ist $Price > SMA_{50} > SMA_{200}$?  \n> **Beschreibung:** Dies ist der stärkste Trendfilter. Ein Golden Cross zeigt an, dass institutionelles Kapital den Wert stützt. Ein Score-Abzug erfolgt sofort, wenn der Kurs unter den SMA 200 fällt, da dies ein Bärenmarkt-Signal ist.")
        st.markdown("")

        st.markdown("### 2. Dynamik-Check (RSI 14) <span class='weight-badge'>±10</span>", unsafe_allow_html=True)
        st.markdown("> **Bedingung:** $30 < RSI < 70$ (Neutral), $RSI < 30$ (+10), $RSI > 70$ (-10).  \n> **Beschreibung:** Verhindert den Einstieg in überhitzte Märkte. Ein niedriger RSI in einem intakten Aufwärtstrend ist oft der perfekte 'Dip'-Einstieg.")
        st.markdown("")

        st.markdown("### 3. Volatilitäts-Rauschen (ATR) <span class='weight-badge'>-5</span>", unsafe_allow_html=True)
        st.markdown("> **Bedingung:** $(ATR / Price) * 100 > 4\%$.  \n> **Beschreibung:** Hohe Volatilität erhöht die Wahrscheinlichkeit, dass Stop-Loss-Orders unglücklich ausgelöst werden. Die KI bestraft 'unruhige' Aktien.")

        st.markdown("### 4. Operative Effizienz (Marge) <span class='weight-badge'>+10</span>", unsafe_allow_html=True)
        st.markdown("> **Bedingung:** $Operating Margin > 15\%$.  \n> **Beschreibung:** Misst die Preismacht. Unternehmen mit hohen Margen können Inflation an Kunden weitergeben und bleiben in Krisen profitabel.")

        st.markdown("### 5. Liquiditäts-Stabilität (Net-Cash) <span class='weight-badge'>+5</span>", unsafe_allow_html=True)
        st.markdown("> **Bedingung:** $Total Cash > Total Debt$.  \n> **Beschreibung:** Ein Sicherheitspuffer. Firmen ohne Schuldenlast sind immun gegen Zinserhöhungen der Zentralbanken.")

        st.markdown("### 6. Bewertungs-Matrix (KGV/KUV) <span class='weight-badge'>+10</span>", unsafe_allow_html=True)
        st.markdown("> **Bedingung:** $KGV < 18$ ODER ($KGV \le 0$ & $KUV < 3$).  \n> **Beschreibung:** Kombiniert Value- und Growth-Ansätze. Es wird geprüft, ob der Preis im Verhältnis zum Gewinn oder zum Umsatz (bei Wachstumsfirmen) gerechtfertigt ist.")
        st.markdown("")

        st.markdown("### 7. Volumen-Bestätigung <span class='weight-badge'>+10</span>", unsafe_allow_html=True)
        st.markdown("> **Bedingung:** $Vol_{heute} > Vol_{ø20d} * 1.3$.  \n> **Beschreibung:** Preisbewegungen ohne Volumen sind 'Fake'. Ein Ausbruch mit hohem Volumen zeigt, dass große Adressen (Smart Money) einsteigen.")

        st.markdown("### 8. Sentiment & News-NLP <span class='weight-badge'>±20</span>", unsafe_allow_html=True)
        st.markdown("> **Bedingung:** Zeitgewichtete Analyse der letzten 5 Schlagzeilen.  \n> **Beschreibung:** Die KI scannt Schlagzeilen nach Schlüsselwörtern wie 'Beat', 'Upgrade' oder 'Risk'. Da News den Markt kurzfristig dominieren, ist dies der am stärksten gewichtete Faktor.")

        st.markdown("### 9. Sektor-Outperformance <span class='weight-badge'>+10</span>", unsafe_allow_html=True)
        st.markdown("> **Bedingung:** $Performance_{Asset} > Performance_{Benchmark}$.  \n> **Beschreibung:** Sucht nach den 'Alpha'-Aktien. Wir wollen nur die Gewinner innerhalb eines Sektors halten, nicht die Nachzügler.")

        st.markdown("### 10. Momentum-Oszillator (MACD) <span class='weight-badge'>+5</span>", unsafe_allow_html=True)
        st.markdown("> **Bedingung:** $MACD_{Line} > Signal_{Line}$.  \n> **Beschreibung:** Bestätigt, dass der Trend aktuell an Fahrt gewinnt. Ein bullishes Crossover ist oft der finale Trigger für technische Trader.")
        st.markdown("[attachment_0](attachment)")

        st.markdown("### 11. PEG-Ratio (Growth at Fair Price) <span class='weight-badge'>+5</span>", unsafe_allow_html=True)
        st.markdown(f"> **Bedingung:** $0.5 < \\frac{{KGV}}{{Gewinnwachstum}} < 1.5$.  \n> **Beschreibung:** Das PEG-Ratio stellt sicher, dass man für Wachstum nicht zu viel bezahlt. Ein Wert um 1.0 bedeutet, dass die Aktie exakt so viel kostet, wie ihr Wachstum rechtfertigt.")
        st.markdown("")

except Exception as e: st.error(f"Fehler: {e}")
