import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- Hilfsfunktion: RSI ---
def calculate_rsi(data, window=14):
    if len(data) < window: return pd.Series()
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

st.set_page_config(page_title="Stock Intelligence 2026", layout="wide")

# --- Sidebar ---
st.sidebar.title("🎮 Terminal")
mode = st.sidebar.selectbox("Funktion:", ["Analyse & Timing", "Positionsrechner"])
symbol = st.sidebar.text_input("Ticker (z.B. RIOT oder AAPL):", value="RIOT").strip().upper()

if symbol:
    try:
        ticker = yf.Ticker(symbol)
        # Wir fordern nur notwendige Daten an, um Timeouts zu vermeiden
        info = ticker.info 
        
        if mode == "Analyse & Timing":
            st.title(f"Analyse: {info.get('longName', symbol)}")
            
            # --- KPI Sektion mit Fehlerprüfung ---
            curr_price = info.get('currentPrice') or info.get('regularMarketPrice')
            pe_ratio = info.get('forwardPE') or info.get('trailingPE')
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Kurs", f"{curr_price} {info.get('currency', 'USD')}")
            m2.metric("KGV", f"{pe_ratio:.2f}" if pe_ratio else "N/A")
            m3.metric("Marge", f"{info.get('profitMargins', 0)*100:.1f}%" if info.get('profitMargins') else "N/A")

            # --- Chart Sektion ---
            df = ticker.history(period="1y")
            if not df.empty:
                df['RSI'] = calculate_rsi(df)
                
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Preis"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name="RSI", line=dict(color='purple')), row=2, col=1)
                
                # RSI Linien
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
                
                fig.update_layout(height=500, xaxis_rangeslider_visible=False, margin=dict(t=20, b=20))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("Keine historischen Kursdaten gefunden.")

        elif mode == "Positionsrechner":
            st.title("🧮 Risiko-Management")
            # Wir nutzen den aktuellen Kurs als Vorschlag für den Einstieg
            live_price = info.get('currentPrice') or 0.0
            
            depot = st.number_input("Depotwert (€)", value=10000)
            risk_pct = st.slider("Risiko (%)", 0.5, 5.0, 1.0)
            entry = st.number_input("Einstieg (€)", value=float(live_price) if live_price > 0 else 10.0)
            stop = st.number_input("Stop Loss (€)", value=float(live_price * 0.85) if live_price > 0 else 8.5)
            
            if entry > stop:
                max_loss = (depot * risk_pct) / 100
                qty = int(max_loss / (entry - stop))
                st.success(f"Empfehlung: **{qty} Stück**")
                st.write(f"Einsatz: {qty * entry:.2f} € | Risiko: {max_loss:.2f} €")
            else:
                st.warning("Stop-Loss muss unter dem Einstieg liegen.")

    except Exception as e:
        st.error(f"Ein Fehler ist aufgetreten: {e}")
        st.info("Hinweis: Manche Ticker liefern am Wochenende oder bei API-Überlastung keine Daten. Prüfe auch, ob 'yfinance' aktuell ist.")
