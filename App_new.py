import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# --- 1. RSI BERECHNUNG ---
def calculate_rsi(data, window=14):
    if len(data) < window: return pd.Series()
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 2. APP KONFIGURATION ---
st.set_page_config(page_title="Aktien-Check Pro", layout="wide")

# CSS für Black Design & Aktive Buttons
st.markdown("""
<style>
    .main { background-color: #0e1117; color: white; }
    div[data-testid="stMetric"] {
        background-color: #000000;
        border: 1px solid #333;
        padding: 15px;
        border-radius: 10px;
        color: white;
    }
    .news-box { background-color: #1e1e1e; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #bb86fc; }
    /* Styling für Buttons */
    .stButton > button {
        width: 100%;
        border-radius: 5px;
        background-color: #1e1e1e;
        color: white;
        border: 1px solid #444;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. SIDEBAR (MENÜ) ---
st.sidebar.title("📱 Menü")
symbol = st.sidebar.text_input("Aktie:", value="RIOT").strip().upper()
mode = st.sidebar.selectbox("Funktion:", ["Analyse", "Prognosen", "Positionsrechner"])

# Session State für Zeitraum initialisieren
if 'period' not in st.session_state:
    st.session_state.period = '1y'

# --- 4. DATEN-LOGIK ---
if symbol:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Währungsumrechnung (USD zu EUR)
        eur_usd_ticker = yf.Ticker("EURUSD=X")
        usd_to_eur_rate = 1 / eur_usd_ticker.info.get('regularMarketPrice', 1.09)

        if mode == "Analyse":
            st.title(f"{info.get('longName', symbol)}")
            
            # Zeit-Buttons direkt über dem Chart mit Hervorhebung
            cols = st.columns(5)
            periods = [("1T", "1d"), ("1W", "5d"), ("1M", "1mo"), ("6M", "6mo"), ("1J", "1y")]
            
            for i, (label, p) in enumerate(periods):
                # Wenn der Button dem aktiven Zeitraum entspricht, bekommt er ein spezielles Styling via Markdown/CSS Hack
                if st.session_state.period == p:
                    if cols[i].button(label, key=p, use_container_width=True, type="primary"):
                        st.session_state.period = p
                else:
                    if cols[i].button(label, key=p, use_container_width=True):
                        st.session_state.period = p
                        st.rerun()

            # Intervall-Logik
            interval = "1m" if st.session_state.period == "1d" else "1h" if st.session_state.period == "5d" else "1d"
            df = ticker.history(period=st.session_state.period, interval=interval)

            if not df.empty:
                price_usd = info.get('currentPrice') or df['Close'].iloc[-1]
                price_eur = price_usd * usd_to_eur_rate
                open_price = df['Open'].iloc[0]
                change_pct = ((price_usd - open_price) / open_price) * 100

                # RSI & Rating
                df['RSI'] = calculate_rsi(df)
                current_rsi = df['RSI'].iloc[-1] if not df['RSI'].dropna().empty else 50.0
                
                if current_rsi < 35: st.success(f"👍 KAUFEN (RSI: {current_rsi:.1f})")
                elif current_rsi > 65: st.error(f"👎 VERKAUFEN (RSI: {current_rsi:.1f})")
                else: st.warning(f"✋ HALTEN (RSI: {current_rsi:.1f})")

                # Metriken
                m1, m2, m3 = st.columns(3)
                m1.metric("USD", f"{price_usd:.2f} $", f"{change_pct:.2f} %")
                m2.metric("EUR", f"{price_eur:.2f} €", f"{change_pct:.2f} %")
                m3.metric("RSI", f"{current_rsi:.1f}")

                # CHART
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Kurs"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name="RSI", line=dict(color='#bb86fc', width=2)), row=2, col=1)
                fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False, dragmode='zoom', margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)

        elif mode == "Prognosen":
            st.title(f"🎯 Prognosen & News")
            price_usd = info.get('currentPrice') or 0.0
            target_usd = info.get('targetMeanPrice')
            
            if target_usd:
                target_eur = target_usd * usd_to_eur_rate
                upside = ((target_usd - price_usd) / price_usd) * 100
                c1, c2 = st.columns(2)
                c1.metric("Kursziel (USD)", f"{target_usd:.2f} $")
                c2.metric("Kursziel (EUR)", f"{target_eur:.2f} €")
                st.write(f"### Potenzial: **{upside:.2f} %**")
                recommendation = info.get('recommendationKey', 'N/A').replace('_', ' ').title()
                st.info(f"Analysten-Rating: **{recommendation}**")
            
            st.write("---")
            st.subheader("📰 Aktuelle Nachrichten")
            news_list = ticker.news
            if news_list:
                for item in news_list[:5]:
                    date = datetime.fromtimestamp(item['providerPublishTime']).strftime('%d.%m.%Y %H:%M')
                    st.markdown(f"""
                    <div class="news-box">
                        <small>{date} | {item['publisher']}</small><br>
                        <a href="{item['link']}" target="_blank" style="color: #bb86fc; text-decoration: none; font-weight: bold;">{item['title']}</a>
                    </div>
                    """, unsafe_allow_html=True)

        elif mode == "Positionsrechner":
            st.title("🧮 Risiko-Planer")
            curr_p_eur = (info.get('currentPrice') or 0.0) * usd_to_eur_rate
            entry = st.number_input("Einstieg (€)", value=float(curr_p_eur))
            stop = st.number_input("Stop Loss (€)", value=float(curr_p_eur * 0.9))
            risk = st.number_input("Max. Verlust (€)", value=100.0)
            if entry > stop:
                qty = int(risk / (entry - stop))
                st.success(f"Empfehlung: **{qty} Stück** kaufen")
                st.write(f"Einsatz: {qty * entry:.2f} € | Risiko: {risk:.2f} €")

    except Exception as e:
        st.error(f"Fehler: {e}")
