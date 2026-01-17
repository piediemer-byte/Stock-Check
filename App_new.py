import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. FUNKTIONEN ---
def calculate_rsi(data, window=14):
    if len(data) < window: return pd.Series()
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 2. KONFIGURATION & STYLING ---
st.set_page_config(page_title="StockIntelligence Pro", layout="wide")

st.markdown("""
<style>
    .main { background-color: #0e1117; color: white; }
    div[data-testid="stMetric"] { background-color: #000; border: 1px solid #333; padding: 15px; border-radius: 10px; }
    .stButton > button { border-radius: 8px; font-size: 0.85rem; height: 32px; }
    
    /* Favoriten-Tags Design */
    div[data-testid="column"]:nth-child(2) .stButton > button {
        border-top-left-radius: 0; border-bottom-left-radius: 0;
        margin-left: -25px; color: #ef5350; border-left: none;
    }
    div[data-testid="column"]:nth-child(1) .stButton > button {
        border-top-right-radius: 0; border-bottom-right-radius: 0;
    }
    .target-box { background-color: #1e1e1e; padding: 20px; border-radius: 12px; border: 1px solid #333; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 3. SESSION STATE ---
if 'watchlist' not in st.session_state: st.session_state.watchlist = ["RIOT", "AAPL", "MSFT"]
if 'search_query' not in st.session_state: st.session_state.search_query = "RIOT"
if 'period' not in st.session_state: st.session_state.period = '1y'

# --- 4. HEADER & SUCHE ---
st.title("📈 StockIntelligence Pro")

col_search, col_add, col_clear = st.columns([4, 0.5, 0.8])
search_input = col_search.text_input("Ticker suchen:", value=st.session_state.search_query, key="main_search").strip().upper()

if col_add.button("⭐"):
    if search_input and search_input not in st.session_state.watchlist:
        st.session_state.watchlist.append(search_input)
        st.rerun()

if col_clear.button("🗑️ Alle"):
    st.session_state.watchlist = []
    st.rerun()

# Favoriten-Tags
if st.session_state.watchlist:
    cols = st.columns(5)
    for i, s in enumerate(st.session_state.watchlist):
        with cols[i % 5]:
            c1, c2 = st.columns([2, 1])
            if c1.button(s, key=f"sel_{s}", use_container_width=True):
                st.session_state.search_query = s
                st.rerun()
            if c2.button("×", key=f"del_{s}", use_container_width=True):
                st.session_state.watchlist.remove(s)
                st.rerun()

st.write("---")
mode = st.radio("Menü:", ["Analyse", "Prognosen", "Strong Buy", "Positionsrechner"], horizontal=True)

# Währung & Daten-Fetch
eur_usd = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)
ticker = yf.Ticker(search_input)

# --- 5. HAUPTLOGIK ---
if mode == "Analyse" and search_input:
    try:
        info = ticker.info
        st.subheader(f"{info.get('longName', search_input)}")
        
        # Zeit-Buttons mit Highlight
        t_cols = st.columns(5)
        periods = [("1T", "1d"), ("1W", "5d"), ("1M", "1mo"), ("6M", "6mo"), ("1J", "1y")]
        for i, (label, p) in enumerate(periods):
            if t_cols[i].button(label, key=f"btn_p_{p}", type="primary" if st.session_state.period == p else "secondary", use_container_width=True):
                st.session_state.period = p
                st.rerun()

        df = ticker.history(period="2y", interval="1d")
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['SMA200'] = df['Close'].rolling(200).mean()
        df['RSI'] = calculate_rsi(df)

        # Metriken
        m1, m2, m3, m4, m5 = st.columns(5)
        curr_p = info.get('currentPrice') or df['Close'].iloc[-1]
        m1.metric("Preis (€)", f"{curr_p * eur_usd:.2f} €")
        m2.metric("RSI (14)", f"{df['RSI'].iloc[-1]:.1f}")
        m3.metric("KGV", f"{info.get('forwardPE', 'N/A')}")
        m4.metric("Dividende", f"{(info.get('dividendYield', 0) or 0)*100:.2f} %")
        
        rating = info.get('recommendationMean', 3.0)
        rec_text = "👍 Strong Buy" if rating <= 2.0 else "✅ Buy" if rating <= 2.5 else "➡️ Hold"
        m5.metric("Rating", rec_text)

        # Chart
        plot_df = df.tail(365 if st.session_state.period == '1y' else 180 if st.session_state.period == '6mo' else 30)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name="Kurs"), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA50'], name="SMA 50", line=dict(color='#00d1ff')), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA200'], name="SMA 200", line=dict(color='#ff4b4b')), row=1, col=1)
        fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['Volume'], name="Volumen", marker_color='#333'), row=2, col=1)
        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    except: st.error("Datenfehler.")

elif mode == "Prognosen":
    info = ticker.info
    st.subheader(f"🎯 Kursziele für {search_input}")
    
    current = info.get('currentPrice', 0)
    target = info.get('targetMeanPrice', 0)
    
    if target > 0:
        diff = ((target / current) - 1) * 100
        color = "#00ff00" if diff > 0 else "#ff4b4b"
        
        st.markdown(f"""
        <div class="target-box">
            <h4 style="margin:0;">Durchschnittliches Analysten-Kursziel</h4>
            <h2 style="color:{color}; margin:10px 0;">{target * eur_usd:.2f} €</h2>
            <p>Das entspricht einem Potenzial von <b>{diff:.2f} %</b> zum aktuellen Kurs.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Visualisierung des Kursziels
        fig_target = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = current,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Aktueller Preis vs. Kursziel (USD)"},
            gauge = {
                'axis': {'range': [None, max(target, current) * 1.2]},
                'bar': {'color': "#bb86fc"},
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': target
                }
            }
        ))
        fig_target.update_layout(template="plotly_dark", height=300)
        st.plotly_chart(fig_target, use_container_width=True)
    else:
        st.info("Keine Kursziel-Daten von Analysten verfügbar.")

    st.write("---")
    st.subheader("📰 Letzte News")
    for n in ticker.news[:5]:
        st.markdown(f"**{n['publisher']}**: [{n['title']}]({n['link']})")
