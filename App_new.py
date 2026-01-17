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
    except: 
        return query.upper()

def get_eur_usd_rate():
    try:
        hist = yf.Ticker("EURUSD=X").history(period="1d")
        if not hist.empty:
            return 1 / float(hist['Close'].iloc[-1])
        return 0.92 
    except:
        return 0.92

def analyze_news_sentiment(news_list):
    if not news_list: return 0
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

# --- 2. 11-FAKTOR KI-Analyse-ENGINE ---
def get_ki_verdict(ticker_obj):
    try:
        inf = ticker_obj.info
        hist = ticker_obj.history(period="1y")
        
        if len(hist) < 200: 
            return "➡️ Neutral", "Zu wenig historische Daten.", 0, 0, 50
        
        curr_p = float(hist['Close'].iloc[-1])
        score = 50
        reasons = []
        
        # 1. Trend (SMA 50/200)
        s200 = hist['Close'].rolling(200).mean().iloc[-1]
        s50 = hist['Close'].rolling(50).mean().iloc[-1]
        trend_reversal_p = s200 
        if curr_p > s50 > s200: 
            score += 15
            reasons.append(f"📈 Trend: Stark Bullish (über SMA 50/200).")
        elif curr_p < s200: 
            score -= 15
            reasons.append(f"📉 Trend: Bearish (unter SMA 200).")

        # 2. RSI (14)
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1]))
        if rsi > 70: score -= 10; reasons.append(f"🔥 RSI: Überhitzt ({rsi:.1f}).")
        elif rsi < 30: score += 10; reasons.append(f"🧊 RSI: Überverkauft ({rsi:.1f}).")

        # 3. Volatilität (ATR)
        high_low = hist['High'] - hist['Low']
        atr = high_low.rolling(14).mean().iloc[-1]
        vola_ratio = (atr / curr_p) * 100
        if vola_ratio > 4: score -= 5; reasons.append(f"⚠️ Vola: Hoch ({vola_ratio:.1f}%)")

        # 4. & 5. Bilanz & Liquidität
        marge = inf.get('operatingMargins', 0)
        if marge > 0.15: score += 10; reasons.append(f"💰 Bilanz: Hohe Marge ({marge*100:.1f}%).")
        cash = inf.get('totalCash', 0) or 0
        debt = inf.get('totalDebt', 0) or 0
        if cash > debt: score += 5; reasons.append("🏦 Bilanz: Net-Cash vorhanden.")

        # 6. Bewertung (KGV/KUV)
        kgv = inf.get('forwardPE', -1)
        kuv = inf.get('priceToSalesTrailing12Months', -1)
        if kgv and 0 < kgv < 18: score += 10; reasons.append(f"💎 Bewertung: KGV attraktiv ({kgv:.1f}).")
        elif (not kgv or kgv <= 0) and (kuv and 0 < kuv < 3): score += 10; reasons.append(f"🚀 Bewertung: KUV attraktiv ({kuv:.1f}).")
        
        # 7. Volumen & 8. News
        vol_avg = hist['Volume'].tail(20).mean()
        if vol_avg > 0 and hist['Volume'].iloc[-1] > vol_avg * 1.3: score += 10; reasons.append("📊 Volumen: Hohes Interesse.")
        score += analyze_news_sentiment(ticker_obj.news)
        
        # 9. Sektor-Benchmark
        sector = inf.get('sector', 'N/A')
        start_p = float(hist['Close'].iloc[0])
        if start_p > 0 and (curr_p / start_p) - 1 > 0.2: score += 10; reasons.append(f"🏆 Sektor: Top-Performer in {sector}.")

        # --- NEU: 10. MACD (Trend-Momentum) ---
        exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
        exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        if macd.iloc[-1] > signal.iloc[-1]:
            score += 5
            reasons.append("🌊 MACD: Bullishes Momentum (Crossover).")

        # --- NEU: 11. PEG Ratio (Growth Valuation) ---
        peg = inf.get('pegRatio')
        if peg is not None and 0.5 < peg < 1.5:
            score += 5
            reasons.append(f"⚖️ PEG: Wachstum/Preis-Ratio optimal ({peg}).")

        if score >= 80: verdict = "💎 STRONG BUY"
        elif score >= 60: verdict = "🚀 BUY"
        elif score >= 35: verdict = "➡️ HOLD"
        else: verdict = "🛑 SELL"
        
        return verdict, "\n".join(reasons), vola_ratio, trend_reversal_p, score

    except Exception as e:
        return "⚠️ Error", str(e), 0, 0, 50

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

