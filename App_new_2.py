import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
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
    if not news_list: return 0, 0
    score = 0
    now = datetime.now(timezone.utc)
    pos_w = ['upgraded', 'buy', 'growth', 'beats', 'profit', 'bull', 'stark', 'chance', 'hoch', 'surge', 'soar', 'jump']
    neg_w = ['risk', 'sell', 'loss', 'misses', 'bear', 'warnung', 'senkt', 'problem', 'tief', 'drop', 'fall', 'plunge']
    
    analyzed_count = 0
    for n in news_list[:5]:
        title = n.get('title', '').lower()
        pub_time = datetime.fromtimestamp(n.get('providerPublishTime', now.timestamp()), timezone.utc)
        hours_old = (now - pub_time).total_seconds() / 3600
        weight = 1.0 if hours_old < 24 else (0.5 if hours_old < 72 else 0.2)
        
        if any(w in title for w in pos_w): score += (5 * weight)
        if any(w in title for w in neg_w): score -= (7 * weight)
        analyzed_count += 1
    
    return round(score, 1), analyzed_count

# --- 2. 11-FAKTOR KI-Analyse-ENGINE ---
def get_ki_verdict(ticker_obj):
    try:
        inf = ticker_obj.info
        hist = ticker_obj.history(period="1y")
        
        # Initialisierung
        details = {}
        
        if len(hist) < 200: 
            return "➡️ Neutral", "Zu wenig historische Daten.", 0, 0, 50, {}
        
        curr_p = float(hist['Close'].iloc[-1])
        score = 50
        reasons = []
        
        # 1. Trend (SMA 50/200)
        s200 = hist['Close'].rolling(200).mean().iloc[-1]
        s50 = hist['Close'].rolling(50).mean().iloc[-1]
        details['sma200'] = s200
        details['sma50'] = s50
        details['curr_p'] = curr_p
        
        if curr_p > s50 > s200: 
            score += 15
            reasons.append(f"📈 Trend: Stark Bullish (über SMA 50/200).")
        elif curr_p < s200: 
            score -= 15
            reasons.append(f"📉 Trend: Bearish (unter SMA 200).")
        else:
            reasons.append(f"➡️ Trend: Neutral (Konsolidierung).")

        # 2. RSI (14)
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1]))
        details['rsi'] = rsi
        
        if rsi > 70: score -= 10; reasons.append(f"🔥 RSI: Überhitzt ({rsi:.1f}).")
        elif rsi < 30: score += 10; reasons.append(f"🧊 RSI: Überverkauft ({rsi:.1f}).")

        # 3. Volatilität (ATR)
        high_low = hist['High'] - hist['Low']
        atr = high_low.rolling(14).mean().iloc[-1]
        vola_ratio = (atr / curr_p) * 100
        details['atr_pct'] = vola_ratio
        
        if vola_ratio > 4: score -= 5; reasons.append(f"⚠️ Vola: Hoch ({vola_ratio:.1f}%)")

        # 4. & 5. Bilanz & Liquidität
        marge = inf.get('operatingMargins', 0)
        details['margin'] = marge
        if marge > 0.15: score += 10; reasons.append(f"💰 Bilanz: Hohe Marge ({marge*100:.1f}%).")
        
        cash = inf.get('totalCash', 0) or 0
        debt = inf.get('totalDebt', 0) or 0
        details['net_cash'] = cash > debt
        if cash > debt: score += 5; reasons.append("🏦 Bilanz: Net-Cash vorhanden.")

        # 6. Bewertung (KGV/KUV)
        kgv = inf.get('forwardPE', -1)
        kuv = inf.get('priceToSalesTrailing12Months', -1)
        details['kgv'] = kgv
        details['kuv'] = kuv
        
        if kgv and 0 < kgv < 18: score += 10; reasons.append(f"💎 Bewertung: KGV attraktiv ({kgv:.1f}).")
        elif (not kgv or kgv <= 0) and (kuv and 0 < kuv < 3): score += 10; reasons.append(f"🚀 Bewertung: KUV attraktiv ({kuv:.1f}).")
        
        # 7. Volumen & 8. News
        vol_avg = hist['Volume'].tail(20).mean()
        curr_vol = hist['Volume'].iloc[-1]
        details['vol_spike'] = curr_vol > vol_avg * 1.3
        if details['vol_spike']: score += 10; reasons.append("📊 Volumen: Hohes Interesse.")
        
        news_score, news_count = analyze_news_sentiment(ticker_obj.news)
        score += news_score
        details['news_score'] = news_score
        
        # 9. Sektor-Benchmark
        sector = inf.get('sector', 'N/A')
        details['sector'] = sector
        start_p = float(hist['Close'].iloc[0])
        ytd_perf = (curr_p / start_p) - 1
        if start_p > 0 and ytd_perf > 0.2: score += 10; reasons.append(f"🏆 Sektor: Top-Performer in {sector}.")

        # 10. MACD (Trend-Momentum)
        exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
        exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        is_bullish_macd = macd.iloc[-1] > signal.iloc[-1]
        details['macd_bull'] = is_bullish_macd
        
        if is_bullish_macd:
            score += 5
            reasons.append("🌊 MACD: Bullishes Momentum (Crossover).")

        # 11. PEG Ratio
        peg = inf.get('pegRatio')
        details['peg'] = peg
        if peg is not None and 0.5 < peg < 1.5:
            score += 5
            reasons.append(f"⚖️ PEG: Wachstum/Preis-Ratio optimal ({peg}).")

        # Score Capping
        score = min(100, max(0, score))

        if score >= 80: verdict = "💎 STRONG BUY"
        elif score >= 60: verdict = "🚀 BUY"
        elif score >= 35: verdict = "➡️ HOLD"
        else: verdict = "🛑 SELL"
        
        return verdict, "\n".join(reasons), vola_ratio, s200, score, details

    except Exception as e:
        return "⚠️ Error", str(e), 0, 0, 50, {}

