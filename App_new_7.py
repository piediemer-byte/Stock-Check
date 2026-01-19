import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# --- 1. UI SETUP & CONFIG ---
st.set_page_config(page_title="KI-Analyse Intelligence Ultimate", layout="wide", page_icon="📈")

st.markdown("""
<style>
/* V1 ORIGINAL STYLES (Wiederhergestellt) */
.status-card { background: #0d1117; padding: 12px; border-radius: 10px; border-left: 5px solid #3d5afe; margin-bottom: 15px; font-size: 0.9em; white-space: pre-wrap; }
.high-conviction { background: linear-gradient(90deg, #ffd700, #bf953f); color: #000; padding: 15px; border-radius: 10px; font-weight: bold; text-align: center; margin-bottom: 20px; border: 2px solid #fff; box-shadow: 0 0 15px rgba(253, 185, 49, 0.4); }
.calc-box { background: #161b22; padding: 15px; border-radius: 12px; border: 1px solid #30363d; margin-bottom: 15px; }
.reversal-box { background: #1a1a1a; padding: 10px; border-radius: 8px; border: 1px dashed #ff4b4b; margin-top: 10px; text-align: center; height: 100%; display: flex; flex-direction: column; justify-content: center; }
.explain-text { font-size: 0.85em; color: #b0bec5; line-height: 1.5; text-align: justify; }
.explain-text ul { padding-left: 20px; margin-top: 5px; margin-bottom: 5px; }
.factor-title { font-weight: bold; font-size: 1.05em; color: #ffffff; margin-top: 15px; margin-bottom: 8px; border-bottom: 1px solid #30363d; padding-bottom: 4px; }
.budget-ok { color: #00b894; font-weight: bold; }
.budget-err { color: #ff7675; font-weight: bold; }
.slider-label { font-size: 0.8em; color: #fff; margin-bottom: -10px; }
</style>
""", unsafe_allow_html=True)

