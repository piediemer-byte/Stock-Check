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

# --- 2. 8-FAKTOR KI-Analyse-ENGINE ---
def get_ki_verdict(ticker_obj):
    inf = ticker_obj.info
    hist = ticker_obj.history(period="1y")
    if len(hist) < 200: return "➡️ Neutral", "Zu wenig Daten.", 0
    
    curr_p = float(hist['Close'].iloc[-1])
    score = 50
    reasons = []
    
    # 1. Trend (SMA)
    s50 = hist['Close'].rolling(50).mean().iloc[-1]
    s200 = hist['Close'].rolling(200).mean().iloc[-1]
    if curr_p > s50 > s200: score += 15; reasons.append("📈 Trend: Bullish (SMA 50 > 200).")
    elif curr_p < s200: score -= 15; reasons.append("📉 Trend: Bearish (unter SMA 200).")

    # 2. RSI (Überkauft/Überverkauft)
    delta = hist['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs.iloc[-1]))
    if rsi > 70: score -= 10; reasons.append(f"🔥 RSI: Überhitzt ({rsi:.1f}) - Rückschlagrisiko!")
    elif rsi < 30: score += 10; reasons.append(f"🧊 RSI: Überverkauft ({rsi:.1f}) - Chance!")

    # 3. Volatilität (ATR-Check)
    high_low = hist['High'] - hist['Low']
    atr = high_low.rolling(14).mean().iloc[-1]
    vola_ratio = (atr / curr_p) * 100
    if vola_ratio > 4: score -= 5; reasons.append(f"⚠️ Vola: Hoch ({vola_ratio:.1f}%) - Weiten Stop nutzen.")

    # 4. Bilanz
    marge = inf.get('operatingMargins', 0)
    cash = inf.get('totalCash', 0)
    debt = inf.get('totalDebt', 0)
    if marge > 0.15: score += 10; reasons.append(f"💰 Bilanz: Hohe Marge ({marge*100:.1f}%).")
    if cash > debt: score += 5; reasons.append("🏦 Bilanz: Net-Cash vorhanden.")

    # 5. Bewertung (KGV/KUV)
    kgv = inf.get('forwardPE', -1)
    kuv = inf.get('priceToSalesTrailing12Months', -1)
    if kgv > 0 and kgv < 18: score += 10; reasons.append(f"💎 Bewertung: Günstiges KGV ({kgv:.1f}).")
    elif kgv <= 0 and kuv > 0 and kuv < 3: score += 10; reasons.append(f"🚀 Bewertung: Wachstums-KUV attraktiv ({kuv:.1f}).")
    
    # 6. Volumen
    avg_vol = hist['Volume'].tail(20).mean()
    if hist['Volume'].iloc[-1] > avg_vol * 1.3: score += 10; reasons.append("📊 Volumen: Hohes Interesse.")

    # 7. News
    news_val = analyze_news_sentiment(ticker_obj.news)
    score += news_val
    if news_val > 2: reasons.append(f"📰 News: Aktuell positiv (+{news_val}).")

    # 8. Prognosen
    target = inf.get('targetMedianPrice', curr_p)
    upside = (target / curr_p - 1) * 100
    if upside > 15: score += 10; reasons.append(f"🎯 Prognose: +{upside:.1f}% Upside.")

    if score >= 80: verdict = "💎 STRONG BUY"
    elif score >= 60: verdict = "🚀 BUY"
    elif score >= 35: verdict = "➡️ HOLD"
    else: verdict = "🛑 SELL"
    return verdict, "\n".join(reasons), vola_ratio

# --- 3. UI SETUP ---
st.set_page_config(page_title="KI-Analyse Pro", layout="centered")
st.markdown("<style>.status-card { background: #0d1117; padding: 12px; border-radius: 10px; border-left: 5px solid #3d5afe; margin-bottom: 15px; font-size: 0.85em; white-space: pre-wrap; } .calc-box { background: #161b22; padding: 15px; border-radius: 12px; border: 1px solid #30363d; } .matrix-desc { font-size: 0.88em; color: #cfd8dc; line-height: 1.6; margin-bottom: 15px; }</style>", unsafe_allow_html=True)

# --- 4. APP ---
st.title("🛡️ KI-Analyse Intelligence")
search_query = st.text_input("Suche (Name, ISIN, Ticker):", value="Apple")
ticker_symbol = get_ticker_from_any(search_query)
eur_usd_rate = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

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
        
        st.caption(f"Asset: **{ticker.info.get('longName', ticker_symbol)}**")
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Kurs (€)", f"{curr_eur:.2f} €", f"{perf:.2f}%")
        col_m2.metric("Kurs ($)", f"{recent['Close'].iloc[-1]:.2f} $")
        
        verdict, reasons, current_vola = get_ki_verdict(ticker)
        st.subheader(f"KI-Analyse: {verdict}")
        st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
        
        st.subheader("🛡️ Order- & Profit-Planer")
        with st.container():
            st.markdown("<div class='calc-box'>", unsafe_allow_html=True)
            c_inv, c_fee = st.columns(2)
            invest = c_inv.number_input("Investment (€)", value=1000.0)
            fee = c_fee.number_input("Gebühr/Trade (€)", value=1.0)
            
            # Dynamische Risiko-Empfehlung basierend auf Volatilität
            rec_risk = max(5.0, current_vola * 1.5)
            risk_pct = st.slider("Risiko (%)", 1.0, 30.0, rec_risk)
            target_pct = st.slider("Ziel (%)", 1.0, 60.0, 15.0)
            
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
            if crv >= 2.0: st.success(f"✅ **CRV: {crv:.2f}**")
            elif crv >= 1.0: st.warning(f"⚖️ **CRV: {crv:.2f}**")
            else: st.error(f"⚠️ **CRV: {crv:.2f}**")
            st.markdown("</div>", unsafe_allow_html=True)

        st.divider()
        st.subheader("🔍 Deep Dive: KI-Analyse-Strategie Protokoll")
        
        st.markdown("### 1. Trend & Relative Stärke (RSI)")
        st.markdown("<p class='matrix-desc'><b>SMA 50/200:</b> Basis-Trendbestimmung.<br><b>RSI (Relative Strength Index):</b> Die KI-Analyse prüft, ob eine Aktie 'heißgelaufen' ist. Ein RSI > 70 führt zu Punktabzug (-10), da die Wahrscheinlichkeit für eine technische Korrektur steigt. Ein RSI < 30 signalisiert eine massive Überverkaufung und bietet Einstiegschancen (+10).</p>", unsafe_allow_html=True)
        

        st.markdown("### 2. Volatilitäts-Check (ATR)")
        st.markdown("<p class='matrix-desc'><b>Average True Range:</b> Die KI-Analyse misst die tägliche Schwankungsbreite. Bei hoher Volatilität (>4% des Kurses) wird der Score leicht gesenkt (-5), da das Risiko für Stop-Loss-Fischer steigt. Der Order-Planer passt daraufhin automatisch die Risiko-Empfehlung an.</p>", unsafe_allow_html=True)

        st.markdown("### 3. Bilanzqualität & Bewertung")
        st.markdown("<p class='matrix-desc'><b>Dual-Check:</b> Hohe Margen (>15%) und Net-Cash bringen Stabilität. Bei der Bewertung nutzt die KI-Analyse das KGV (<18) oder wechselt bei Verlusten zum KUV-Check (<3 für Growth), um faire Einstiegspreise zu finden.</p>", unsafe_allow_html=True)
        
        st.markdown("### 4. Dynamik & Erwartung")
        st.markdown("<p class='matrix-desc'><b>Volumen & Analysten:</b> Ein Volumen-Peak (>130%) bestätigt institutionelles Interesse. Das Analysten-Upside (>15%) dient als Bestätigung des langfristigen fairen Werts.</p>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Fehler: {e}")
