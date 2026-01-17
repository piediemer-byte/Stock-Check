import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. BERECHNUNGEN ---
def calculate_rsi(data, window=14):
    if len(data) < window: return pd.Series()
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_pro_signals(usd_to_eur):
    candidates = ["NVDA", "AMZN", "MSFT", "GOOGL", "META", "AAPL", "XOM", "CVX", "ABBV", "JNJ", "KO", "PG", "ASML", "SAP", "TSMC"]
    results = []
    prog = st.progress(0)
    for i, symbol in enumerate(candidates):
        try:
            t = yf.Ticker(symbol)
            rating = t.info.get('recommendationMean')
            if rating and rating <= 2.1:
                hist = t.history(period="1y")
                sma50 = hist['Close'].rolling(window=50).mean().iloc[-1]
                sma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
                price = (t.info.get('currentPrice') or hist['Close'].iloc[-1]) * usd_to_eur
                results.append({"Symbol": symbol, "Name": t.info.get('shortName', symbol), "Preis": round(price, 2), "Rating": rating, "Bullish": sma50 > sma200})
        except: continue
        prog.progress((i + 1) / len(candidates))
    prog.empty()
    return pd.DataFrame(results).sort_values(by="Preis").head(5)

# --- 2. KONFIGURATION & STYLING ---
st.set_page_config(page_title="StockIntelligence Pro", layout="wide")

st.markdown("""
<style>
    .main { background-color: #0e1117; color: white; }
    div[data-testid="stMetric"] { background-color: #000; border: 1px solid #333; padding: 15px; border-radius: 10px; }
    .news-box { background-color: #1e1e1e; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #bb86fc; }
    .stButton > button { border-radius: 20px; background-color: #1e1e1e; color: white; border: 1px solid #444; }
    .sb-card { background-color: #1e1e1e; padding: 18px; border-radius: 12px; margin-bottom: 12px; border-left: 6px solid #00ff00; }
    .badge { padding: 3px 8px; border-radius: 5px; font-weight: bold; font-size: 0.7em; margin-right: 5px; color: black; }
</style>
""", unsafe_allow_html=True)

# --- 3. SESSION STATE ---
if 'watchlist' not in st.session_state: st.session_state.watchlist = ["RIOT", "AAPL", "MSFT"]
if 'current_symbol' not in st.session_state: st.session_state.current_symbol = "RIOT"
if 'search_query' not in st.session_state: st.session_state.search_query = "RIOT"
if 'period' not in st.session_state: st.session_state.period = '1y'

# --- 4. HEADER & SUCHE ---
st.title("📈 StockIntelligence Pro")

col_search, col_add = st.columns([4, 1])
search_input = col_search.text_input("Ticker suchen (z.B. AAPL):", value=st.session_state.search_query, key="main_search").strip().upper()

if col_add.button("⭐ +"):
    if search_input and search_input not in st.session_state.watchlist:
        st.session_state.watchlist.append(search_input)
        st.rerun()

# Watchlist Tags nebeneinander
if st.session_state.watchlist:
    cols_wl = st.columns(len(st.session_state.watchlist))
    for i, s in enumerate(st.session_state.watchlist):
        with cols_wl[i]:
            c1, c2 = st.columns([3, 1])
            if c1.button(s, key=f"sel_{s}"):
                st.session_state.search_query = s
                st.session_state.current_symbol = s
                st.rerun()
            if c2.button("x", key=f"del_{s}"):
                st.session_state.watchlist.remove(s)
                st.rerun()

st.write("---")
mode = st.radio("Menü:", ["Analyse", "Prognosen", "Strong Buy", "Positionsrechner"], horizontal=True)

# Währung
eur_usd = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

# --- 5. HAUPTLOGIK ---
active_symbol = st.session_state.current_symbol if search_input == st.session_state.current_symbol else search_input