# --- 3. CHARTING FUNKTION ---
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

# --- 4. UI SETUP ---
st.set_page_config(page_title="KI-Analyse Intelligence", layout="centered")
st.markdown("""
<style>
.status-card { background: #0d1117; padding: 12px; border-radius: 10px; border-left: 5px solid #3d5afe; margin-bottom: 15px; font-size: 0.9em; white-space: pre-wrap; }
.high-conviction { background: linear-gradient(90deg, #ffd700, #bf953f); color: #000; padding: 15px; border-radius: 10px; font-weight: bold; text-align: center; margin-bottom: 20px; border: 2px solid #fff; }
.calc-box { background: #161b22; padding: 15px; border-radius: 12px; border: 1px solid #30363d; }
.reversal-box { background: #1a1a1a; padding: 10px; border-radius: 8px; border: 1px dashed #ff4b4b; margin-top: 10px; text-align: center; }
.weight-badge { background: #3d5afe; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.75em; float: right; }
.explain-text { font-size: 0.9em; color: #b0bec5; line-height: 1.6; margin-bottom: 15px; }
.factor-title { font-weight: bold; font-size: 1.05em; color: #ffffff; margin-top: 15px; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 5. APP ---
st.title("📈 KI-Analyse Intelligence v2.1")
search_query = st.text_input("Suche (Ticker):", value="NVDA")
ticker_symbol = get_ticker_from_any(search_query)
eur_usd_rate = get_eur_usd_rate()

# Zeit-Buttons (für Session State)
if 'days' not in st.session_state: st.session_state.days = 22

try:
    ticker = yf.Ticker(ticker_symbol)
    hist_1y = ticker.history(period="1y")
    
    if not hist_1y.empty:
        curr_price = hist_1y['Close'].iloc[-1]
        curr_eur = curr_price * eur_usd_rate
        prev_close = hist_1y['Close'].iloc[-2]
        change_pct = ((curr_price / prev_close) - 1) * 100
        
        # Header
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader(f"{ticker.info.get('longName', ticker_symbol)} ({ticker_symbol})")
            st.caption(f"Sektor: {ticker.info.get('sector', 'N/A')} | Industrie: {ticker.info.get('industry', 'N/A')}")
        with c2:
            st.metric("Aktueller Kurs", f"{curr_eur:.2f} €", f"{change_pct:.2f}%")
        
        # KI Analyse ausführen
        verdict, reasons, current_vola, reversal_p, main_score, details = get_ki_verdict(ticker)
        
        if main_score >= 85:
            st.markdown("<div class='high-conviction'>🌟 HIGH CONVICTION: Elite-Setup erkannt!</div>", unsafe_allow_html=True)
            
        st.info(f"KI-Verdikt: {verdict} (Score: {main_score}/100)")
        
        # TABS
        tab_main, tab_chart, tab_fund, tab_desc = st.tabs(["🚀 Dashboard", "📊 Chart", "🏢 Fundamentals", "📚 Erklärung (Deep Dive)"])

        # TAB 1: DASHBOARD
        with tab_main:
            st.markdown(f"**Analyse-Faktoren:**")
            st.markdown(f"<div class='status-card'>{reasons}</div>", unsafe_allow_html=True)
            
            col_rev1, col_rev2 = st.columns(2)
            with col_rev1:
                st.markdown(f"<div class='reversal-box'>🚨 <b>Trend-Umkehr (SMA200)</b><br>{reversal_p * eur_usd_rate:.2f} €</div>", unsafe_allow_html=True)
            with col_rev2:
                target = ticker.info.get('targetMeanPrice')
                if target:
                    pot = ((target / curr_price) - 1) * 100
                    color = "#00b894" if pot > 0 else "#ff7675"
                    st.markdown(f"<div class='reversal-box'>🎯 <b>Analysten Ziel</b><br>{target:.2f} $ (<span style='color:{color}'>{pot:+.1f}%</span>)</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='reversal-box'>🎯 <b>Analysten Ziel</b><br>N/A</div>", unsafe_allow_html=True)

            st.write("---")
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

        # TAB 2: CHART
        with tab_chart:
            st.plotly_chart(plot_chart(hist_1y, ticker_symbol, details), use_container_width=True)

        # TAB 3: FUNDAMENTALS
        with tab_fund:
            inf = ticker.info
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                st.markdown("### 💰 Bewertung")
                st.write(f"**KGV (Forward):** {inf.get('forwardPE', 'N/A')}")
                st.write(f"**PEG Ratio:** {inf.get('pegRatio', 'N/A')}")
                st.write(f"**Price/Sales:** {inf.get('priceToSalesTrailing12Months', 'N/A')}")
                st.write(f"**Marktkapitalisierung:** {inf.get('marketCap', 0) / 1e9:.2f} Mrd. $")
            with col_f2:
                st.markdown("### 🏦 Bilanz & Dividende")
                div_yield = inf.get('dividendYield', 0)
                st.write(f"**Dividenden-Rendite:** {div_yield * 100 if div_yield else 0:.2f}%")
                st.write(f"**Gewinnmarge:** {inf.get('profitMargins', 0) * 100:.2f}%")
                st.write(f"**Beta (Volatilität):** {inf.get('beta', 'N/A')}")
                st.write(f"**52-Wochen Hoch:** {inf.get('fiftyTwoWeekHigh', 'N/A')} $")

        # TAB 4: ERKLÄRUNG / DEEP DIVE (WIEDERHERGESTELLT & VERBESSERT)
        with tab_desc:
            st.header("🔍 Strategischer Deep Dive: Die 11-Faktor-Matrix")
            st.markdown("Hier wird detailliert erklärt, warum die KI zu ihrem Urteil kommt und was die Fachbegriffe für deine Strategie bedeuten.")
            
            # 1. TREND
            st.markdown(f"<div class='factor-title'>1. Markt-Phasierung (SMA 200/50) <span class='weight-badge'>±15 Punkte</span></div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class='explain-text'>
            Die Position des Kurses zum <b>SMA 200</b> (aktuell bei {details['sma200']:.2f} $) ist der wichtigste Indikator für den langfristigen Trend (die "Großwetterlage").
            <ul>
                <li><b>Bullish:</b> Liegt der Kurs darüber, gilt das Asset als 'gesund'. Große Fonds und Institutionen nutzen diese Linie oft als automatisierte Kaufzone.</li>
                <li><b>Bearish:</b> Darunter dominieren die Verkäufer. Investments sind hier statistisch riskanter.</li>
                <li><b>SMA 50:</b> Dient als kurzfristigerer Indikator. Ein Kurs über SMA 50 und SMA 200 signalisiert starkes Momentum.</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)

            # 2. RSI
            st.markdown(f"<div class='factor-title'>2. Relative Stärke Index (RSI 14) <span class='weight-badge'>±10 Punkte</span></div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class='explain-text'>
            Der RSI misst die Geschwindigkeit von Kursbewegungen. Dein aktueller Wert: <b>{details['rsi']:.1f}</b>.
            <ul>
                <li><b>Überkauft (>70):</b> Die Gier im Markt ist extrem hoch. Eine Korrektur ist statistisch wahrscheinlich, da Gewinnmitnahmen einsetzen könnten.</li>
                <li><b>Überverkauft (<30):</b> Extreme Panik herrscht vor. Oft ein guter antizyklischer Einstiegspunkt ("Buy the Fear").</li>
                <li><b>Neutral (30-70):</b> Der Markt ist in Balance.</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)

            # 3. VOLATILITÄT
            st.markdown(f"<div class='factor-title'>3. Volatilitäts-Profil (ATR) <span class='weight-badge'>-5 Punkte (Malus)</span></div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class='explain-text'>
            Die Average True Range (ATR) misst das "Marktrauschen". Dein aktueller Wert (ATR/Preis): <b>{details['atr_pct']:.2f}%</b>.
            <ul>
                <li>Ein Wert <b>über 4%</b> deutet auf extrem spekulatives Verhalten hin.</li>
                <li><b>Gefahr:</b> Bei hoher Volatilität wirst du oft unglücklich aus deinem Stop-Loss geworfen, bevor der Kurs dreht. Positionen sollten hier kleiner gewählt werden.</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)

            # 4. & 5. BILANZ
            st.markdown(f"<div class='factor-title'>4. & 5. Fundamentale Resilienz <span class='weight-badge'>+15 Punkte</span></div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class='explain-text'>
            Hier prüft die KI die "Burganlage" (Moat) des Unternehmens:
            <ul>
                <li><b>Operating Margin (>15%):</b> Beweist Preismacht. Das Unternehmen kann steigende Kosten an Kunden weitergeben. Aktuell: <b>{details['margin']*100:.1f}%</b>.</li>
                <li><b>Net-Cash:</b> Ein Unternehmen, das mehr Cash als Schulden hat, ist immun gegen steigende Zinsen und kann in Krisen Konkurrenten aufkaufen.</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)

            # 6. BEWERTUNG
            st.markdown(f"<div class='factor-title'>6. Value-Check (KGV / KUV) <span class='weight-badge'>+10 Punkte</span></div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class='explain-text'>
            Wachstum darf nicht um jeden Preis gekauft werden.
            <ul>
                <li><b>KGV (Kurs-Gewinn-Verhältnis):</b> Ein KGV < 18 gilt historisch als attraktiv für etablierte Firmen. (Aktuell: {details['kgv']})</li>
                <li><b>KUV (Kurs-Umsatz-Verhältnis):</b> Bei jungen Tech-Werten ohne Gewinn weicht die KI auf das KUV aus (< 3 ist gut), um "Hype-Blasen" zu erkennen.</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)

            # 7. VOLUMEN
            st.markdown(f"<div class='factor-title'>7. Volumen-Analyse <span class='weight-badge'>+10 Punkte</span></div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class='explain-text'>
            "Volume precedes price" (Volumen geht dem Preis voraus). 
            Steigt der Kurs bei einem Volumen, das deutlich über dem Schnitt liegt, deutet dies auf <b>Akkumulation durch institutionelle Anleger</b> hin. Es ist kein Zufall, sondern gezieltes "Groß-Kaufen".
            </div>
            """, unsafe_allow_html=True)

            # 8. NEWS
            st.markdown(f"<div class='factor-title'>8. Mediales Echo (Sentiment) <span class='weight-badge'>±20 Punkte</span></div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class='explain-text'>
            Die KI scannt Schlagzeilen. Wir nutzen eine Zeitgewichtung: News der letzten 24h zählen voll, ältere News weniger.
            Dies fängt plötzliche Gewinnwarnungen oder Upgrades von Analysten (Goldman Sachs, Morgan Stanley etc.) sofort ab. 
            (Aktueller Score: {details['news_score']})
            </div>
            """, unsafe_allow_html=True)

            # 9. SEKTOR
            st.markdown(f"<div class='factor-title'>9. Outperformance-Check <span class='weight-badge'>+10 Punkte</span></div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class='explain-text'>
            Wir suchen die "Alpha-Tiere". Ein Bonus wird nur vergeben, wenn die Aktie eine Performance von >20% im letzten Jahr zeigt. Wir wollen Marktführer kaufen, keine Nachzügler.
            </div>
            """, unsafe_allow_html=True)

            # 10. MACD
            st.markdown(f"<div class='factor-title'>10. MACD Trend-Konvergenz <span class='weight-badge'>+5 Punkte</span></div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class='explain-text'>
            Der <b>Moving Average Convergence Divergence</b> zeigt das Zusammenspiel zweier exponentieller Durchschnitte.
            Ein "Bullish Crossover" signalisiert, dass das Kaufinteresse gerade massiv zunimmt und ein neuer Aufwärtstrend geboren wird.
            </div>
            """, unsafe_allow_html=True)

            # 11. PEG
            st.markdown(f"<div class='factor-title'>11. PEG-Ratio (Growth Valuation) <span class='weight-badge'>+5 Punkte</span></div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class='explain-text'>
            Das <b>PEG-Ratio</b> ist die Königsklasse der Bewertung. Es setzt das KGV ins Verhältnis zum erwarteten Gewinnwachstum.
            <ul>
                <li><b>PEG = 1.0:</b> Die Aktie ist fair bewertet (Preis entspricht Wachstum).</li>
                <li><b>PEG < 1.0:</b> Die Aktie ist unterbewertet (Du zahlst wenig für viel Wachstum).</li>
                <li>Aktueller Wert: <b>{details['peg']}</b></li>
            </ul>
            </div>
            """, unsafe_allow_html=True)

    else:
        st.error("Keine Daten gefunden. Bitte prüfe das Ticker-Symbol.")

except Exception as e:
    st.error(f"Ein Fehler ist aufgetreten: {e}")
