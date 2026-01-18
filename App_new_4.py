import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# --- 1. UI SETUP & CONFIG ---
st.set_page_config(page_title="KI-Analyse Intelligence", layout="centered")

st.markdown("""
<style>
.status-card { background: #0d1117; padding: 12px; border-radius: 10px; border-left: 5px solid #3d5afe; margin-bottom: 15px; font-size: 0.9em; white-space: pre-wrap; }
.high-conviction { background: linear-gradient(90deg, #ffd700, #bf953f); color: #000; padding: 15px; border-radius: 10px; font-weight: bold; text-align: center; margin-bottom: 20px; border: 2px solid #fff; }
.calc-box { background: #161b22; padding: 15px; border-radius: 12px; border: 1px solid #30363d; }
.reversal-box { background: #1a1a1a; padding: 10px; border-radius: 8px; border: 1px dashed #ff4b4b; margin-top: 10px; text-align: center; height: 100%; }
.explain-text { font-size: 0.85em; color: #b0bec5; line-height: 1.5; text-align: justify; }
.explain-text ul { padding-left: 20px; margin-top: 5px; margin-bottom: 5px; }
.factor-title { font-weight: bold; font-size: 1.05em; color: #ffffff; margin-top: 15px; margin-bottom: 8px; border-bottom: 1px solid #30363d; padding-bottom: 4px; }
.budget-ok { color: #00b894; font-weight: bold; }
.budget-err { color: #ff7675; font-weight: bold; }
.slider-label { font-size: 0.8em; color: #fff; margin-bottom: -10px; }
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

# --- VERBESSERTE NEWS FUNKTION ---
def get_alternative_news(ticker):
    """Versucht News via Yahoo RSS (zuverlässiger) und dann Google RSS zu holen"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    news_items = []
    
    # 1. Versuch: Yahoo Finance RSS (Direkt für den Ticker)
    try:
        url_yahoo = f"https://finance.yahoo.com/rss/headline?s={ticker}"
        response = requests.get(url_yahoo, headers=headers, timeout=4)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for item in root.findall('./channel/item')[:5]:
                title = item.find('title').text if item.find('title') is not None else ""
                news_items.append({
                    'title': title, 
                    'providerPublishTime': datetime.now().timestamp()
                })
    except:
        pass

    # 2. Versuch: Google News RSS (Falls Yahoo leer ist oder als Ergänzung)
    if len(news_items) < 3:
        try:
            url_google = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
            response = requests.get(url_google, headers=headers, timeout=4)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                for item in root.findall('./channel/item')[:5]:
                    title = item.find('title').text if item.find('title') is not None else ""
                    # Duplikate vermeiden
                    if not any(n['title'] == title for n in news_items):
                        news_items.append({
                            'title': title, 
                            'providerPublishTime': datetime.now().timestamp()
                        })
        except:
            pass
            
    return news_items

def analyze_news_sentiment(news_list, w_pos, w_neg):
    if not news_list: return 0, 0
    score = 0
    now = datetime.now(timezone.utc)
    pos_w_list = ['upgraded', 'buy', 'growth', 'beats', 'profit', 'bull', 'stark', 'chance', 'hoch', 'surge', 'soar', 'jump', 'outperform', 'strong', 'gains']
    neg_w_list = ['risk', 'sell', 'loss', 'misses', 'bear', 'warnung', 'senkt', 'problem', 'tief', 'drop', 'fall', 'plunge', 'downgrade', 'weak', 'crashing']
    
    analyzed_count = 0
    for n in news_list[:10]:
        title = n.get('title', '').lower()
        pub_time = datetime.fromtimestamp(n.get('providerPublishTime', now.timestamp()), timezone.utc)
        hours_old = (now - pub_time).total_seconds() / 3600
        weight = 1.0 if hours_old < 24 else (0.5 if hours_old < 72 else 0.2)
        
        if any(w in title for w in pos_w_list): score += (w_pos * weight)
        if any(w in title for w in neg_w_list): score -= (w_neg * weight)
        analyzed_count += 1
    
    return round(score, 1), analyzed_count

# --- 3. 11-FAKTOR KI-ENGINE ---
def get_ki_verdict(ticker_obj, w):
    try:
        inf = ticker_obj.info
        hist = ticker_obj.history(period="1y")
        
        details = {}
        if len(hist) < 200: 
            return "➡️ Neutral", "Zu wenig historische Daten.", 0, 0, 50, {}
        
        curr_p = float(hist['Close'].iloc[-1])
        score = 50 
        reasons = []
        
        # 1. Trend
        s200 = hist['Close'].rolling(200).mean().iloc[-1]
        s50 = hist['Close'].rolling(50).mean().iloc[-1]
        details['sma200'] = s200
        details['sma50'] = s50
        details['curr_p'] = curr_p
        
        if curr_p > s50 > s200: 
            score += w['trend']; reasons.append(f"📈 Trend: Stark Bullish (über SMA 50/200) [+{w['trend']}]")
        elif curr_p < s200: 
            score -= w['trend']; reasons.append(f"📉 Trend: Bearish (unter SMA 200) [-{w['trend']}]")
        else:
            reasons.append(f"➡️ Trend: Neutral (Konsolidierung)")

        # 2. RSI
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1]))
        details['rsi'] = rsi
        
        if rsi > 70: score -= w['rsi']; reasons.append(f"🔥 RSI: Überhitzt ({rsi:.1f}) [-{w['rsi']}]")
        elif rsi < 30: score += w['rsi']; reasons.append(f"🧊 RSI: Überverkauft ({rsi:.1f}) [+{w['rsi']}]")
        else: reasons.append(f"🔹 RSI: Neutral ({rsi:.1f})")

        # 3. Volatilität
        high_low = hist['High'] - hist['Low']
        atr = high_low.rolling(14).mean().iloc[-1]
        vola_ratio = (atr / curr_p) * 100
        details['atr_pct'] = vola_ratio
        
        if vola_ratio > 4: score -= w['vola']; reasons.append(f"⚠️ Vola: Hoch ({vola_ratio:.1f}%) [-{w['vola']}]")
        else: reasons.append(f"🔹 Vola: Angemessen ({vola_ratio:.1f}%)")

        # 4. Marge
        marge = inf.get('operatingMargins', 0)
        details['margin'] = marge
        if marge > 0.15: score += w['margin']; reasons.append(f"💰 Marge: Stark ({marge*100:.1f}%) [+{w['margin']}]")
        else: reasons.append(f"🔹 Marge: Normal (<15%)")
        
        # 5. Cash
        cash = inf.get('totalCash', 0) or 0
        debt = inf.get('totalDebt', 0) or 0
        details['net_cash'] = cash > debt
        if cash > debt: score += w['cash']; reasons.append(f"🏦 Bilanz: Net-Cash vorhanden [+{w['cash']}]")
        else: reasons.append(f"🔹 Bilanz: Net-Debt (Schulden > Cash)")

        # 6. Bewertung
        kgv = inf.get('forwardPE', -1)
        kuv = inf.get('priceToSalesTrailing12Months', -1)
        details['kgv'] = kgv
        details['kuv'] = kuv
        
        if kgv and 0 < kgv < 18: score += w['value']; reasons.append(f"💎 Bewertung: KGV attraktiv ({kgv:.1f}) [+{w['value']}]")
        elif (not kgv or kgv <= 0) and (kuv and 0 < kuv < 3): score += w['value']; reasons.append(f"🚀 Bewertung: KUV attraktiv ({kuv:.1f}) [+{w['value']}]")
        else: reasons.append(f"🔹 Bewertung: Neutral/Teuer")
        
        # 7. Volumen
        vol_avg = hist['Volume'].tail(20).mean()
        curr_vol = hist['Volume'].iloc[-1]
        details['vol_spike'] = curr_vol > vol_avg * 1.3
        if details['vol_spike']: score += w['volume']; reasons.append(f"📊 Volumen: Hohes Interesse [+{w['volume']}]")
        else: reasons.append(f"🔹 Volumen: Normal")
        
        # 8. News (OPTIMIERT)
        yf_news = ticker_obj.news if ticker_obj.news else []
        alt_news = get_alternative_news(ticker_obj.ticker)
        combined_news = yf_news + alt_news
        
        news_score, news_count = analyze_news_sentiment(combined_news, w['news_pos'], w['news_neg'])
        score += news_score
        details['news_score'] = news_score
        
        reasons.append(f"📰 News Feed: Score {news_score} ({news_count} Artikel)")
        
        # 9. Sektor
        sector = inf.get('sector', 'N/A')
        details['sector'] = sector
        start_p = float(hist['Close'].iloc[0])
        ytd_perf = (curr_p / start_p) - 1
        if start_p > 0 and ytd_perf > 0.2: score += w['sector']; reasons.append(f"🏆 Sektor: Top-Performer ({sector}) [+{w['sector']}]")
        else: reasons.append(f"🔹 Sektor: Normal/Underperf. ({sector})")

        # 10. MACD
        exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
        exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        is_bullish_macd = macd.iloc[-1] > signal.iloc[-1]
        details['macd_bull'] = is_bullish_macd
        
        if is_bullish_macd: score += w['macd']; reasons.append(f"🌊 MACD: Bullishes Momentum [+{w['macd']}]")
        else: reasons.append(f"🔹 MACD: Neutral/Bearish")

        # 11. PEG
        peg = inf.get('pegRatio')
        details['peg'] = peg
        if peg is not None and 0.5 < peg < 1.5: score += w['peg']; reasons.append(f"⚖️ PEG: Wachstum/Preis optimal ({peg}) [+{w['peg']}]")
        else: reasons.append(f"🔹 PEG: Neutral/Teuer ({peg if peg else 'N/A'})")

        # Capping
        score = min(100, max(0, score))

        if score >= 80: verdict = "💎 STRONG BUY"
        elif score >= 60: verdict = "🚀 BUY"
        elif score >= 35: verdict = "➡️ HOLD"
        else: verdict = "🛑 SELL"
        
        return verdict, "\n".join(reasons), vola_ratio, s200, score, details

    except Exception as e:
        return "⚠️ Error", str(e), 0, 0, 50, {}

