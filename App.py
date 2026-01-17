import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- RSI BERECHNUNG ---
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- APP LAYOUT ---
st.set_page_config(page_title="Pro-Trader Dashboard 2026", layout="wide")

st.sidebar.title("🎮 Terminal")
mode = st.sidebar.selectbox("Funktion:", ["Analyse & Timing", "Positionsrechner"])

# --- MODUS 1: ANALYSE & TIMING ---
if mode == "Analyse & Timing":
    symbol = st.sidebar.text_input("Ticker:", value="RIOT")
    t = yf.Ticker(symbol)
    df = t.history(period="1y")
    
    if not df.empty:
        df['RSI'] = calculate_rsi(df)
        current_rsi = df['RSI'].iloc[-1]
        
        st.title(f"Analyse: {symbol}")
        
        # KI-Timing Bewertung
        if current_rsi > 70:
            st.error(f"⚠️ ACHTUNG: Überkauft (RSI: {current_rsi:.1f}). Warte auf Rücksetzer!")
        elif current_rsi < 30:
            st.success(f"🚀 CHANCE: Überverkauft (RSI: {current_rsi:.1f}). Möglicher Boden gefunden!")
        else:
            st.info(f"⚖️ NEUTRAL: RSI bei {current_rsi:.1f}. Trend stabil.")

        # Kombi-Chart (Preis + RSI)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.7, 0.3])
        
        # Kurs-Chart
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Preis"), row=1, col=1)
        
        # RSI-Chart
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name="RSI", line=dict(color='purple')), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
        
        fig.update_layout(height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

# --- MODUS 2: POSITIONSRECHNER ---
elif mode == "Positionsrechner":
    st.title("🧮 Risiko-Rechner")
    depot = st.number_input("Depotwert (€)", value=10000)
    risk_pct = st.slider("Risiko (%)", 0.5, 5.0, 1.0)
    
    col1, col2 = st.columns(2)
    entry = col1.number_input("Einstieg (€)", value=19.0)
    stop = col2.number_input("Stop Loss (€)", value=16.5)
    
    if entry > stop:
        max_loss = (depot * risk_pct) / 100
        qty = int(max_loss / (entry - stop))
        st.success(f"Kauf-Empfehlung: **{qty} Stück**")
        st.write(f"Gesamteinsatz: {qty * entry:.2f} € | Risiko: {max_loss:.2f} €")
