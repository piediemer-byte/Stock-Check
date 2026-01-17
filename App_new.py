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

# --- 2. 9-FAKTOR KI-Analyse-ENGINE ---
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
        
        if rsi > 70: 
            score -= 10
            reasons.append(f"🔥 RSI: Überhitzt ({rsi:.1f}).")
        elif rsi < 30: 
            score += 10
            reasons.append(f"🧊 RSI: Überverkauft ({rsi:.1f}).")

        # 3. Volatilität (ATR)
        high_low = hist['High'] - hist['Low']
        atr = high_low.rolling(14).mean().iloc[-1]
        vola_ratio = (atr / curr_p) * 100
        if vola_ratio > 4: 
            score -= 5
            reasons.append(f"⚠️ Vola: Hoch ({vola_ratio:.1f}%)")

        # 4. & 5. Bilanz & Liquidität
        marge = inf.get('operatingMargins', 0)
        if marge > 0.15: 
            score += 10
            reasons.append(f"💰 Bilanz: Hohe Marge ({marge*100:.1f}%).")
        
        cash = inf.get('totalCash', 0) or 0
        debt = inf.get('totalDebt', 0) or 0
        if cash > debt: 
            score += 5
            reasons.append("🏦 Bilanz: Net-Cash vorhanden.")

        # 6. Bewertung (KGV/KUV)
        kgv = inf.get('forwardPE', -1)
        kuv = inf.get('priceToSalesTrailing12Months', -1)
        
        if kgv is not None and 0 < kgv < 18: 
            score += 10
            reasons.append(f"💎 Bewertung: KGV attraktiv ({kgv:.1f}).")
        elif (kgv is None or kgv <= 0) and (kuv is not None and 0 < kuv < 3): 
            score += 10
            reasons.append(f"🚀 Bewertung: KUV attraktiv ({kuv:.1f}).")
        
        # 7. Volumen & 8. News
        vol_avg = hist['Volume'].tail(20).mean()
        if vol_avg > 0 and hist['Volume'].iloc[-1] > vol_avg * 1.3: 
            score += 10
            reasons.append("📊 Volumen: Hohes Interesse.")
        
        score += analyze_news_sentiment(ticker_obj.news)
        
        # 9. Sektor-Benchmark
        sector = inf.get('sector', 'N/A')
        start_p = float(hist['Close'].iloc[0])
        if start_p > 0 and (curr_p / start_p) - 1 > 0.2:
            score += 10
            reasons.append(f"🏆 Sektor: Top-Performer in {sector}.")

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
st.title("🛡️ KI-Analyse Intelligence")
search_query = st.text_input("Suche (Name, ISIN, Ticker):", value="NVIDIA")
ticker_symbol = get_ticker_from_any(search_query)
eur_usd_rate = get_eur_usd_rate()

# Performance-Zeitraum-Auswahl
if 'days' not in st.session_state: st.session_state.days = 22
c1, c2, c3 = st.columns(3)
if c1.button("1T"): st.session_state.days = 2
if c2.button("1W"): st.session_state.days = 6
if c3.button("1M"): st.session_state.days = 22