# --- 2. SESSION STATE (GEWICHTUNG) ---
defaults = {
    'w_t': 15, 'w_r': 10, 'w_v': 5, 'w_m': 10, 'w_c': 5,
    'w_val': 10, 'w_vol': 10, 'w_np': 5, 'w_sec': 10, 'w_ma': 5, 'w_p': 5, 'w_nn': 7
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

weights = {
    'trend': st.session_state.w_t, 'rsi': st.session_state.w_r, 'vola': st.session_state.w_v,
    'margin': st.session_state.w_m, 'cash': st.session_state.w_c, 'value': st.session_state.w_val,
    'peg': st.session_state.w_p, 'volume': st.session_state.w_vol, 'sector': st.session_state.w_sec,
    'macd': st.session_state.w_ma, 'news_pos': st.session_state.w_np, 'news_neg': st.session_state.w_nn
}

current_budget = sum([v for k,v in weights.items() if k != 'news_neg'])
MAX_BUDGET = 100
valid_config = current_budget <= MAX_BUDGET

# --- 3. HELFER-FUNKTIONEN (LIVE DATEN) ---

def get_eur_usd_rate():
    # Live Abruf
    try:
        hist = yf.Ticker("EURUSD=X").history(period="1d")
        if not hist.empty: return 1 / float(hist['Close'].iloc[-1])
        return 0.92 
    except: return 0.92

def get_ticker_from_any(query):
    try:
        search = yf.Search(query, max_results=1)
        return search.quotes[0]['symbol'] if search.quotes else query.upper()
    except: return query.upper()

@st.cache_data(ttl=300) 
def get_alternative_news(ticker):
    headers = {"User-Agent": "Mozilla/5.0"}
    news_items = []
    try:
        url_yahoo = f"https://finance.yahoo.com/rss/headline?s={ticker}"
        response = requests.get(url_yahoo, headers=headers, timeout=3)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for item in root.findall('./channel/item')[:5]:
                title = item.find('title').text
                if title: news_items.append({'title': title, 'providerPublishTime': datetime.now().timestamp()})
    except: pass
    
    if len(news_items) < 2:
        try:
            url_google = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
            response = requests.get(url_google, headers=headers, timeout=3)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                for item in root.findall('./channel/item')[:5]:
                    title = item.find('title').text
                    if title: news_items.append({'title': title, 'providerPublishTime': datetime.now().timestamp()})
        except: pass
    return news_items

def analyze_news_sentiment(news_list, w_pos, w_neg):
    if not news_list: return 0, 0
    score = 0
    pos_w_list = ['upgraded', 'buy', 'growth', 'beats', 'profit', 'bull', 'surge', 'soar', 'strong', 'record', 'partnership']
    neg_w_list = ['risk', 'sell', 'loss', 'misses', 'bear', 'warnung', 'drop', 'fall', 'plunge', 'downgrade', 'weak', 'lawsuit']
    
    count = 0
    for n in news_list[:10]:
        title = n.get('title', '').lower()
        if any(w in title for w in pos_w_list): score += w_pos
        if any(w in title for w in neg_w_list): score -= w_neg
        count += 1
    return round(score, 1), count

# --- 4. KI-ENGINE (Logik bleibt erhalten) ---
def get_ki_verdict(ticker_obj, info_dict, hist_df, news_list, w):
    try:
        if len(hist_df) < 50: return "➡️ Neutral", "Zu wenig Daten", 0, 0, 50, {}, {}
        
        details = {}
        radar_scores = {} 
        curr_p = float(hist_df['Close'].iloc[-1])
        score = 50 
        reasons = []
        
        # 1. Trend
        s200 = hist_df['Close'].rolling(200).mean().iloc[-1]
        s50 = hist_df['Close'].rolling(50).mean().iloc[-1]
        details['sma200'] = s200
        details['sma50'] = s50
        details['curr_p'] = curr_p
        
        if not pd.isna(s50) and not pd.isna(s200):
            if curr_p > s50 > s200: score += w['trend']; reasons.append(f"🧭 Trend: Stark Bullish (über SMA 50/200) [+{w['trend']}]"); radar_scores['Trend'] = 1.0
            elif curr_p < s200: score -= w['trend']; reasons.append(f"🧭 Trend: Bearish (unter SMA 200) [-{w['trend']}]"); radar_scores['Trend'] = 0.0
            else: reasons.append("🧭 Trend: Neutral (Konsolidierung)"); radar_scores['Trend'] = 0.5
        else: reasons.append(f"🧭 Trend: Daten unvollständig"); radar_scores['Trend'] = 0.5

        # 2. RSI
        delta = hist_df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1]))
        details['rsi'] = rsi
        
        if rsi > 70: score -= w['rsi']; reasons.append(f"⚡ RSI: Überhitzt ({rsi:.1f}) [-{w['rsi']}]"); radar_scores['RSI'] = 0.2
        elif rsi < 30: score += w['rsi']; reasons.append(f"⚡ RSI: Überverkauft ({rsi:.1f}) [+{w['rsi']}]"); radar_scores['RSI'] = 1.0
        else: reasons.append(f"⚡ RSI: Neutral ({rsi:.1f})"); radar_scores['RSI'] = 0.5

        # 3. Vola
        atr = (hist_df['High']-hist_df['Low']).rolling(14).mean().iloc[-1]
        vola_ratio = (atr / curr_p) * 100
        details['atr_pct'] = vola_ratio
        if vola_ratio > 4: score -= w['vola']; reasons.append(f"🎢 Vola: Hoch ({vola_ratio:.1f}%) [-{w['vola']}]"); radar_scores['Stabilität'] = 0.2
        else: reasons.append(f"🎢 Vola: Angemessen ({vola_ratio:.1f}%)"); radar_scores['Stabilität'] = 1.0

        # 4. Fundamental
        marge = info_dict.get('operatingMargins', 0)
        details['margin'] = marge
        if marge > 0.15: score += w['margin']; reasons.append(f"💎 Marge: Stark ({marge*100:.1f}%) [+{w['margin']}]"); radar_scores['Marge'] = 1.0
        else: reasons.append(f"💎 Marge: Normal (<15%)"); radar_scores['Marge'] = 0.4
        
        cash = info_dict.get('totalCash', 0) or 0
        debt = info_dict.get('totalDebt', 0) or 0
        if cash > debt: score += w['cash']; reasons.append(f"🏦 Bilanz: Net-Cash vorhanden [+{w['cash']}]"); radar_scores['Bilanz'] = 1.0
        else: reasons.append(f"🏦 Bilanz: Net-Debt (Schulden > Cash)"); radar_scores['Bilanz'] = 0.4
        
        kgv = info_dict.get('forwardPE', info_dict.get('trailingPE'))
        details['kgv'] = kgv
        if kgv and 0 < kgv < 18: score += w['value']; reasons.append(f"🏷️ Bewertung: KGV attraktiv ({kgv:.1f}) [+{w['value']}]"); radar_scores['Value'] = 1.0
        else: reasons.append(f"🏷️ Bewertung: Neutral/Teuer"); radar_scores['Value'] = 0.4
        
        peg = info_dict.get('pegRatio')
        if peg and 0.5 < peg < 1.5: score += w['peg']; reasons.append(f"⚖️ PEG: Wachstum/Preis optimal ({peg}) [+{w['peg']}]"); radar_scores['Growth'] = 1.0
        else: reasons.append(f"⚖️ PEG: Neutral/Teuer"); radar_scores['Growth'] = 0.5

        # 5. Volumen & Sektor
        curr_vol = hist_df['Volume'].iloc[-1]
        avg_vol = hist_df['Volume'].tail(20).mean()
        if curr_vol > avg_vol * 1.3: score += w['volume']; reasons.append(f"📶 Volumen: Hohes Interesse [+{w['volume']}]"); radar_scores['Momentum'] = 1.0
        else: reasons.append(f"📶 Volumen: Normal"); radar_scores['Momentum'] = 0.5
        
        start_p = float(hist_df['Close'].iloc[0])
        sector = info_dict.get('sector', 'N/A')
        if (curr_p/start_p)-1 > 0.2: score += w['sector']; reasons.append(f"🏅 Sektor: Top-Performer ({sector}) [+{w['sector']}]"); radar_scores['Rel. Stärke'] = 1.0
        else: reasons.append(f"🏅 Sektor: Normal/Underperf. ({sector})"); radar_scores['Rel. Stärke'] = 0.4

        # 6. MACD & News
        exp1 = hist_df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = hist_df['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        sig = macd.ewm(span=9, adjust=False).mean()
        if macd.iloc[-1] > sig.iloc[-1]: score += w['macd']; reasons.append(f"🌊 MACD: Bullishes Momentum [+{w['macd']}]"); radar_scores['MACD'] = 1.0
        else: reasons.append(f"🌊 MACD: Neutral/Bearish"); radar_scores['MACD'] = 0.4

        n_score, n_count = analyze_news_sentiment(news_list, w['news_pos'], w['news_neg'])
        score += n_score
        reasons.append(f"📰 News Feed: Score {n_score} (aus {n_count} Quellen)")
        
        score = min(100, max(0, score))
        
        if score >= 95: verdict = "🌟 STAR AKTIE" 
        elif score >= 80: verdict = "💎 STRONG BUY"
        elif score >= 60: verdict = "🚀 BUY"
        elif score >= 35: verdict = "➡️ HOLD"
        else: verdict = "🛑 SELL"
        
        return verdict, "\n".join(reasons), vola_ratio, s200, score, details, radar_scores

    except Exception as e:
        return "⚠️ Error", str(e), 0, 0, 50, {}, {}

# --- 5. PLOTTING ---
def plot_radar_chart(radar_scores, ticker_symbol):
    if not radar_scores: return None
    cats = list(radar_scores.keys())
    vals = list(radar_scores.values())
    vals += [vals[0]]; cats += [cats[0]]
    fig = go.Figure(go.Scatterpolar(r=vals, theta=cats, fill='toself', line_color='#3d5afe'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1], showticklabels=False)), 
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                      margin=dict(l=30,r=30,t=20,b=20), height=300, showlegend=False,
                      font=dict(color='white'))
    return fig