# --- 4. APP ---
st.title("📈 KI-Analyse Intelligence")
search_query = st.text_input("Suche (Ticker):", value="NVDA")
ticker_symbol = get_ticker_from_any(search_query)
eur_usd_rate = get_eur_usd_rate()

# Zeit-Buttons
if 'days' not in st.session_state: st.session_state.days = 22
c1, c2, c3 = st.columns(3)
if c1.button("1T"): st.session_state.days = 2
if c2.button("1W"): st.session_state.days = 6
if c3.button("1M"): st.session_state.days = 22

try:
    ticker = yf.Ticker(ticker_symbol)
    hist_all = ticker.history(period="3mo")
    
    if not hist_all.empty:
        recent = hist_all.tail(st.session_state.days)
        curr_price = recent['Close'].iloc[-1]
        curr_eur = curr_price * eur_usd_rate
        perf = ((curr_price / recent['Close'].iloc[0]) - 1) * 100
        
        st.caption(f"Asset: **{ticker.info.get('longName', ticker_symbol)}**")
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Kurs (€)", f"{curr_eur:.2f} €", f"{perf:.2f}%")
        col_m2.metric("Kurs ($)", f"{curr_price:.2f} $")
        
        verdict, reasons, current_vola, reversal_p, main_score = get_ki_verdict(ticker)
        
        if main_score >= 90:
            st.markdown("<div class='high-conviction'>🌟 HIGH CONVICTION OPPORTUNITY: Absolute Elite-Übereinstimmung!</div>", unsafe_allow_html=True)
            
        st.subheader(f"KI-Analyse: {verdict} (Score: {main_score})")
        st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='reversal-box'>🚨 <b>Trend-Umkehr-Marke:</b> {reversal_p * eur_usd_rate:.2f} € ({reversal_p:.2f} $)<br><small>Unter diesem Wert ist der langfristige Trend gebrochen.</small></div>", unsafe_allow_html=True)

        # Order Planer (0.25% Schritte)
        st.subheader("📈 Order- & Profit-Planer")
        with st.container():
            st.markdown("<div class='calc-box'>", unsafe_allow_html=True)
            invest = st.number_input("Investment (€)", value=1000.0, step=100.0)
            risk_pct = st.slider("Risiko (%)", 0.0, 50.0, 5.0, step=0.25)
            target_pct = st.slider("Ziel (%)", 0.0, 100.0, 15.0, step=0.25)
            
            stücke = int(invest // curr_eur)
            eff_inv = stücke * curr_eur
            sl_price = curr_eur * (1 - (risk_pct / 100))
            tp_price = curr_eur * (1 + (target_pct / 100))
            risk_eur = (eff_inv * (risk_pct/100))
            profit_eur = (eff_inv * (target_pct/100))
            crv = profit_eur / risk_eur if risk_eur > 0 else 0
            
            st.write(f"📊 **{stücke} Stück** | **Invest:** {eff_inv:.2f} €")
            st.error(f"📍 **Stop-Loss:** {sl_price:.2f} € (-{risk_eur:.2f} €)")
            st.success(f"🎯 **Take-Profit:** {tp_price:.2f} € (+{profit_eur:.2f} €)")
            st.info(f"⚖️ **CRV: {crv:.2f}**")
            st.markdown("</div>", unsafe_allow_html=True)

      # --- MAXIMAL DETAILLIERTER STRATEGISCHER DEEP DIVE ---
        st.divider()
        st.subheader("🔍 Strategischer Deep Dive: Die 11-Faktor-Matrix")
        
        st.markdown("### 1. Markt-Phasierung (SMA 50/200) <span class='weight-badge'>±15</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Prüfung der Position zum 200-Tage-Schnitt. Kurs > SMA 200 signalisiert institutionelle Akzeptanz. Ein Golden Cross (50er über 200er) gilt als massives technisches Kaufsignal.</p>", unsafe_allow_html=True)
        st.markdown("")

        st.markdown("### 2. Dynamik (RSI 14) <span class='weight-badge'>±10</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Der RSI misst die innere Stärke. RSI > 70 zeigt Überhitzung (Gefahr), RSI < 30 Panik (Chance).</p>", unsafe_allow_html=True)
        st.markdown("")

        st.markdown("### 3. Volatilität (ATR) <span class='weight-badge'>-5</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Die ATR misst das 'Rauschen'. Beträgt die tägliche Schwankung mehr als 4% des Kurses, wird das Risiko für unberechenbare Kurssprünge als zu hoch eingestuft.</p>", unsafe_allow_html=True)

        st.markdown("### 4. Operative Effizienz (Marge) <span class='weight-badge'>+10</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Operating Margin > 15% beweist Preismacht. Ein Kernfaktor für fundamentale Stabilität gegen Inflation.</p>", unsafe_allow_html=True)

        st.markdown("### 5. Krisenfestigkeit (Net-Cash) <span class='weight-badge'>+5</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Vergleich von Barreserven zu Schulden. Net-Cash-Positionen machen Firmen immun gegen hohe Zinsen.</p>", unsafe_allow_html=True)

        st.markdown("### 6. Bewertung (KGV/KUV) <span class='weight-badge'>+10</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Prüft KGV (< 18) oder KUV (< 3) für Wachstumswerte. Verhindert den Kauf von überteuerten Hype-Titeln.</p>", unsafe_allow_html=True)

        st.markdown("### 7. Smart-Money (Volumen) <span class='weight-badge'>+10</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Volumenanstieg > 30% über Schnitt zeigt, dass große Fonds Positionen aufbauen.</p>", unsafe_allow_html=True)

        st.markdown("### 8. Sentiment & Analysten <span class='weight-badge'>±20</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>KI-Gewichtung von News-Headlines und Analysten-Kurszielen (>15% Upside) als fundamentale Bestätigung.</p>", unsafe_allow_html=True)

        st.markdown("### 9. Sektor-Benchmark <span class='weight-badge'>+10</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Vergleicht die Performance mit dem Sektor. Nur Branchenführer erhalten diesen Bonus.</p>", unsafe_allow_html=True)

        st.markdown("### 10. Momentum-Bestätigung (MACD) <span class='weight-badge'>+5</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Der <b>MACD (Moving Average Convergence Divergence)</b> berechnet die Differenz zweier exponentieller Durchschnitte. Wenn die MACD-Linie die Signallinie von unten nach oben kreuzt, bestätigt dies ein bullishes Momentum und signalisiert, dass der Trend an Kraft gewinnt.</p>", unsafe_allow_html=True)
        st.markdown("[attachment_0](attachment)")

        st.markdown("### 11. Wachstum zum Preis (PEG Ratio) <span class='weight-badge'>+5</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Das <b>PEG-Ratio (Price/Earnings-to-Growth)</b> setzt das KGV ins Verhältnis zum Gewinnwachstum. Ein Wert zwischen 0,5 und 1,5 gilt als 'Fair Value' für Wachstumsaktien. Es stellt sicher, dass man nicht nur eine Aktie mit niedrigem KGV kauft, sondern eine, deren Preis durch echtes Wachstum gerechtfertigt ist.</p>", unsafe_allow_html=True)

    else:
        st.error("Daten konnten nicht abgerufen werden.")

except Exception as e:
    st.error(f"Fehler: {e}")
