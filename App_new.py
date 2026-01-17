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

# CSS für bessere mobile Darstellung
st.markdown("""<style> .main { padding: 0rem; } .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; } </style>""", unsafe_allow_html=True)

# --- 3. SIDEBAR ---
st.sidebar.title("Settings")
symbol = st.sidebar.text_input("Ticker Symbol:", value="RIOT").strip().upper()
mode = st.sidebar.selectbox("Modus:", ["Analyse", "Positionsrechner"])

# --- 4. DATEN LADEN ---
if symbol:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        df = ticker.history(period="1y")

        if not df.empty:
            df['RSI'] = calculate_rsi(df)
            current_rsi = df['RSI'].iloc[-1]
            current_price = info.get('currentPrice') or df['Close'].iloc[-1]

            # --- RATING LOGIK (Daumen-System) ---
            if current_rsi < 35:
                rating_text = "KAUFEN (Überverkauft)"
                rating_icon = "👍"
                rating_color = "green"
            elif current_rsi > 65:
                rating_text = "VERKAUFEN (Überkauft)"
                rating_icon = "👎"
                rating_color = "red"
            else:
                rating_text = "HALTEN (Neutral)"
                rating_icon = "✋"
                rating_color = "orange"

            if mode == "Analyse":
                st.title(f"{info.get('longName', symbol)}")
                
                # Top Rating Anzeige
                st.subheader(f"{rating_icon} Empfehlung: {rating_text}")
                
                # Metriken
                col1, col2 = st.columns(2)
                col1.metric("Kurs", f"{current_price:.2f} {info.get('currency', 'USD')}")
                col2.metric("RSI (14 Tage)", f"{current_rsi:.1f}")

                # RSI Erklärung
                with st.expander("ℹ️ Was ist der RSI? (Erklärung)"):
                    st.write("""
                    Der **Relative Strength Index (RSI)** misst die Geschwindigkeit von Kursbewegungen:
                    * **Unter 30-35:** Die Aktie gilt als 'überverkauft'. Ein Boden könnte nah sein (Kaufsignal).
                    * **Über 65-70:** Die Aktie gilt als 'überkauft'. Eine Korrektur ist wahrscheinlich (Verkaufsignal).
                    * **Zwischen 35-65:** Neutraler Bereich.
                    """)

                # Interaktives Chart (Zoombar per Finger)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
                
                # Preis-Chart
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Kurs"), row=1, col=1)
                
                # RSI-Chart
                fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name="RSI", line=dict(color='purple', width=2)), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

                fig.update_layout(height=600, xaxis_rangeslider_visible=False, dragmode='zoom')
                st.plotly_chart(fig, use_container_width=True)

            elif mode == "Positionsrechner":
                st.title("🧮 Risiko-Planer")
                depot = st.number_input("Dein Depot (€)", value=5000)
                risk_limit = st.slider("Risiko pro Trade (€)", 50, 500, 100)
                
                c1, c2 = st.columns(2)
                entry = c1.number_input("Einstiegspreis", value=float(current_price))
                stop = c2.number_input("Stop Loss", value=float(current_price * 0.9))
                
                if entry > stop:
                    risk_per_share = entry - stop
                    qty = int(risk_limit / risk_per_share)
                    st.success(f"### Kaufe: {qty} Stück")
                    st.write(f"Gesamteinsatz: {qty * entry:.2f} €")
                else:
                    st.error("Stop-Loss muss niedriger als der Einstieg sein!")

    except Exception as e:
        st.error(f"Fehler beim Laden: {e}")