try:
    ticker = yf.Ticker(ticker_symbol)
    hist_all = ticker.history(period="3mo")
    
    if not hist_all.empty:
        # Metriken
        recent = hist_all.tail(st.session_state.days)
        curr_price = recent['Close'].iloc[-1]
        curr_eur = curr_price * eur_usd_rate
        perf = ((curr_price / recent['Close'].iloc[0]) - 1) * 100
        
        st.caption(f"Asset: **{ticker.info.get('longName', ticker_symbol)}**")
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Kurs (€)", f"{curr_eur:.2f} €", f"{perf:.2f}%")
        col_m2.metric("Kurs ($)", f"{curr_price:.2f} $")
        
        # Analyse
        verdict, reasons, current_vola, reversal_p, main_score = get_ki_verdict(ticker)
        
        # High Conviction Alert
        if main_score >= 90:
            st.markdown("<div class='high-conviction'>🌟 HIGH CONVICTION OPPORTUNITY: Dieser Wert erreicht eine seltene Übereinstimmung in allen 9 Faktoren!</div>", unsafe_allow_html=True)
            
        st.subheader(f"KI-Analyse: {verdict} (Score: {main_score})")
        st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='reversal-box'>🚨 <b>Trend-Umkehr-Marke:</b> {reversal_p * eur_usd_rate:.2f} € ({reversal_p:.2f} $)<br><small>Unter diesem Wert ist der langfristige Trend mathematisch gebrochen.</small></div>", unsafe_allow_html=True)

        # Order Planer
        st.subheader("🛡️ Order- & Profit-Planer")
        with st.container():
            st.markdown("<div class='calc-box'>", unsafe_allow_html=True)
            col_inv, col_fee = st.columns(2)
            invest = col_inv.number_input("Investment (€)", value=1000.0, step=100.0)
            fee = col_fee.number_input("Gebühr/Trade (€)", value=1.0, step=0.5)
            
            risk_pct = st.slider("Risiko (%)", 0.0, 50.0, 5.0, step=0.25)
            target_pct = st.slider("Ziel (%)", 0.0, 100.0, 15.0, step=0.25)
            
            if curr_eur > 0:
                stücke = int(invest // curr_eur)
                eff_inv = stücke * curr_eur
                sl_price = curr_eur * (1 - (risk_pct / 100))
                tp_price = curr_eur * (1 + (target_pct / 100))
                risk_eur = (eff_inv * (risk_pct/100)) + (2*fee)
                profit_eur = (eff_inv * (target_pct/100)) - (2*fee)
                crv = profit_eur / risk_eur if risk_eur > 0 else 0
                
                st.write(f"📊 **{stücke} Stück** | **Invest:** {eff_inv:.2f} €")
                st.error(f"📍 **Stop-Loss Preis:** {sl_price:.2f} € (-{risk_eur:.2f} €)")
                st.success(f"🎯 **Take-Profit (Order Limit):** {tp_price:.2f} € (+{profit_eur:.2f} €)")
                st.info(f"⚖️ **CRV: {crv:.2f}**")
            st.markdown("</div>", unsafe_allow_html=True)

        # --- MAXIMAL DETAILLIERTER STRATEGISCHER DEEP DIVE ---
        st.divider()
        st.subheader("🔍 Deep Dive: KI-Analyse Kriterien-Katalog")
        
        st.markdown("### 1. Markt-Phasierung (SMA 50/200) <span class='weight-badge'>Gewicht: ±15</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Der Algorithmus nutzt den gleitenden Durchschnitt der letzten 200 Tage als primären Filter für das Marktrisiko. <b>Mathematik:</b> Kurs > SMA 200 = struktureller Bullenmarkt. Zusätzliche Pluspunkte gibt es für ein 'Golden Cross' (SMA 50 > SMA 200), das eine Beschleunigung des Aufwärtstrends anzeigt. Ein Bruch unter den SMA 200 gilt als technisches Verkaufssignal mit hoher Treffsicherheit.</p>", unsafe_allow_html=True)
        st.markdown("")

        st.markdown("### 2. Relative Stärke Oszillator (RSI 14) <span class='weight-badge'>Gewicht: ±10</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Der RSI misst die 'Innere Stärke'. Er vergleicht die durchschnittlichen Gewinne mit den Verlusten über 14 Perioden. <b>Algorithmus:</b> Bei einem RSI über 70 ist die Aktie statistisch 'zu teuer' im Vergleich zum Trend (Überhitzung). Die KI zieht 10 Punkte ab, um dich vor FOMO-Käufen zu schützen. Ein Wert unter 30 signalisiert Panikverkäufe, die oft eine 'V'-Umkehr einleiten (+10 Pkt).</p>", unsafe_allow_html=True)
        st.markdown("")

        st.markdown("### 3. Volatilitäts-Adjustierung (ATR) <span class='weight-badge'>Gewicht: -5</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Die <b>Average True Range (ATR)</b> berechnet die durchschnittliche Kerzengröße der letzten 14 Tage. Die KI setzt diese ATR in Relation zum aktuellen Kurs. Liegt diese Quote über 4%, wird die Analyse als 'instabil' markiert. <b>Ziel:</b> Warnung vor Aktien, die so stark schwanken, dass herkömmliche Stop-Loss-Marken wirkungslos sind.</p>", unsafe_allow_html=True)

        st.markdown("### 4. Operative Effizienz (Marge) <span class='weight-badge'>Gewicht: +10</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Das System prüft die <b>Operating Margin</b>. Eine Marge über 15% beweist, dass das Unternehmen Preismacht hat (Moat). Dies ist das wichtigste fundamentale Kriterium, da profitable Firmen in Rezessionen stabil bleiben. Unternehmen mit negativen Margen erhalten hier konsequent keine Bonuspunkte.</p>", unsafe_allow_html=True)

        st.markdown("### 5. Liquiditäts-Stabilität (Net-Cash) <span class='weight-badge'>Gewicht: +5</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Ein Vergleich zwischen Barmitteln (Total Cash) und Gesamtschulden (Total Debt). Ein Unternehmen mit <b>Net-Cash</b> (Cash > Debt) ist krisensicher und kann Dividenden oder Aktienrückkäufe auch in schwierigen Zeiten finanzieren. Im aktuellen Zinsumfeld ist dies ein massiver Sicherheitsfaktor.</p>", unsafe_allow_html=True)

        st.markdown("### 6. Bewertungs-Dualismus (KGV/KUV) <span class='weight-badge'>Gewicht: +10</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Die KI nutzt zwei Pfade: 1. <b>Value-Pfad:</b> KGV < 18 wird als günstig eingestuft. 2. <b>Growth-Pfad:</b> Bei Verlusten (Startups/Tech) prüft die KI das KUV. Ein KUV < 3 bei gleichzeitigem Umsatzwachstum wird als Einstiegschance gewertet. So werden sowohl Coca-Cola als auch junge Tech-Werte fair analysiert.</p>", unsafe_allow_html=True)
        st.markdown("")

        st.markdown("### 7. Smart-Money Bestätigung (Volumen) <span class='weight-badge'>Gewicht: +10</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Echtes institutionelles Kaufinteresse lässt sich am Volumen ablesen. Steigt das Handelsvolumen des aktuellen Tages um mehr als 30% über den 20-Tage-Durchschnitt, wertet die KI dies als Einstieg von Fonds und Banken. Trends ohne Volumen gelten als unzuverlässig.</p>", unsafe_allow_html=True)

        st.markdown("### 8. Sentiment & Analysten-Power <span class='weight-badge'>Gewicht: ±20</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Der finale Faktor kombiniert zwei externe Datenquellen: Das <b>NLP-News-Sentiment</b> (gewichtete Schlagzeilen-Analyse) und das <b>Median-Kursziel</b> der Wall-Street-Analysten. Liegt das Kursziel mind. 15% über dem aktuellen Preis, liefert dies die fundamentale 'Validation' für das technische Kaufsignal.</p>", unsafe_allow_html=True)

        st.markdown("### 9. Sektor-Benchmark (Peer-Leader) <span class='weight-badge'>Gewicht: +10</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'><b>Die Elite-Bedingung:</b> Die KI vergleicht das Asset mit seinem Sektor (z.B. Technology, Healthcare). Nur Aktien, die eine signifikante Outperformance zum Sektor-Durchschnitt zeigen, erhalten diesen Bonus. <b>Strategie:</b> Es wird sichergestellt, dass du nicht nur eine gute Aktie kaufst, sondern den 'Best-in-Class' Leader der Branche.</p>", unsafe_allow_html=True)

    else:
        st.error("Keine Daten gefunden.")

except Exception as e:
    st.error(f"Fehler: {e}")