def plot_chart(hist, symbol, eur_rate):
    fig = go.Figure()
    hist_eur = hist * eur_rate
    fig.add_trace(go.Candlestick(x=hist.index, open=hist_eur['Open'], high=hist_eur['High'], low=hist_eur['Low'], close=hist_eur['Close'], name='Kurs'))
    sma20 = hist_eur['Close'].rolling(20).mean()
    std = hist_eur['Close'].rolling(20).std()
    fig.add_trace(go.Scatter(x=hist.index, y=sma20+2*std, line=dict(color='rgba(255,255,255,0.1)'), hoverinfo='skip', showlegend=False))
    fig.add_trace(go.Scatter(x=hist.index, y=sma20-2*std, line=dict(color='rgba(255,255,255,0.1)'), fill='tonexty', fillcolor='rgba(255,255,255,0.05)', name='Bollinger', hoverinfo='skip'))
    fig.update_layout(title=f"Chart: {symbol}", yaxis_title='Preis (€)', xaxis_rangeslider_visible=False, template="plotly_dark", height=500, paper_bgcolor='rgba(0,0,0,0)')
    return fig

# --- 6. MAIN APP ---
st.title("📈 KI-Analyse Intelligence Ultimate")
eur_rate = get_eur_usd_rate()

with st.sidebar:
    search_query = st.text_input("Ticker Symbol:", value="NVDA")
    ticker_symbol = get_ticker_from_any(search_query)
    st.caption(f"Aktueller EUR/USD: {eur_rate:.4f}")
    if st.button("🔄 Refresh Data"):
        st.rerun()

