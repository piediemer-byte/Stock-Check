import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timezone

# --- 1. UI SETUP & CONFIG ---
st.set_page_config(page_title="KI-Analyse Intelligence", layout="centered")

st.markdown("""
<style>
.status-card { background: #0d1117; padding: 12px; border-radius: 10px; border-left: 5px solid #3d5afe; margin-bottom: 15px; font-size: 0.9em; white-space: pre-wrap; }
.high-conviction { background: linear-gradient(90deg, #ffd700, #bf953f); color: #000; padding: 15px; border-radius: 10px; font-weight: bold; text-align: center; margin-bottom: 20px; border: 2px solid #fff; }
.calc-box { background: #161b22; padding: 15px; border-radius: 12px; border: 1px solid #30363d; }
.reversal-box { background: #1a1a1a; padding: 10px; border-radius: 8px; border: 1px dashed #ff4b4b; margin-top: 10px; text-align: center; height: 100%; }
.weight-badge { background: #3d5afe; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.75em; float: right; }
.explain-text { font-size: 0.9em; color: #b0bec5; line-height: 1.5; margin-bottom: 5px; }
.factor-title { font-weight: bold; font-size: 1.1em; color: #ffffff; margin-top: 12px; margin-bottom: 5px; border-bottom: 1px solid #30363d; padding-bottom: 4px; }
.budget-ok { color: #00b894; font-weight: bold; }
.budget-err { color: #ff7675; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 2. HELFER-FUNKTIONEN ---
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

def analyze_news_sentiment(news_list, w_pos, w_neg):
    if not news_list: return 0, 0
    score = 0
    now = datetime.now(timezone.utc)
    # Vollständige Wortlisten wiederhergestellt
    pos_w_list = ['upgraded', 'buy', 'growth', 'beats', 'profit', 'bull', 'stark', 'chance', 'hoch', 'surge', 'soar', 'jump']
    neg_w_list = ['risk', 'sell', 'loss', 'misses', 'bear', 'warnung', 'senkt', 'problem', 'tief', 'drop', 'fall', 'plunge']
    
    analyzed_count = 0
    for n in news_list[:5]:
        title = n.get('title', '').lower()
        pub_time = datetime.fromtimestamp(n.get('providerPublishTime', now.timestamp()), timezone.utc)
        hours_old = (now - pub_time).total_seconds() / 3600
        weight = 1.0 if hours_old < 24 else (0.5 if hours_old < 72 else 0.2)
        
        if any(w in title for w in pos_w_list): score += (w_pos * weight)
        if any(w in title for w in neg_w_list): score -= (w_neg * weight)
        analyzed_count += 1
    
    return round(score, 1), analyzed_count

# --- 3. 11-FAKTOR KI-ENGINE (VOLLSTÄNDIG) ---
def get_ki_verdict(ticker_obj, w):
    try:
        inf = ticker_obj.info
        hist = ticker_obj.history(period="1y")
        
        # Initialisierung
        details = {}
        
        if len(hist) < 200: 
            return "➡️ Neutral", "Zu wenig historische Daten.", 0, 0, 50, {}
        
        curr_p = float(hist['Close'].iloc[-1])
        score = 50 # Start-Score
        reasons = []
        
        # 1. Trend (SMA 50/200)
        s200 = hist['Close'].rolling(200).mean().iloc[-1]
        s50 = hist['Close'].rolling(50).mean().iloc[-1]
        details['sma200'] = s200
        details['sma50'] = s50
        details['curr_p'] = curr_p
        
        if curr_p > s50 > s200: 
            score += w['trend']
            reasons.append(f"📈 Trend: Stark Bullish (über SMA 50/200) [+{w['trend']}]")
        elif curr_p < s200: 
            score -= w['trend']
            reasons.append(f"📉 Trend: Bearish (unter SMA 200) [-{w['trend']}]")
        else:
            reasons.append(f"➡️ Trend: Neutral (Konsolidierung).")

        # 2. RSI (14)
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1]))
        details['rsi'] = rsi
        
        if rsi > 70: 
            score -= w['rsi']
            reasons.append(f"🔥 RSI: Überhitzt ({rsi:.1f}) [-{w['rsi']}]")
        elif rsi < 30: 
            score += w['rsi']
            reasons.append(f"🧊 RSI: Überverkauft ({rsi:.1f}) [+{w['rsi']}]")

        # 3. Volatilität (ATR)
        high_low = hist['High'] - hist['Low']
        atr = high_low.rolling(14).mean().iloc[-1]
        vola_ratio = (atr / curr_p) * 100
        details['atr_pct'] = vola_ratio
        
        if vola_ratio > 4: 
            score -= w['vola']
            reasons.append(f"⚠️ Vola: Hoch ({vola_ratio:.1f}%) [-{w['vola']}]")

        # 4. & 5. Bilanz & Liquidität
        marge = inf.get('operatingMargins', 0)
        details['margin'] = marge
        if marge > 0.15: 
            score += w['margin']
            reasons.append(f"💰 Bilanz: Hohe Marge ({marge*100:.1f}%) [+{w['margin']}]")
        
        cash = inf.get('totalCash', 0) or 0
        debt = inf.get('totalDebt', 0) or 0
        details['net_cash'] = cash > debt
        if cash > debt: 
            score += w['cash']
            reasons.append(f"🏦 Bilanz: Net-Cash vorhanden [+{w['cash']}]")

        # 6. Bewertung (KGV/KUV)
        kgv = inf.get('forwardPE', -1)
        kuv = inf.get('priceToSalesTrailing12Months', -1)
        details['kgv'] = kgv
        details['kuv'] = kuv
        
        if kgv and 0 < kgv < 18: 
            score += w['value']
            reasons.append(f"💎 Bewertung: KGV attraktiv ({kgv:.1f}) [+{w['value']}]")
        elif (not kgv or kgv <= 0) and (kuv and 0 < kuv < 3): 
            score += w['value']
            reasons.append(f"🚀 Bewertung: KUV attraktiv ({kuv:.1f}) [+{w['value']}]")
        
        # 7. Volumen
        vol_avg = hist['Volume'].tail(20).mean()
        curr_vol = hist['Volume'].iloc[-1]
        details['vol_spike'] = curr_vol > vol_avg * 1.3
        if details['vol_spike']: 
            score += w['volume']
            reasons.append(f"📊 Volumen: Hohes Interesse [+{w['volume']}]")
        
        # 8. News
        news_score, news_count = analyze_news_sentiment(ticker_obj.news, w['news_pos'], w['news_neg'])
        score += news_score
        details['news_score'] = news_score
        
        # 9. Sektor-Benchmark
        sector = inf.get('sector', 'N/A')
        details['sector'] = sector
        start_p = float(hist['Close'].iloc[0])
        ytd_perf = (curr_p / start_p) - 1
        if start_p > 0 and ytd_perf > 0.2: 
            score += w['sector']
            reasons.append(f"🏆 Sektor: Top-Performer in {sector} [+{w['sector']}]")

        # 10. MACD (Trend-Momentum)
        exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
        exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        is_bullish_macd = macd.iloc[-1] > signal.iloc[-1]
        details['macd_bull'] = is_bullish_macd
        
        if is_bullish_macd:
            score += w['macd']
            reasons.append(f"🌊 MACD: Bullishes Momentum (Crossover) [+{w['macd']}]")

        # 11. PEG Ratio
        peg = inf.get('pegRatio')
        details['peg'] = peg
        if peg is not None and 0.5 < peg < 1.5:
            score += w['peg']
            reasons.append(f"⚖️ PEG: Wachstum/Preis-Ratio optimal ({peg}) [+{w['peg']}]")

        # Score Capping
        score = min(100, max(0, score))

        if score >= 80: verdict = "💎 STRONG BUY"
        elif score >= 60: verdict = "🚀 BUY"
        elif score >= 35: verdict = "➡️ HOLD"
        else: verdict = "🛑 SELL"
        
        return verdict, "\n".join(reasons), vola_ratio, s200, score, details

    except Exception as e:
        return "⚠️ Error", str(e), 0, 0, 50, {}

# --- 4. CHARTING FUNKTION (VOLLSTÄNDIG) ---
def plot_chart(hist, ticker_symbol, details):
    fig = go.Figure()

    # Candlestick
    fig.add_trace(go.Candlestick(x=hist.index,
                    open=hist['Open'], high=hist['High'],
                    low=hist['Low'], close=hist['Close'],
                    name='Kurs'))

    # SMA Linien
    s50 = hist['Close'].rolling(window=50).mean()
    s200 = hist['Close'].rolling(window=200).mean()
    
    fig.add_trace(go.Scatter(x=hist.index, y=s50, line=dict(color='#ff9f43', width=1.5), name='SMA 50'))
    fig.add_trace(go.Scatter(x=hist.index, y=s200, line=dict(color='#2e86de', width=2), name='SMA 200 (Trend)'))

    fig.update_layout(
        title=f"Chart-Analyse: {ticker_symbol}",
        yaxis_title='Preis ($)',
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# --- 5. MAIN APP STRUKTUR & LOGIK ---
st.title("📈 KI-Analyse Tool (Custom)")
search_query = st.text_input("Suche (Ticker):", value="NVDA")
ticker_symbol = get_ticker_from_any(search_query)

# TABS DEFINIEREN (Wir füllen Tab 4 zuerst, um die Weights zu bekommen!)
tab_main, tab_chart, tab_fund, tab_desc = st.tabs(["🚀 Dashboard", "📊 Chart", "🏢 Fundamentals", "⚙️ Deep Dive & Setup"])

# ==============================================================================
# SCHRITT 1: TAB 4 - EINGABE & CONFIG (Zuerst ausführen für Weights)
# ==============================================================================
with tab_desc:
    st.header("⚙️ Strategie-Matrix & Gewichtung")
    st.markdown("Hier definierst du die Regeln. Passe die Slider an deine Strategie an. Änderungen wirken sich **sofort** auf das Dashboard aus.")
    
    MAX_BUDGET = 100
    budget_container = st.container()

    # Helper für sauberes Layout der Eingaben
    def create_factor_input(title, desc, key, min_v, max_v, default_v):
        st.markdown(f"<div class='factor-title'>{title}</div>", unsafe_allow_html=True)
        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown(f"<div class='explain-text'>{desc}</div>", unsafe_allow_html=True)
        with c2:
            return st.slider(f"Punkte", min_v, max_v, default_v, key=key, label_visibility="collapsed")

    # --- EINGABEN (SLIDER) ---
    st.subheader("1. Technische Analyse")
    w_trend = create_factor_input("1. Trend (SMA)", "Belohnt Kurse über dem 200-Tage-Durchschnitt (langfristiger Aufwärtstrend).", "w_t", 0, 30, 15)
    w_rsi = create_factor_input("2. RSI (Indikator)", "Abzug bei Überhitzung (>70), Bonus bei Panik (<30).", "w_r", 0, 20, 10)
    w_vola = create_factor_input("3. Volatilität (Malus)", "Punktabzug bei zu starken Schwankungen (>4% ATR).", "w_v", 0, 20, 5)
    w_macd = create_factor_input("10. MACD Momentum", "Bonus für frisches Kaufsignal (Bullish Crossover).", "w_ma", 0, 20, 5)

    st.subheader("2. Fundamentaldaten")
    w_margin = create_factor_input("4. Marge", "Bonus für Unternehmen mit hoher Gewinnmarge (>15%).", "w_m", 0, 20, 10)
    w_cash = create_factor_input("5. Bilanz (Net Cash)", "Bonus für mehr Bargeld als Schulden.", "w_c", 0, 20, 5)
    w_value = create_factor_input("6. Bewertung (KGV/KUV)", "Punkte für günstige Bewertung (KGV < 18 oder KUV < 3).", "w_val", 0, 20, 10)
    w_peg = create_factor_input("11. PEG Ratio", "Growth at a reasonable Price (PEG 0.5 - 1.5).", "w_p", 0, 20, 5)

    st.subheader("3. Markt & Sentiment")
    w_volume = create_factor_input("7. Volumen", "Bonus, wenn das aktuelle Volumen deutlich über dem Durchschnitt liegt.", "w_vol", 0, 20, 10)
    w_sector = create_factor_input("9. Sektor-Performance", "Bonus für Aktien, die den Markt schlagen (YTD > 20%).", "w_sec", 0, 20, 10)
    w_news_pos = create_factor_input("8. News (Positiv)", "Punkte pro positiver Schlagzeile (KI-Sentiment).", "w_np", 0, 10, 5)
    
    st.divider()
    st.caption("Malus-Faktor (zählt nicht ins Budget):")
    w_news_neg = st.slider("Abzug pro negativer News", 0, 15, 7)

    # --- BUDGET VALIDIERUNG ---
    current_sum = w_trend + w_rsi + w_vola + w_margin + w_cash + w_value + w_peg + w_volume + w_sector + w_macd + w_news_pos
    
    with budget_container:
        st.write("---")
        c_bud1, c_bud2 = st.columns([3, 1])
        pct = min(current_sum / MAX_BUDGET, 1.0)
        
        with c_bud1:
            if current_sum <= MAX_BUDGET:
                st.markdown(f"**Vergebenes Strategie-Budget:** <span class='budget-ok'>{current_sum} / {MAX_BUDGET}</span>", unsafe_allow_html=True)
                st.progress(pct, text="Gültige Konfiguration")
                valid_config = True
            else:
                st.markdown(f"**Vergebenes Strategie-Budget:** <span class='budget-err'>{current_sum} / {MAX_BUDGET}</span>", unsafe_allow_html=True)
                st.progress(1.0, text="Überschritten!")
                st.error(f"Du hast {current_sum - MAX_BUDGET} Punkte zu viel vergeben! Bitte reduzieren.")
                valid_config = False

    # Dictionary erstellen
    weights = {
        'trend': w_trend, 'rsi': w_rsi, 'vola': w_vola, 'margin': w_margin, 'cash': w_cash, 
        'value': w_value, 'peg': w_peg, 'volume': w_volume, 'sector': w_sector, 
        'macd': w_macd, 'news_pos': w_news_pos, 'news_neg': w_news_neg
    }

# ==============================================================================
# SCHRITT 2: ANALYSE & DASHBOARD (Nur wenn Config gültig)
# ==============================================================================
if valid_config:
    try:
        ticker = yf.Ticker(ticker_symbol)
        eur_rate = get_eur_usd_rate()
        
        # Volle KI-Analyse
        verdict, reasons, vola, sma200, ki_score, details = get_ki_verdict(ticker, weights)
        
        hist_1y = ticker.history(period="1y")
        
        if not hist_1y.empty:
            curr_price = hist_1y['Close'].iloc[-1]
            curr_eur = curr_price * eur_rate
            prev_close = hist_1y['Close'].iloc[-2]
            change_pct = ((curr_price / prev_close) - 1) * 100
            
            # --- TAB 1: DASHBOARD (Wieder vollständig hergestellt) ---
            with tab_main:
                # Header Area
                c_head1, c_head2 = st.columns([2, 1])
                with c_head1:
                    st.subheader(f"{ticker.info.get('longName', ticker_symbol)} ({ticker_symbol})")
                    if ki_score >= 85: 
                        st.markdown("<div class='high-conviction'>🌟 HIGH CONVICTION: Elite-Setup erkannt!</div>", unsafe_allow_html=True)
                    st.info(f"KI-Ergebnis: {verdict} (Score: {ki_score}/100)")
                with c_head2:
                    st.metric("Aktueller Kurs", f"{curr_eur:.2f} €", f"{change_pct:.2f}%")

                # Gründe anzeigen
                st.markdown(f"**Analyse-Details (nach deiner Gewichtung):**")
                st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
                
                # Reversal Box & Analyst Target (Wieder da!)
                col_rev1, col_rev2 = st.columns(2)
                with col_rev1:
                    st.markdown(f"<div class='reversal-box'>🚨 <b>Trend-Umkehr (SMA200)</b><br>{sma200 * eur_rate:.2f} €</div>", unsafe_allow_html=True)
                with col_rev2:
                    target = ticker.info.get('targetMeanPrice')
                    if target:
                        pot = ((target / curr_price) - 1) * 100
                        color = "#00b894" if pot > 0 else "#ff7675"
                        st.markdown(f"<div class='reversal-box'>🎯 <b>Analysten Ziel</b><br>{target:.2f} $ (<span style='color:{color}'>{pot:+.1f}%</span>)</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='reversal-box'>🎯 <b>Analysten Ziel</b><br>N/A</div>", unsafe_allow_html=True)

                st.write("---")
                # Risiko-Rechner
                st.subheader("🧮 Risiko-Rechner")
                with st.container():
                    st.markdown("<div class='calc-box'>", unsafe_allow_html=True)
                    c_calc1, c_calc2 = st.columns(2)
                    with c_calc1:
                        invest = st.number_input("Investment (€)", value=2500.0, step=100.0)
                        risk_pct = st.slider("Max Risiko (%)", 0.0, 20.0, 5.0, step=0.5)
                    with c_calc2:
                        tp_suggestion = risk_pct * 3
                        target_pct = st.slider("Ziel-Profit (%)", 0.0, 100.0, tp_suggestion, step=1.0)
                    
                    stücke = int(invest // curr_eur)
                    eff_inv = stücke * curr_eur
                    sl_price = curr_eur * (1 - (risk_pct / 100))
                    tp_price = curr_eur * (1 + (target_pct / 100))
                    risk_eur = (eff_inv * (risk_pct/100))
                    profit_eur = (eff_inv * (target_pct/100))
                    crv = profit_eur / risk_eur if risk_eur > 0 else 0
                    
                    c_res1, c_res2, c_res3 = st.columns(3)
                    c_res1.metric("Position", f"{stücke} Stk.", f"{eff_inv:.0f} €")
                    c_res2.metric("Stop Loss", f"{sl_price:.2f} €", f"-{risk_eur:.2f} €", delta_color="inverse")
                    c_res3.metric("Take Profit", f"{tp_price:.2f} €", f"+{profit_eur:.2f} €")
                    st.caption(f"Chance-Risiko-Verhältnis (CRV): **{crv:.2f}**")
                    st.markdown("</div>", unsafe_allow_html=True)

            # --- TAB 2: CHART (Wieder mit Details) ---
            with tab_chart:
                st.plotly_chart(plot_chart(hist_1y, ticker_symbol, details), use_container_width=True)

            # --- TAB 3: FUNDAMENTALS ---
            with tab_fund:
                inf = ticker.info
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    st.markdown("### 💰 Bewertung")
                    st.write(f"**KGV (Forward):** {inf.get('forwardPE', 'N/A')}")
                    st.write(f"**PEG Ratio:** {inf.get('pegRatio', 'N/A')}")
                    st.write(f"**Price/Sales:** {inf.get('priceToSalesTrailing12Months', 'N/A')}")
                    st.write(f"**Marktkap:** {inf.get('marketCap', 0) / 1e9:.2f} Mrd. $")
                with col_f2:
                    st.markdown("### 🏦 Bilanz & Dividende")
                    div_yield = inf.get('dividendYield', 0)
                    st.write(f"**Div-Rendite:** {div_yield * 100 if div_yield else 0:.2f}%")
                    st.write(f"**Gewinnmarge:** {inf.get('profitMargins', 0) * 100:.2f}%")
                    st.write(f"**Beta:** {inf.get('beta', 'N/A')}")
                    st.write(f"**52W Hoch:** {inf.get('fiftyTwoWeekHigh', 'N/A')} $")
        else:
            st.error("Keine Historie gefunden.")
            
    except Exception as e:
        st.error(f"Fehler bei der Analyse: {e}")

else:
    # Fallback wenn Config ungültig
    with tab_main:
        st.warning("⚠️ Bitte korrigiere deine Gewichtung im Tab 'Deep Dive & Setup' (Budget überschritten), um die Analyse zu sehen.")
