import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. RSI BERECHNUNG ---
def calculate_rsi(data, window=14):
    if len(data) < window: return pd.Series()
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 2. APP KONFIGURATION ---
st.set_page_config(page_title="Aktien-Check Mobile", layout="wide")

# CSS für Design: Schwarzer Hintergrund für Metriken & Weiße Schrift
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
    div[data-testid="stMetricLabel"] { color: #999 !important; }
    div[data-testid="stMetricValue"] { color: white !important; }
</style>
""", unsafe_allow_html=True)

# --- 3. SIDEBAR & EINSTELLUNGEN ---
st.sidebar.title("🎮 Terminal")
symbol = st.sidebar.text_input("Ticker Symbol:", value="RIOT").strip().upper()
mode = st.sidebar.selectbox("Modus:", ["Analyse", "Positionsrechner"])

period_map = {"1 Tag": "1d", "1 Woche": "5d", "1 Monat": "1mo", "6 Monate": "6mo", "1 Jahr": "1y"}
selected_period_label = st.sidebar.radio("Zeitraum:", list(period_map.keys()), index=4)
selected_period = period_map[selected_period_label]
interval = "1m" if selected_period == "1d" else "1h" if selected_period == "5d" else "1d"

# --- 4. DATEN & WÄHRUNGSKURS LADEN ---
if symbol:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        df = ticker.history(period=selected_period, interval=interval)
        
        # Euro-Umrechnungskurs holen
        eur_usd_ticker = yf.Ticker("EURUSD=X")
        usd_to_eur_rate = 1 / eur_usd_ticker.info.get('regularMarketPrice', 1.09)

        if not df.empty:
            df['RSI'] = calculate_rsi(df)
            current_rsi = df['RSI'].iloc[-1] if not df['RSI'].dropna().empty else 50.0
            price_usd = info.get('currentPrice') or df['Close'].iloc[-1]
            price_eur = price_usd * usd_to_eur_rate

            if mode == "Analyse":
                st.title(f"{info.get('longName', symbol)}")
                
                # DAUMEN RATING
                if current_rsi < 35:
                    st.success(f"👍 KAUFEN (RSI: {current_rsi:.1f})")
                elif current_rsi > 65:
                    st.error(f"👎 VERKAUFEN (RSI: {current_rsi:.1f})")
                else:
                    st.warning(f"✋ HALTEN (RSI: {current_rsi:.1f})")

                # Metriken in Schwarz/Weiß
                m1, m2, m3 = st.columns(3)
                m1.metric("Kurs (USD)", f"{price_usd:.2f} $")
                m2.metric("Kurs (EUR)", f"{price_eur:.2f} €")
                m3.metric("RSI", f"{current_rsi:.1f}")

                # CHART
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Kurs"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name="RSI", line=dict(color='#bb86fc', width=2)), row=2, col=1)
                
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

                fig.update_layout(
                    template="plotly_dark",
                    height=500,
                    xaxis_rangeslider_visible=False,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    dragmode='zoom'
                )
                st.plotly_chart(fig, use_container_width=True)

            elif mode == "Positionsrechner":
                st.title("🧮 Risiko-Planer")
                st.write(f"Aktueller Kurs: **{price_eur:.2f} €**")
                entry = st.number_input("Einstieg (€)", value=float(price_eur))
                stop = st.number_input("Stop Loss (€)", value=float(price_eur * 0.9))
                risk = st.number_input("Max. Verlust (€)", value=100.0)
                
                if entry > stop:
                    qty = int(risk / (entry - stop))
                    st.success(f"Kaufen: {qty} Stück")
                    st.write(f"Einsatz: {qty * entry:.2f} €")

    except Exception as e:
        st.error(f"Fehler: {e}")