# LIVE DATA FETCHING
try:
    ticker = yf.Ticker(ticker_symbol)
    with st.spinner(f"Lade Live-Daten für {ticker_symbol}..."):
        current_info = ticker.info 
        hist_1y = ticker.history(period="1y") 
        yf_news = ticker.news if ticker.news else []
        alt_news = get_alternative_news(ticker.ticker)
        current_news = yf_news + alt_news
except:
    current_info = {}
    hist_1y = pd.DataFrame()
    current_news = []

# TABS
tab_main, tab_compare, tab_calc, tab_chart, tab_fund, tab_scanner, tab_desc = st.tabs([
    "🚀 Dashboard", "🆚 Peer-Vergleich", "🧮 Berechnung", "📊 Chart", "🏢 Basisdaten", "🌟 Scanner", "⚙️ Deep Dive & Setup"
])

if not valid_config:
    st.error(f"⚠️ **Budget überschritten!** Du hast {current_budget}/100 Punkte vergeben. Bitte korrigiere dies im Tab 'Deep Dive'.")

# ==============================================================================
# TAB 1: DASHBOARD (WIEDER ORIGINAL LAYOUT VOM ERSTEN CODE)
# ==============================================================================
with tab_main:
    if not hist_1y.empty and valid_config:
        verdict, reasons, vola, sma200, ki_score, details, radar = get_ki_verdict(ticker, current_info, hist_1y, current_news, weights)
        curr_price = hist_1y['Close'].iloc[-1]
        curr_eur = curr_price * eur_rate
        prev_close = hist_1y['Close'].iloc[-2]
        change_pct = ((curr_price / prev_close) - 1) * 100
        
        # Original Dashboard Layout (Text & Boxen)
        # Wir fügen das Radar Chart in eine linke Spalte ein, aber lassen den Rest im Original V1 Look
        col_dash_1, col_dash_2 = st.columns([1, 1.5])
        
        with col_dash_1:
            # Name & Radar
            st.subheader(f"{current_info.get('longName', ticker_symbol)}")
            st.plotly_chart(plot_radar_chart(radar, ticker_symbol), use_container_width=True)
            
            # Kennzahlen Grid
            st.markdown("---")
            k1, k2 = st.columns(2)
            k1.metric("Score", f"{ki_score} / 100")
            k2.metric("RSI", f"{details.get('rsi',0):.1f}")
        
        with col_dash_2:
            # Original V1 Header Section
            st.metric("Kurs (Live)", f"{curr_eur:.2f} € / {curr_price:.2f} $", f"{change_pct:.2f}%")
            st.caption("vs. Vortag")

            # High Conviction Badge Logic aus Code 1
            if ki_score >= 95: 
                st.markdown("<div class='high-conviction'>🌟 STAR AKTIE</div>", unsafe_allow_html=True)
            elif ki_score >= 80:
                st.markdown("<div class='high-conviction' style='background:linear-gradient(90deg, #00b894, #55efc4); color:black;'>💎 STRONG BUY</div>", unsafe_allow_html=True)
            
            st.info(f"KI-Urteil: {verdict} ({ki_score} Pkt)")

            # Status Card (Reasons)
            st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
            
            # Reversal & Analyst Boxen (Original Code 1 Style)
            cr1, cr2 = st.columns(2)
            with cr1:
                sma200_val = sma200 if not pd.isna(sma200) else 0
                st.markdown(f"<div class='reversal-box'>🚨 <b>Trend-Umkehr (SMA200)</b><br>{sma200_val * eur_rate:.2f} €</div>", unsafe_allow_html=True)
            
            with cr2:
                stock_currency = current_info.get('currency', 'USD')
                conversion_rate = eur_rate if stock_currency != 'EUR' else 1.0
                tgt = current_info.get('targetMeanPrice')
                if not tgt: tgt = current_info.get('targetMedianPrice')

                if tgt:
                    pot = ((tgt/curr_price)-1)*100
                    col = "#00b894" if pot > 0 else "#ff7675"
                    tgt_eur = tgt * conversion_rate
                    st.markdown(f"<div class='reversal-box'>🎯 <b>Analysten Ziel</b><br>{tgt_eur:.2f} € (<span style='color:{col}'>{pot:+.1f}%</span>)</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='reversal-box'>🎯 <b>Analysten Ziel</b><br>N/A</div>", unsafe_allow_html=True)