# --- 4. CHART FUNKTION ---
def plot_chart(hist, ticker_symbol, details):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name='Kurs'))
    s50 = hist['Close'].rolling(window=50).mean()
    s200 = hist['Close'].rolling(window=200).mean()
    fig.add_trace(go.Scatter(x=hist.index, y=s50, line=dict(color='#ff9f43', width=1.5), name='SMA 50'))
    fig.add_trace(go.Scatter(x=hist.index, y=s200, line=dict(color='#2e86de', width=2), name='SMA 200'))
    fig.update_layout(title=f"Chart-Analyse: {ticker_symbol}", yaxis_title='Preis ($)', xaxis_rangeslider_visible=False, template="plotly_dark", height=500, margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig

# --- 5. MAIN APP ---
st.title("📈 KI-Aktien-Analyse")
search_query = st.text_input("Suche (Ticker):", value="NVDA")
ticker_symbol = get_ticker_from_any(search_query)

# TABS (Tab 4 wird zuerst verarbeitet für Input)
tab_main, tab_calc, tab_chart, tab_fund, tab_desc = st.tabs(["🚀 Dashboard", "🧮 Berechnung", "📊 Chart", "🏢 Basisdaten", "⚙️ Deep Dive & Setup"])

# ==============================================================================
# TAB 4: SETUP & DETAILLIERTE ERKLÄRUNGEN
# ==============================================================================
with tab_desc:
    st.header("⚙️ Strategie-Matrix & Gewichtung")
    st.markdown("Passe hier die Regeln deiner Strategie an. Links findest du die **Erklärung**, rechts den **Einfluss (Punkte)**.")
    
    MAX_BUDGET = 100
    budget_container = st.container()

    # Layout Helper: Linke Spalte Text (60%), Rechte Spalte Slider (40%)
    def create_detailed_input(title, text_html, key, min_v, max_v, default_v):
        st.markdown(f"<div class='factor-title'>{title}</div>", unsafe_allow_html=True)
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"<div class='explain-text'>{text_html}</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='slider-label'>Punkte:</div>", unsafe_allow_html=True)
            return st.slider("Pkt", min_v, max_v, default_v, key=key, label_visibility="collapsed")

    # --- 1. TREND ---
    w_trend = create_detailed_input(
        "1. Markt-Phasierung (SMA 200)",
        """Die Position zum <b>SMA 200</b> (200-Tage-Linie) ist der wichtigste Indikator für die "Großwetterlage".
        <ul><li><b>Bullish:</b> Kurs darüber = Asset ist 'gesund'. Fonds nutzen dies als Kaufzone.</li>
        <li><b>Bearish:</b> Kurs darunter = Verkäufer dominieren. Hohes Risiko.</li></ul>""",
        "w_t", 0, 30, 15
    )

    # --- 2. RSI ---
    w_rsi = create_detailed_input(
        "2. Relative Stärke Index (RSI 14)",
        """Misst die Geschwindigkeit der Kursbewegung (0-100).
        <ul><li><b>Überkauft (>70):</b> Extreme Gier. Korrekturgefahr (Malus).</li>
        <li><b>Überverkauft (<30):</b> Panik. Oft guter antizyklischer Einstieg (Bonus).</li></ul>""",
        "w_r", 0, 20, 10
    )

    # --- 3. VOLATILITÄT ---
    w_vola = create_detailed_input(
        "3. Volatilität (Malus)",
        """Die ATR (Average True Range) misst das "Marktrauschen".
        <ul><li><b>Gefahr (>4%):</b> Bei hoher Vola wirst du oft unglücklich ausgestoppt.</li>
        <li>Dies ist ein <b>Malus-Faktor</b>: Je höher die Vola, desto mehr Punkte Abzug.</li></ul>""",
        "w_v", 0, 20, 5
    )

    # --- 4. MARGE ---
    w_margin = create_detailed_input(
        "4. Operative Marge",
        """Beweist Preismacht. Kann das Unternehmen steigende Kosten weitergeben?
        <ul><li><b>Ziel:</b> >15% Marge zeigt ein starkes Geschäftsmodell (Moat).</li></ul>""",
        "w_m", 0, 20, 10
    )

    # --- 5. CASH ---
    w_cash = create_detailed_input(
        "5. Bilanz (Net-Cash)",
        """Hat das Unternehmen mehr Cash als Schulden?
        <ul><li><b>Vorteil:</b> Immun gegen hohe Zinsen und kann in Krisen Konkurrenten kaufen.</li></ul>""",
        "w_c", 0, 20, 5
    )

    # --- 6. VALUE ---
    w_value = create_detailed_input(
        "6. Bewertung (KGV / KUV)",
        """Wachstum darf nicht um jeden Preis gekauft werden.
        <ul><li><b>KGV < 18:</b> Günstig für etablierte Firmen.</li>
        <li><b>KUV < 3:</b> Günstig für Wachstumsfirmen (noch ohne Gewinn).</li></ul>""",
        "w_val", 0, 20, 10
    )
    
    # --- 7. VOLUMEN ---
    w_volume = create_detailed_input(
        "7. Volumen-Analyse",
        """ "Volume precedes price". Steigt der Kurs bei hohem Volumen (>130% Ø)?
        <ul><li><b>Signal:</b> Deutet auf "Groß-Käufe" durch Institutionen hin (Smart Money).</li></ul>""",
        "w_vol", 0, 20, 10
    )

    # --- 8. NEWS ---
    w_news_pos = create_detailed_input(
        "8. News Feed (Positiv)",
        """KI-Scan der Schlagzeilen (letzte 24-72h) aus mehreren Quellen (Yahoo, Google News, Reuters, etc.).
        <ul><li>Gewichtet aktuelle News (Upgrades, Gewinne, Beats) stärker.</li></ul>""",
        "w_np", 0, 10, 5
    )

    # --- 9. SEKTOR ---
    w_sector = create_detailed_input(
        "9. Relative Stärke (Sektor)",
        """Wir suchen die "Alpha-Tiere".
        <ul><li><b>Outperformance:</b> Aktie muss im letzten Jahr >20% gestiegen sein. Wir kaufen Stärke, keine Verlierer.</li></ul>""",
        "w_sec", 0, 20, 10
    )

    # --- 10. MACD ---
    w_macd = create_detailed_input(
        "10. MACD Momentum",
        """Trend-Folge-Indikator.
        <ul><li><b>Crossover:</b> Bullishes Kreuzen der Signallinien deutet auf frisches Kauf-Momentum hin.</li></ul>""",
        "w_ma", 0, 20, 5
    )

    # --- 11. PEG ---
    w_peg = create_detailed_input(
        "11. PEG Ratio",
        """Königsklasse der Bewertung: KGV im Verhältnis zum Wachstum.
        <ul><li><b>0.5 - 1.5:</b> "Growth at a reasonable Price" (GARP). Du zahlst fair für das Wachstum.</li></ul>""",
        "w_p", 0, 20, 5
    )
    
    st.divider()
    st.markdown("**Zusatz-Regel (Malus):**")
    w_news_neg = st.slider("Abzug pro negativer News (zählt nicht ins Budget)", 0, 15, 7)

    # --- BUDGET CHECK ---
    current_sum = w_trend + w_rsi + w_vola + w_margin + w_cash + w_value + w_peg + w_volume + w_sector + w_macd + w_news_pos
    
    with budget_container:
        st.write("---")
        c_bud1, c_bud2 = st.columns([3, 1])
        pct = min(current_sum / MAX_BUDGET, 1.0)
        with c_bud1:
            if current_sum <= MAX_BUDGET:
                st.markdown(f"**Budget:** <span class='budget-ok'>{current_sum} / {MAX_BUDGET} Punkte</span> verwendet.", unsafe_allow_html=True)
                st.progress(pct, text="Gültig")
                valid_config = True
            else:
                st.markdown(f"**Budget:** <span class='budget-err'>{current_sum} / {MAX_BUDGET} Punkte</span> (Zu viel!)", unsafe_allow_html=True)
                st.progress(1.0, text="Ungültig")
                st.error(f"Bitte reduziere die Punkte um {current_sum - MAX_BUDGET}.")
                valid_config = False

    weights = {
        'trend': w_trend, 'rsi': w_rsi, 'vola': w_vola, 'margin': w_margin, 'cash': w_cash, 
        'value': w_value, 'peg': w_peg, 'volume': w_volume, 'sector': w_sector, 
        'macd': w_macd, 'news_pos': w_news_pos, 'news_neg': w_news_neg
    }