if mode == "Analyse" and active_symbol:
    try:
        ticker = yf.Ticker(active_symbol)
        st.subheader(f"{ticker.info.get('longName', active_symbol)}")
        
        # Zeit-Buttons
        t_cols = st.columns(5)
        periods = [("1T", "1d"), ("1W", "5d"), ("1M", "1mo"), ("6M", "6mo"), ("1J", "1y")]
        for i, (label, p) in enumerate(periods):
            if t_cols[i].button(label, key=f"p_{p}", type="primary" if st.session_state.period == p else "secondary"):
                st.session_state.period = p
                st.rerun()

        # SMA Toggles
        c1, c2, c3 = st.columns(3)
        show_50 = c1.checkbox("SMA 50", value=True)
        show_100 = c2.checkbox("SMA 100", value=False)
        show_200 = c3.checkbox("SMA 200", value=True)

        df = ticker.history(period="2y", interval="1d")
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['SMA100'] = df['Close'].rolling(100).mean()
        df['SMA200'] = df['Close'].rolling(200).mean()
        df['RSI'] = calculate_rsi(df)

        # Golden Cross Check
        if df['SMA50'].iloc[-1] > df['SMA200'].iloc[-1] and df['SMA50'].iloc[-2] <= df['SMA200'].iloc[-2]:
            st.success("🚀 GOLDEN CROSS erkannt!")

        # Metriken
        m1, m2, m3, m4, m5 = st.columns(5)
        curr_p = (ticker.info.get('currentPrice') or df['Close'].iloc[-1])
        div = (ticker.info.get('dividendYield', 0) or 0) * 100
        m1.metric("Preis (€)", f"{curr_p * eur_usd:.2f} €")
        m2.metric("RSI", f"{df['RSI'].iloc[-1]:.1f}", help="Relative Strength Index: <30 überverkauft, >70 überkauft.")
        m3.metric("KGV", f"{ticker.info.get('forwardPE', 'N/A')}", help="Kurs-Gewinn-Verhältnis: <15 günstig, >30 teuer.")
        m4.metric("Dividende", f"{div:.2f} %")
        m5.metric("Trend", "BULL" if df['SMA50'].iloc[-1] > df['SMA200'].iloc[-1] else "BEAR")

        # Chart
        plot_df = df.tail(365 if st.session_state.period == '1y' else 180)
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.2, 0.3])
        fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name="Kurs"), row=1, col=1)
        if show_50: fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA50'], name="SMA 50", line=dict(color='#00d1ff')), row=1, col=1)
        if show_100: fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA100'], name="SMA 100", line=dict(color='#ffea00')), row=1, col=1)
        if show_200: fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA200'], name="SMA 200", line=dict(color='#ff4b4b')), row=1, col=1)
        
        colors = ['green' if r['Open'] < r['Close'] else 'red' for _, r in plot_df.iterrows()]
        fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['Volume'], name="Volumen", marker_color=colors), row=2, col=1)
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['RSI'], name="RSI", line=dict(color='#bb86fc')), row=3, col=1)
        fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False, margin=dict(t=0,b=0,l=0,r=0))
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e: st.error(f"Fehler: {e}")

elif mode == "Strong Buy":
    st.subheader("🔥 Top 5 Expert-Picks")
    res = get_pro_signals(eur_usd)
    for _, row in res.iterrows():
        bull = '<span class="badge" style="background-color:#00d1ff">📈 Bullisch</span>' if row['Bullish'] else ""
        st.markdown(f'<div class="sb-card"><div style="display:flex;justify-content:space-between"><b>{row["Symbol"]}</b> <span>{row["Preis"]} €</span></div><small>{row["Name"]}</small><br><span class="badge" style="background-color:#bb86fc">Rating: {row["Rating"]}</span>{bull}</div>', unsafe_allow_html=True)

elif mode == "Prognosen":
    ticker = yf.Ticker(active_symbol)
    for n in ticker.news[:5]:
        st.markdown(f'<div class="news-box"><a href="{n["link"]}" target="_blank" style="color:#bb86fc;text-decoration:none"><b>{n["title"]}</b></a><br><small>{n["publisher"]}</small></div>', unsafe_allow_html=True)

elif mode == "Positionsrechner":
    st.subheader("🧮 Risiko-Planer")
    entry = st.number_input("Einstieg (€)", value=100.0)
    stop = st.number_input("Stop Loss (€)", value=90.0)
    risk = st.number_input("Risiko Betrag (€)", value=50.0)
    if entry > stop: st.success(f"Empfohlene Menge: {int(risk / (entry - stop))} Stück")