# TAB 2: PEER VERGLEICH
with tab_compare:
    st.header("🆚 Aktien-Duell")
    comp_input = st.text_input("Gegner-Ticker:", value="AMD")
    if st.button("Vergleich starten") and valid_config:
        comp_ticker = get_ticker_from_any(comp_input)
        t2 = yf.Ticker(comp_ticker)
        h2 = t2.history(period="1y")
        if not h2.empty:
            v1, _, _, _, s1, d1, r1 = get_ki_verdict(ticker, current_info, hist_1y, current_news, weights)
            v2, _, _, _, s2, d2, r2 = get_ki_verdict(t2, t2.info, h2, [], weights)
            
            cc1, cc2 = st.columns(2)
            with cc1:
                st.subheader(ticker_symbol)
                st.metric("Score", s1, delta=s1-s2)
                st.plotly_chart(plot_radar_chart(r1, ticker_symbol), use_container_width=True, key="r1")
            with cc2:
                st.subheader(comp_ticker)
                st.metric("Score", s2, delta=s2-s1)
                st.plotly_chart(plot_radar_chart(r2, comp_ticker), use_container_width=True, key="r2")
                
            df_c = pd.DataFrame({
                "Metrik": ["KGV", "Marge", "RSI", "Score"],
                ticker_symbol: [d1.get('kgv'), f"{d1.get('margin',0)*100:.1f}%", f"{d1.get('rsi',0):.0f}", s1],
                comp_ticker: [d2.get('kgv'), f"{d2.get('margin',0)*100:.1f}%", f"{d2.get('rsi',0):.0f}", s2]
            })
            st.dataframe(df_c, hide_index=True, use_container_width=True)