# ==============================================================================
# MAIN LOGIC (DASHBOARD ETC.)
# ==============================================================================
if valid_config:
    try:
        ticker = yf.Ticker(ticker_symbol)
        eur_rate = get_eur_usd_rate()
        
        # KI Analyse
        verdict, reasons, vola, sma200, ki_score, details = get_ki_verdict(ticker, weights)
        
        hist_1y = ticker.history(period="1y")
        
        if not hist_1y.empty:
            curr_price = hist_1y['Close'].iloc[-1]
            curr_eur = curr_price * eur_rate
            prev_close = hist_1y['Close'].iloc[-2]
            change_pct = ((curr_price / prev_close) - 1) * 100
            
            # --- TAB 1: DASHBOARD ---
            with tab_main:
                # Layout Änderung: Kurs oben, Urteil unten
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.subheader(f"{ticker.info.get('longName', ticker_symbol)}")
                with c2:
                    st.metric("Kurs", f"{curr_eur:.2f} € / {curr_price:.2f} $", f"{change_pct:.2f}%")
                    st.caption("vs. Vortag")

                # Schwellenwert auf 95
                if ki_score >= 95: 
                    st.markdown("<div class='high-conviction'>🌟 Star Aktie</div>", unsafe_allow_html=True)
                st.info(f"KI-Urteil: {verdict} ({ki_score} Pkt)")

                st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
                
                # Reversal & Target
                cr1, cr2 = st.columns(2)
                with cr1:
                    st.markdown(f"<div class='reversal-box'>🚨 <b>Trend-Umkehr (SMA200)</b><br>{sma200 * eur_rate:.2f} €</div>", unsafe_allow_html=True)
                with cr2:
                    tgt = ticker.info.get('targetMeanPrice')
                    if tgt:
                        pot = ((tgt/curr_price)-1)*100
                        col = "#00b894" if pot > 0 else "#ff7675"
                        # Währungsanpassung hier:
                        st.markdown(f"<div class='reversal-box'>🎯 <b>Analysten Ziel</b><br>{tgt * eur_rate:.2f} € (<span style='color:{col}'>{pot:+.1f}%</span>)</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='reversal-box'>🎯 <b>Analysten Ziel</b><br>N/A</div>", unsafe_allow_html=True)

            # --- TAB 2: BERECHNUNG (NEUER TAB) ---
            with tab_calc:
                st.header("🧮 Risiko- & Positions-Planer")
                st.markdown("<div class='calc-box'>", unsafe_allow_html=True)
                cc1, cc2 = st.columns(2)
                inv = cc1.number_input("Invest (€)", value=2500.0, step=100.0)
                risk_pct = cc1.slider("Stop Loss %", 1.0, 20.0, 5.0)
                target_pct = cc2.slider("Take Profit %", 1.0, 100.0, 15.0)
                
                pcs = int(inv // curr_eur)
                risk_eur = inv * (risk_pct/100)
                prof_eur = inv * (target_pct/100)
                
                # CRV
                crv = prof_eur / risk_eur if risk_eur > 0 else 0
                
                r1, r2, r3, r4 = st.columns(4)
                r1.metric("Menge", f"{pcs} Stk.")
                r2.metric("Stop Loss", f"{curr_eur*(1-risk_pct/100):.2f} €", f"-{risk_eur:.2f}€")
                r3.metric("Take Profit", f"{curr_eur*(1+target_pct/100):.2f} €", f"+{prof_eur:.2f}€")
                r4.metric("CRV", f"{crv:.2f}")
                
                st.markdown("</div>", unsafe_allow_html=True)

            # --- TAB 3: CHART ---
            with tab_chart:
                st.plotly_chart(plot_chart(hist_1y, ticker_symbol, details), use_container_width=True)

            # --- TAB 4: BASISDATEN ---
            with tab_fund:
                i = ticker.info
                cf1, cf2 = st.columns(2)
                cf1.write(f"**KGV:** {i.get('forwardPE', 'N/A')}")
                cf1.write(f"**PEG:** {i.get('pegRatio', 'N/A')}")
                cf1.write(f"**KUV:** {i.get('priceToSalesTrailing12Months', 'N/A')}")
                cf2.write(f"**Sektor:** {i.get('sector', 'N/A')}")
                cf2.write(f"**Dividende:** {i.get('dividendYield', 0)*100:.2f}%")
                
                h52 = i.get('fiftyTwoWeekHigh')
                l52 = i.get('fiftyTwoWeekLow')
                
                if h52: cf2.write(f"**52W Hoch:** {h52 * eur_rate:.2f} €")
                else: cf2.write("**52W Hoch:** N/A")
                
                if l52: cf2.write(f"**52W Tief:** {l52 * eur_rate:.2f} €")
                else: cf2.write("**52W Tief:** N/A")
                
                cf2.write(f"**SMA 50:** {details['sma50'] * eur_rate:.2f} €")
                cf2.write(f"**SMA 200:** {details['sma200'] * eur_rate:.2f} €")
        else:
            st.error("Keine Daten geladen.")
    except Exception as e:
        st.error(f"Fehler: {e}")
else:
    with tab_main:
        st.warning("⚠️ Bitte korrigiere die Gewichtung im Tab 'Deep Dive & Setup'.")
