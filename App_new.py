import streamlit as st
import yfinance as yf
import pandas as pd
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
        
        # Zeit-Gewichtung: News innerhalb der letzten 24h zählen voll (1.0), danach sinkt der Einfluss
        hours_old = (now - pub_time).total_seconds() / 3600
        weight = 1.0 if hours_old < 24 else (0.5 if hours_old < 72 else 0.2)
        
        if any(w in title for w in pos_w): score += (5 * weight)
        if any(w in title for w in neg_w): score -= (7 * weight)
    return round(score, 1)

# --- 2. 6-FAKTOR KI-ENGINE (4-STUFEN) ---
def get_ki_verdict(ticker_obj):
    inf = ticker_obj.info
    hist = ticker_obj.history(period="1y")
    if len(hist) < 200: return "➡️ Neutral", "Zu wenig Daten."
    
    curr_p = float(hist['Close'].iloc[-1])
    score = 50
    reasons = []
    
    # 1. Trend (SMA)
    s50 = hist['Close'].rolling(50).mean().iloc[-1]
    s200 = hist['Close'].rolling(200).mean().iloc[-1]
    if curr_p > s50 > s200: score += 15; reasons.append("📈 Trend: Bullish (SMA 50 > 200).")
    elif curr_p < s200: score -= 15; reasons.append("📉 Trend: Bearish (unter SMA 200).")

    # 2. Bilanz
    marge = inf.get('operatingMargins', 0)
    cash = inf.get('totalCash', 0)
    debt = inf.get('totalDebt', 0)
    if marge > 0.15: score += 10; reasons.append(f"💰 Bilanz: Hohe Marge ({marge*100:.1f}%).")
    if cash > debt: score += 5; reasons.append("🏦 Bilanz: Net-Cash vorhanden.")

    # 3. KGV
    kgv = inf.get('forwardPE', 0)
    if 0 < kgv < 18: score += 10; reasons.append(f"💎 KGV: Günstig bewertet ({kgv:.1f}).")

    # 4. Volumen
    avg_vol = hist['Volume'].tail(20).mean()
    if hist['Volume'].iloc[-1] > avg_vol * 1.3: score += 10; reasons.append("📊 Volumen: Hohes Interesse.")

    # 5. News (Zeit-Gewichtet)
    news_val = analyze_news_sentiment(ticker_obj.news)
    score += news_val
    if news_val > 2: reasons.append(f"📰 News: Aktuell sehr positiv (+{news_val}).")
    elif news_val < -2: reasons.append(f"📰 News: Aktuell belastet ({news_val}).")

    # 6. Prognosen
    target = inf.get('targetMedianPrice', curr_p)
    upside = (target / curr_p - 1) * 100
    if upside > 15: score += 10; reasons.append(f"🎯 Prognose: +{upside:.1f}% Upside.")

    if score >= 80: verdict = "💎 STRONG BUY"
    elif score >= 60: verdict = "🚀 BUY"
    elif score >= 35: verdict = "➡️ HOLD"
    else: verdict = "🛑 SELL"
    
    return verdict, "\n".join(reasons)

# --- 3. UI SETUP ---
st.set_page_config(page_title="StockAI NewsWeight", layout="centered")
st.markdown("<style>.status-card { background: #0d1117; padding: 12px; border-radius: 10px; border-left: 5px solid #3d5afe; margin-bottom: 15px; font-size: 0.85em; white-space: pre-wrap; } .calc-box { background: #161b22; padding: 15px; border-radius: 12px; border: 1px solid #30363d; }</style>", unsafe_allow_html=True)

# --- 4. APP ---
st.title("🛡️ StockAI Intelligence")
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
        
        verdict, reasons = get_ki_verdict(ticker)
        st.subheader(f"KI: {verdict}", help="Die News-Analyse gewichtet Meldungen der letzten 24h nun dreimal stärker als ältere News.")
        st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
        
        # ORDER-PLANER
        st.subheader("🛡️ Order- & Profit-Planer")
        with st.container():
            st.markdown("<div class='calc-box'>", unsafe_allow_html=True)
            c_inv, c_fee = st.columns(2)
            invest = c_inv.number_input("Investment (€)", value=1000.0)
            fee = c_fee.number_input("Gebühr/Trade (€)", value=1.0)
            
            risk_pct = st.slider("Risiko (%)", 1.0, 20.0, 5.0)
            target_pct = st.slider("Ziel (%)", 1.0, 50.0, 15.0)
            
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
            
            if crv >= 2.0: st.success(f"✅ **Chance-Risiko-Verhältnis (CRV): {crv:.2f}**")
            elif crv >= 1.0: st.warning(f"⚖️ **Chance-Risiko-Verhältnis (CRV): {crv:.2f}**")
            else: st.error(f"⚠️ **Chance-Risiko-Verhältnis (CRV): {crv:.2f}**")
            st.markdown("</div>", unsafe_allow_html=True)

        # DEEP DIVE
        st.divider()
        st.subheader("🔍 Deep Dive: KI-Matrix Protokoll")
        st.markdown("""
        | Kategorie | Kriterium | News-Gewichtung (Neu) | max. Pkt |
        | :--- | :--- | :--- | :--- |
        | **Sentiment** | Schlagzeilen < 24h | 100% Einfluss | +10 |
        | **Sentiment** | Schlagzeilen < 72h | 50% Einfluss | +5 |
        | **Sentiment** | Schlagzeilen > 72h | 20% Einfluss | +2 |
        """)

except Exception as e:
    st.error(f"Fehler: {e}")
