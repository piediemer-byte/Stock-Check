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

# --- 2. 11-FAKTOR KI-Analyse-ENGINE ---
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

        # 4. Marge & 5. Cash
        if inf.get('operatingMargins', 0) > 0.15: score += w['marge']; reasons.append(f"💰 Marge: Stark (+{w['marge']})")
        if (inf.get('totalCash', 0) or 0) > (inf.get('totalDebt', 0) or 0): score += w['cash']; reasons.append(f"🏦 Net-Cash (+{w['cash']})")
        
        # 6. KGV
        kgv = inf.get('forwardPE', 0)
        if 0 < (kgv or 0) < 18: score += w['val']; reasons.append(f"💎 KGV attraktiv (+{w['val']})")
        
        # 7. Volumen & 8. Banken/News
        if hist['Volume'].iloc[-1] > hist['Volume'].tail(20).mean() * 1.3: score += w['vol']; reasons.append(f"📊 Volumen: Hoch (+{w['vol']})")
        
        target_p = inf.get('targetMeanPrice')
        bank_upside = ((target_p / curr_p) - 1) if target_p else 0
        news_raw = analyze_news_sentiment(ticker_obj.news)
        
        analyst_score = (news_raw * 0.5) + (10 if bank_upside > 0.15 else 0)
        score += analyst_score * (w['news'] / 10)
        if target_p: reasons.append(f"🏛️ Bank-Ziel: {target_p:.2f}$ ({bank_upside*100:+.1f}%)")

        # 9. Sektor, 10. MACD, 11. PEG
        if (curr_p / hist['Close'].iloc[0]) - 1 > 0.2: score += w['sector']; reasons.append(f"🏆 Sektor-Leader (+{w['sector']})")
        exp1, exp2 = hist['Close'].ewm(span=12).mean(), hist['Close'].ewm(span=26).mean()
        if (exp1 - exp2).iloc[-1] > (exp1 - exp2).ewm(span=9).mean().iloc[-1]: score += w['macd']; reasons.append(f"🌊 MACD: Bullish (+{w['macd']})")
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
.calc-box { background: #161b22; padding: 15px; border-radius: 12px; border: 1px solid #30363d; margin-top: 10px; }
.reversal-box { background: #1a1a1a; padding: 10px; border-radius: 8px; border: 1px dashed #ff4b4b; margin-top: 10px; text-align: center; }
.weight-badge { background: #3d5afe; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 0.8em; }
.matrix-desc { font-size: 0.88em; color: #cfd8dc; line-height: 1.6; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR: GEWICHTUNG ---
st.sidebar.header("⚙️ Strategie-Gewichtung")
weights = {k: st.sidebar.slider(f"{i+1}. {label}", 0, 40, v) for i, (k, label, v) in enumerate([
    ('trend', 'Trend (SMA)', 15), ('rsi', 'Dynamik (RSI)', 10), ('vola', 'Vola (ATR)', 5),
    ('marge', 'Marge', 10), ('cash', 'Sicherheit', 5), ('val', 'Bewertung', 10),
    ('vol', 'Volumen', 10), ('news', 'Banken/News', 25), ('sector', 'Sektor', 10),
    ('macd', 'Momentum', 5), ('peg', 'Wachstum (PEG)', 5)])}

# --- 4. APP HAUPTTEIL ---
st.title("🛡️ KI-Analyse Intelligence")
query = st.text_input("Asset (Ticker):", value="NVDA")
ticker_sym = get_ticker_from_any(query)
eur_usd = get_eur_usd_rate()

try:
    ticker = yf.Ticker(ticker_sym)
    inf, hist = ticker.info, ticker.history(period="3mo")
    
    if not hist.empty:
        curr_p = hist['Close'].iloc[-1]
        perf = ((curr_p / hist['Close'].iloc[0]) - 1) * 100
        
        st.subheader(f"{inf.get('longName', ticker_sym)}")
        c_m1, c_m2 = st.columns(2)
        c_m1.metric("Kurs (€)", f"{curr_p * eur_usd:.2f} €", f"{perf:+.2f}%")
        c_m2.metric("Kurs ($)", f"{curr_p:.2f} $")
        
        verdict, reasons, vola, reversal_p, score = get_ki_verdict(ticker, weights)
        if score >= 90: st.markdown("<div class='high-conviction'>🌟 HIGH CONVICTION OPPORTUNITY</div>", unsafe_allow_html=True)
        
        st.subheader(f"KI-Analyse: {verdict} (Score: {score})")
        st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='reversal-box'>🚨 Trend-Umkehr-Marke: {reversal_p * eur_usd:.2f} €</div>", unsafe_allow_html=True)

        # --- NEU: CRV BERECHNUNG & ORDER PLANER ---
        st.subheader("🛡️ Order- & CRV-Planer")
        with st.container():
            st.markdown("<div class='calc-box'>", unsafe_allow_html=True)
            invest = st.number_input("Investment (€)", value=1000.0, step=100.0)
            risk_pct = st.slider("Risiko / Stop-Loss (%)", 0.0, 50.0, 5.0, step=0.25)
            target_pct = st.slider("Gewinnziel (%)", 0.0, 100.0, 15.0, step=0.25)
            
            stücke = int(invest // (curr_p * eur_usd))
            eff_inv = stücke * (curr_p * eur_usd)
            risk_eur = eff_inv * (risk_pct / 100)
            profit_eur = eff_inv * (target_pct / 100)
            crv = profit_eur / risk_eur if risk_eur > 0 else 0
            
            col_p1, col_p2, col_p3 = st.columns(3)
            col_p1.write(f"📦 **{stücke} Stück**")
            col_p2.write(f"💰 **{eff_inv:.2f} € Invest**")
            col_p3.write(f"⚖️ **CRV: {crv:.2f}**")
            
            st.error(f"📍 Stop-Loss: {(curr_p*eur_usd)*(1-risk_pct/100):.2f} € (Risiko: -{risk_eur:.2f} €)")
            st.success(f"🎯 Take-Profit: {(curr_p*eur_usd)*(1+target_pct/100):.2f} € (Chance: +{profit_eur:.2f} €)")
            st.markdown("</div>", unsafe_allow_html=True)

        # --- DETAILLIERTER DEEP DIVE ---
        st.divider()
        st.subheader("🔍 Strategischer Deep Dive: Die 11-Faktor-Matrix")
        
        factors = [
            ("1. Markt-Phasierung (SMA)", "trend", "Kurs > SMA 50 > SMA 200. Institutioneller Trend-Check."),
            ("2. Dynamik (RSI 14)", "rsi", "Überverkauft (<30) oder Überhitzt (>70). Timing-Filter."),
            ("3. Volatilität (ATR)", "vola", "Bestraft Rauschen > 4%. Schützt vor 'Stop-Loss-Hunting'."),
            ("4. Operative Effizienz", "marge", "Marge > 15%. Beweis für Preismacht und Moat."),
            ("5. Sicherheit (Net-Cash)", "cash", "Cash > Schulden. Immunität gegen Zinssteigerungen."),
            ("6. Bewertung (KGV)", "val", "KGV < 18. Schutz vor Überbewertung (Value-Check)."),
            ("7. Smart-Money Flow", "vol", "Volumen > 130% Schnitt. Bestätigung durch Großkapital."),
            ("8. Banken-Targets & News", "news", "Tagesaktueller Abgleich mit Kurszielen (z.B. Goldman, JPM) + NLP Sentiment."),
            ("9. Sektor-Stärke", "sector", "Outperformance zum Gesamtmarkt. Leader vs. Laggard."),
            ("10. Momentum (MACD)", "macd", "Technisches Kaufsignal durch Durchschnitts-Konvergenz."),
            ("11. Wachstumspreis (PEG)", "peg", "PEG 0.5 - 1.5. Wachstum zum fairen Preis kaufen.")
        ]

        for title, key, desc in factors:
            st.markdown(f"### {title} <span class='weight-badge'>±{weights[key]}</span>", unsafe_allow_html=True)
            st.markdown(f"<p class='matrix-desc'>{desc}<br>Deine Strategie gewichtet diesen Faktor aktuell mit <b>{weights[key]} Punkten</b>.</p>", unsafe_allow_html=True)
            if "SMA" in title: 
            if "RSI" in title: 
            if "Banken" in title: 
            if "MACD" in title: [attachment_0](attachment)

except Exception as e: st.error(f"Fehler: {e}")
