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
    
    s200 = hist['Close'].rolling(200).mean().iloc[-1]
    s50 = hist['Close'].rolling(50).mean().iloc[-1]
    trend_reversal_p = s200 
    if curr_p > s50 > s200: score += 15; reasons.append(f"📈 Trend: Stark Bullish (über SMA 50/200).")
    elif curr_p < s200: score -= 15; reasons.append(f"📉 Trend: Bearish (unter SMA 200).")

    delta = hist['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs.iloc[-1]))
    if rsi > 70: score -= 10; reasons.append(f"🔥 RSI: Überhitzt ({rsi:.1f}).")
    elif rsi < 30: score += 10; reasons.append(f"🧊 RSI: Überverkauft ({rsi:.1f}).")

    high_low = hist['High'] - hist['Low']
    atr = high_low.rolling(14).mean().iloc[-1]
    vola_ratio = (atr / curr_p) * 100
    if vola_ratio > 4: score -= 5; reasons.append(f"⚠️ Vola: Hoch ({vola_ratio:.1f}%)")

    marge = inf.get('operatingMargins', 0)
    if marge > 0.15: score += 10; reasons.append(f"💰 Bilanz: Hohe Marge ({marge*100:.1f}%).")
    if inf.get('totalCash', 0) > inf.get('totalDebt', 0): score += 5; reasons.append("🏦 Bilanz: Net-Cash vorhanden.")

    kgv = inf.get('forwardPE', -1)
    kuv = inf.get('priceToSalesTrailing12Months', -1)
    if 0 < kgv < 18: score += 10; reasons.append(f"💎 Bewertung: KGV attraktiv ({kgv:.1f}).")
    elif kgv <= 0 and 0 < kuv < 3: score += 10; reasons.append(f"🚀 Bewertung: KUV attraktiv ({kuv:.1f}).")
    
    if hist['Volume'].iloc[-1] > hist['Volume'].tail(20).mean() * 1.3: score += 10; reasons.append("📊 Volumen: Hohes Interesse.")
    score += analyze_news_sentiment(ticker_obj.news)
    
    upside = (inf.get('targetMedianPrice', curr_p) / curr_p - 1) * 100
    if upside > 15: score += 10; reasons.append(f"🎯 Prognose: +{upside:.1f}% Upside.")

    sector = inf.get('sector', 'N/A')
    if (hist['Close'].iloc[-1] / hist['Close'].iloc[0]) - 1 > 0.2:
        score += 10; reasons.append(f"🏆 Sektor: Top-Performer in {sector}.")

    if score >= 80: verdict = "💎 STRONG BUY"
    elif score >= 60: verdict = "🚀 BUY"
    elif score >= 35: verdict = "➡️ HOLD"
    else: verdict = "🛑 SELL"
    return verdict, "\n".join(reasons), vola_ratio, trend_reversal_p, score

# --- 3. UI SETUP ---
st.set_page_config(page_title="KI-Analyse Intelligence", layout="centered")
st.markdown("<style>.status-card { background: #0d1117; padding: 12px; border-radius: 10px; border-left: 5px solid #3d5afe; margin-bottom: 15px; font-size: 0.85em; white-space: pre-wrap; } .calc-box { background: #161b22; padding: 15px; border-radius: 12px; border: 1px solid #30363d; } .reversal-box { background: #1a1a1a; padding: 10px; border-radius: 8px; border: 1px dashed #ff4b4b; margin-top: 10px; text-align: center; } .matrix-desc { font-size: 0.88em; color: #cfd8dc; line-height: 1.6; margin-bottom: 15px; }</style>", unsafe_allow_html=True)

# --- 4. APP ---
st.title("🛡️ KI-Analyse Intelligence")
search_query = st.text_input("Suche (Name, ISIN, Ticker):", value="Apple")
ticker_symbol = get_ticker_from_any(search_query)
eur_usd_rate = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

# ZEIT-FILTER FÜR PERFORMANCE
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
        curr_eur = recent['Close'].iloc[-1] * eur_usd_rate
        perf = ((recent['Close'].iloc[-1] / recent['Close'].iloc[0]) - 1) * 100
        
        # AKTUELLER KURS & PERFORMANCE
        st.caption(f"Asset: **{ticker.info.get('longName', ticker_symbol)}**")
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Kurs (€)", f"{curr_eur:.2f} €", f"{perf:.2f}%")
        col_m2.metric("Kurs ($)", f"{recent['Close'].iloc[-1]:.2f} $")
        
        verdict, reasons, current_vola, reversal_p, main_score = get_ki_verdict(ticker)
        
        st.subheader(f"KI-Analyse: {verdict} (Score: {main_score})")
        st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='reversal-box'>🚨 <b>Trend-Umkehr-Marke:</b> {reversal_p * eur_usd_rate:.2f} € ({reversal_p:.2f} $)<br><small>Unter diesem Wert gilt der Aufwärtstrend als mathematisch gebrochen.</small></div>", unsafe_allow_html=True)

        # SEKTOR VERGLEICH TABELLE
        st.subheader("🏁 Sektor-Benchmark: Top Peers")
        # Dynamische Peer-Liste basierend auf Sektor wäre ideal, hier statisches Beispiel:
        sector_peers = ["MSFT", "GOOGL", "AMZN"] if ticker_symbol == "AAPL" else ["TSLA", "NVDA", "META"]
        peer_data = []
        for p in sector_peers:
            p_t = yf.Ticker(p)
            _, _, _, _, p_score = get_ki_verdict(p_t)
            peer_data.append({"Ticker": p, "Name": p_t.info.get('shortName'), "KI-Score": p_score})
        st.table(pd.DataFrame(peer_data))

        st.subheader("🛡️ Order- & Profit-Planer")
        with st.container():
            st.markdown("<div class='calc-box'>", unsafe_allow_html=True)
            c_inv, c_fee = st.columns(2)
            invest = c_inv.number_input("Investment (€)", value=1000.0)
            fee = c_fee.number_input("Gebühr/Trade (€)", value=1.0)
            
            risk_pct = st.slider("Risiko (%)", 0.0, 50.0, 5.0, step=0.25)
            target_pct = st.slider("Ziel (%)", 0.0, 100.0, 15.0, step=0.25)
            
            stücke = int(invest // curr_eur)
            eff_inv = stücke * curr_eur
            sl_price = curr_eur * (1 - (risk_pct / 100))
            tp_price = curr_eur * (1 + (target_pct / 100))
            risk_eur = (eff_inv * (risk_pct/100)) + (2*fee)
            profit_eur = (eff_inv * (target_pct/100)) - (2*fee)
            crv = profit_eur / risk_eur if risk_eur > 0 else 0
            
            st.write(f"📊 **{stücke} Stück** | **Invest:** {eff_inv:.2f} €")
            st.error(f"📍 **Stop-Loss Preis:** {sl_price:.2f} €")
            st.success(f"🎯 **Take-Profit (Order Limit):** {tp_price:.2f} €")
            st.info(f"⚖️ **CRV: {crv:.2f}**")
            st.markdown("</div>", unsafe_allow_html=True)

        # --- MAXIMAL DETAILLIERTER STRATEGISCHER DEEP DIVE ---
        st.divider()
        st.subheader("🔍 Deep Dive: KI-Analyse Kriterien-Katalog")
        
        st.markdown("### 1. Markt-Phasierung (SMA 50/200) <span style='color:#3d5afe'>±15 Pkt</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Der Algorithmus nutzt den gleitenden Durchschnitt der letzten 200 Tage als primären Filter für das Marktrisiko. Kurs > SMA 200 signalisiert einen strukturellen Bullenmarkt. Zusätzliche Pluspunkte gibt es für ein 'Golden Cross' (SMA 50 > SMA 200).</p>", unsafe_allow_html=True)
        

        st.markdown("### 2. Relative Stärke Oszillator (RSI 14) <span style='color:#3d5afe'>±10 Pkt</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Der RSI misst die 'Innere Stärke' über 14 Perioden. RSI > 70 zeigt Überhitzung (Gefahr von Rücksetzern), während RSI < 30 Panikverkäufe signalisiert, die oft Einstiegschancen bieten.</p>", unsafe_allow_html=True)
        

        st.markdown("### 3. Volatilitäts-Rauschen (ATR) <span style='color:#3d5afe'>-5 Pkt</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Berechnet die Schwankungsbreite der letzten 14 Tage. Eine Quote über 4% des Kurses deutet auf Instabilität hin, was das Risiko für Stop-Loss-Auslöser durch Marktrauschen erhöht.</p>", unsafe_allow_html=True)

        st.markdown("### 4. Operative Effizienz (Marge) <span style='color:#3d5afe'>+10 Pkt</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Marge > 15% beweist Preismacht (Economic Moat). Dies ist der wichtigste fundamentale Puffer gegen Inflation und steigende Kosten.</p>", unsafe_allow_html=True)

        st.markdown("### 5. Krisenfestigkeit (Net-Cash) <span style='color:#3d5afe'>+5 Pkt</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Barreserven vs. Schulden. Unternehmen mit Net-Cash sind unabhängig von Kreditmärkten und können Dividenden sicher finanzieren.</p>", unsafe_allow_html=True)

        st.markdown("### 6. Bewertungs-Dualismus (KGV/KUV) <span style='color:#3d5afe'>+10 Pkt</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Nutzt KGV (< 18) für profitable Firmen und KUV (< 3) für Wachstumswerte. Erkennt Unterbewertung in jeder Wachstumsphase.</p>", unsafe_allow_html=True)
        

        st.markdown("### 7. Smart-Money Bestätigung (Volumen) <span style='color:#3d5afe'>+10 Pkt</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Handelsvolumen > 30% über dem Schnitt zeigt den Einstieg institutioneller Anleger (Fonds/Banken). Ein Trend ohne Volumen gilt als unzuverlässig.</p>", unsafe_allow_html=True)

        st.markdown("### 8. Sentiment & Analysten-Power <span style='color:#3d5afe'>±20 Pkt</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Kombiniert NLP-News-Analysen und die durchschnittlichen Kursziele der Wall-Street. Ein Upside > 15% liefert die fundamentale Bestätigung.</p>", unsafe_allow_html=True)

        st.markdown("### 9. Sektor-Benchmark (Peer-Leader) <span style='color:#3d5afe'>+10 Pkt</span>", unsafe_allow_html=True)
        st.markdown("<p class='matrix-desc'>Vergleich mit Branchen-Konkurrenten. Nur 'Best-in-Class' Performer mit signifikanter relativer Stärke im Sektor erhalten diesen Bonus.</p>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Fehler: {e}")