# TAB 3: BERECHNUNG
with tab_calc:
    if not hist_1y.empty:
        curr_p_eur = hist_1y['Close'].iloc[-1] * eur_rate
        
        st.header("🧮 Risiko- & Positions-Planer")
        st.markdown("<div class='calc-box'>", unsafe_allow_html=True)
        cc1, cc2 = st.columns(2)
        inv = cc1.number_input("Invest (€)", value=2500.0, step=100.0)
        risk_pct = cc1.slider("Stop Loss %", 1.0, 20.0, 5.0)
        target_pct = cc2.slider("Take Profit %", 1.0, 100.0, 15.0)
        
        pcs = int(inv // curr_p_eur)
        risk_eur = inv * (risk_pct/100)
        prof_eur = inv * (target_pct/100)
        crv = prof_eur / risk_eur if risk_eur > 0 else 0
        
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Menge", f"{pcs} Stk.")
        r2.metric("Stop Loss", f"{curr_p_eur*(1-risk_pct/100):.2f} €", f"-{risk_eur:.2f}€")
        r3.metric("Take Profit", f"{curr_p_eur*(1+target_pct/100):.2f} €", f"+{prof_eur:.2f}€")
        r4.metric("CRV", f"{crv:.2f}")
        st.markdown("</div>", unsafe_allow_html=True)

        st.write("---")
        st.subheader("💰 Dividenden-Rechner")
        
        d_rate = current_info.get('dividendRate')
        d_yield = current_info.get('dividendYield')
        
        if d_rate and hist_1y['Close'].iloc[-1] > 0: calc_yield = d_rate / hist_1y['Close'].iloc[-1]
        elif d_yield: calc_yield = d_yield
        else: calc_yield = 0
        
        if d_rate: calc_rate = d_rate
        elif d_yield: calc_rate = d_yield * hist_1y['Close'].iloc[-1]
        else: calc_rate = 0

        st.markdown("<div class='calc-box'>", unsafe_allow_html=True)
        cd1, cd2 = st.columns(2)
        with cd1: div_anzahl = st.number_input("Anzahl Aktien", value=pcs, step=1)
        with cd2: st.metric("Dividenden-Rendite", f"{calc_yield*100:.2f}%")

        if calc_rate > 0:
            div_ges_eur = div_anzahl * calc_rate * eur_rate
            c_res_d1, c_res_d2 = st.columns(2)
            c_res_d1.metric("Jährliche Ausschüttung (est.)", f"{div_ges_eur:.2f} €")
            c_res_d2.metric("Ø Monatlich", f"{div_ges_eur/12:.2f} €")
        else:
            st.info("Dieses Unternehmen schüttet aktuell keine Dividende aus.")
        st.markdown("</div>", unsafe_allow_html=True)

# TAB 4: CHART
with tab_chart:
    if not hist_1y.empty:
        st.plotly_chart(plot_chart(hist_1y, ticker_symbol, eur_rate), use_container_width=True)

# TAB 5: BASISDATEN
with tab_fund:
    st.header("🏢 Fundamentaldaten & Key Metrics")
    cf1, cf2 = st.columns(2)
    cf1.write(f"**KGV (Forward):** {current_info.get('forwardPE', 'N/A')}")
    cf1.write(f"**PEG Ratio:** {current_info.get('pegRatio', 'N/A')}")
    cf1.write(f"**KUV:** {current_info.get('priceToSalesTrailing12Months', 'N/A')}")
    cf1.write(f"**Marge:** {current_info.get('operatingMargins', 0)*100:.2f}%")
    
    cf2.write(f"**Sektor:** {current_info.get('sector', 'N/A')}")
    h52 = current_info.get('fiftyTwoWeekHigh')
    l52 = current_info.get('fiftyTwoWeekLow')
    val_h52 = f"{h52 * eur_rate:.2f} €" if h52 else "N/A"
    val_l52 = f"{l52 * eur_rate:.2f} €" if l52 else "N/A"
    
    s50_val = details.get('sma50', 0)
    s200_val = details.get('sma200', 0)
    cf2.write(f"**SMA 50:** {s50_val * eur_rate:.2f} €")
    cf2.write(f"**SMA 200:** {s200_val * eur_rate:.2f} €")

# TAB 6: SCANNER
with tab_scanner:
    st.header("🌟 Deep Market Scanner (Live)")
    st.caption("Scannt vollständige Listen. Da wir Live-Daten nutzen, kann dies einen Moment dauern.")
    
    tech_ai = ["NVDA", "MSFT", "AAPL", "GOOGL", "AMD", "TSM", "AVGO", "META", "PLTR", "SMCI", "ARM", "ORCL", "ADBE", "CRM", "AMZN", "NFLX"]
    space = ["RKLB", "SPCE", "ASTS", "LUNR", "SIDU", "VSAT", "GSAT"]
    crypto_mining = ["MARA", "RIOT", "CLSK", "MSTR", "COIN", "CORZ", "IREN", "HUT", "WULF", "BITF", "HIVE"]
    defense = ["LMT", "RTX", "NOC", "GD", "LHX", "AVAV", "KTOS", "RHM.DE", "HENS.DE", "BA", "AIR.PA"]
    
    full_scan_list = list(set(tech_ai + space + crypto_mining + defense))
    
    if st.button("🚀 VOLLSTÄNDIGEN SCAN STARTEN"):
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        for idx, s_sym in enumerate(full_scan_list):
            bar.progress((idx + 1) / len(full_scan_list))
            status.text(f"Analysiere {s_sym}...")
            
            try:
                s_obj = yf.Ticker(s_sym)
                s_hist = s_obj.history(period="6mo")
                if len(s_hist) > 50:
                    s_info = s_obj.info
                    _, _, _, _, s_score, _, _ = get_ki_verdict(s_obj, s_info, s_hist, [], weights)
                    
                    if s_score >= 90:
                        cat = "Other"
                        if s_sym in tech_ai: cat = "Tech/AI"
                        elif s_sym in space: cat = "Space"
                        elif s_sym in crypto_mining: cat = "Crypto"
                        elif s_sym in defense: cat = "Defense"
                        
                        results.append({
                            "Ticker": s_sym,
                            "Kategorie": cat,
                            "Preis (€)": round(s_hist['Close'].iloc[-1] * eur_rate, 2),
                            "Score": s_score
                        })
            except: continue
        
        bar.empty()
        status.empty()
        
        if results:
            df_res = pd.DataFrame(results).sort_values(by="Score", ascending=False)
            st.success(f"{len(results)} Top-Picks gefunden!")
            st.dataframe(df_res, use_container_width=True, hide_index=True)
        else:
            st.warning("Keine Aktien mit Score >= 90 gefunden.")

# TAB 7: SETUP & DEEP DIVE
with tab_desc:
    st.header("⚙️ Strategie-Matrix & Gewichtung")
    st.markdown("Passe hier die Regeln deiner Strategie an. Links findest du die **Erklärung**, rechts den **Einfluss (Punkte)**.")

    if valid_config:
        st.markdown(f"**Budget:** <span class='budget-ok'>{current_budget} / {MAX_BUDGET}</span>", unsafe_allow_html=True)
    else:
        st.markdown(f"**Budget:** <span class='budget-err'>{current_budget} / {MAX_BUDGET}</span> (Zu viel!)", unsafe_allow_html=True)
        st.error(f"Bitte reduziere die Punkte um {current_budget - MAX_BUDGET}.")

    def create_detailed_input(title, text_html, key, min_v, max_v):
        st.markdown(f"<div class='factor-title'>{title}</div>", unsafe_allow_html=True)
        c1, c2 = st.columns([3, 1])
        with c1: st.markdown(f"<div class='explain-text'>{text_html}</div>", unsafe_allow_html=True)
        with c2: 
            st.markdown(f"<div class='slider-label'>Punkte:</div>", unsafe_allow_html=True)
            st.slider("Pkt", min_v, max_v, key=key, label_visibility="collapsed")

    # --- 1. TREND ---
    create_detailed_input(
        "🧭 1. Markt-Phasierung (SMA 200)",
        """Die Position zum <b>SMA 200</b> (200-Tage-Linie) ist der wichtigste Indikator für die "Großwetterlage".
        <ul><li><b>Bullish:</b> Kurs darüber = Asset ist 'gesund'. Fonds nutzen dies als Kaufzone.</li>
        <li><b>Bearish:</b> Kurs darunter = Verkäufer dominieren. Hohes Risiko.</li></ul>""",
        "w_t", 0, 30
    )

    # --- 2. RSI ---
    create_detailed_input(
        "⚡ 2. Relative Stärke Index (RSI 14)",
        """Misst die Geschwindigkeit der Kursbewegung (0-100).
        <ul><li><b>Überkauft (>70):</b> Extreme Gier. Korrekturgefahr (Malus).</li>
        <li><b>Überverkauft (<30):</b> Panik. Oft guter antizyklischer Einstieg (Bonus).</li></ul>""",
        "w_r", 0, 20
    )

    # --- 3. VOLATILITÄT ---
    create_detailed_input(
        "🎢 3. Volatilität (Malus)",
        """Die ATR (Average True Range) misst das "Marktrauschen".
        <ul><li><b>Gefahr (>4%):</b> Bei hoher Vola wirst du oft unglücklich ausgestoppt.</li>
        <li>Dies ist ein <b>Malus-Faktor</b>: Je höher die Vola, desto mehr Punkte Abzug.</li></ul>""",
        "w_v", 0, 20
    )

    # --- 4. MARGE ---
    create_detailed_input(
        "💎 4. Operative Marge",
        """Beweist Preismacht. Kann das Unternehmen steigende Kosten weitergeben?
        <ul><li><b>Ziel:</b> >15% Marge zeigt ein starkes Geschäftsmodell (Moat).</li></ul>""",
        "w_m", 0, 20
    )

    # --- 5. CASH ---
    create_detailed_input(
        "🏦 5. Bilanz (Net-Cash)",
        """Hat das Unternehmen mehr Cash als Schulden?
        <ul><li><b>Vorteil:</b> Immun gegen hohe Zinsen und kann in Krisen Konkurrenten kaufen.</li></ul>""",
        "w_c", 0, 20
    )

    # --- 6. VALUE ---
    create_detailed_input(
        "🏷️ 6. Bewertung (KGV / KUV)",
        """Wachstum darf nicht um jeden Preis gekauft werden.
        <ul><li><b>KGV < 18:</b> Günstig für etablierte Firmen.</li>
        <li><b>KUV < 3:</b> Günstig für Wachstumsfirmen (noch ohne Gewinn).</li></ul>""",
        "w_val", 0, 20
    )
    
    # --- 7. VOLUMEN ---
    create_detailed_input(
        "📶 7. Volumen-Analyse",
        """ "Volume precedes price". Steigt der Kurs bei hohem Volumen (>130% Ø)?
        <ul><li><b>Signal:</b> Deutet auf "Groß-Käufe" durch Institutionen hin (Smart Money).</li></ul>""",
        "w_vol", 0, 20
    )

    # --- 8. NEWS ---
    create_detailed_input(
        "📰 8. News Feed (Positiv)",
        """KI-Scan der Schlagzeilen (letzte 24-72h) aus mehreren Quellen (Yahoo, Google News, Reuters, etc.).
        <ul><li>Gewichtet aktuelle News (Upgrades, Gewinne, Beats) stärker.</li></ul>""",
        "w_np", 0, 10
    )

    # --- 9. SEKTOR ---
    create_detailed_input(
        "🏅 9. Relative Stärke (Sektor)",
        """Wir suchen die "Alpha-Tiere".
        <ul><li><b>Outperformance:</b> Aktie muss im letzten Jahr >20% gestiegen sein. Wir kaufen Stärke, keine Verlierer.</li></ul>""",
        "w_sec", 0, 20
    )

    # --- 10. MACD ---
    create_detailed_input(
        "🌊 10. MACD Momentum",
        """Trend-Folge-Indikator.
        <ul><li><b>Crossover:</b> Bullishes Kreuzen der Signallinien deutet auf frisches Kauf-Momentum hin.</li></ul>""",
        "w_ma", 0, 20
    )

    # --- 11. PEG ---
    create_detailed_input(
        "⚖️ 11. PEG Ratio",
        """Königsklasse der Bewertung: KGV im Verhältnis zum Wachstum.
        <ul><li><b>0.5 - 1.5:</b> "Growth at a reasonable Price" (GARP). Du zahlst fair für das Wachstum.</li></ul>""",
        "w_p", 0, 20
    )
    
    st.divider()
    st.markdown("**Zusatz-Regel (Malus):**")
    st.slider("Abzug pro negativer News (zählt nicht ins Budget)", 0, 15, key="w_nn")
