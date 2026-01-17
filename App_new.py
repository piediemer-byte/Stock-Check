import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. FUNKTIONEN ---
def calculate_rsi(data, window=14):
    if len(data) < window: return pd.Series(index=data.index)
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=3600)
def get_industry_recommendations(industry, eur_val):
    sectors = {
        "Verteidigung/Militär": ["LMT", "RTX", "NOC", "GD", "BA", "RHM.DE", "HENS.DE", "BAESY", "LHX", "RKLB"],
        "Lebensmittel": ["KO", "PEP", "PG", "NESN.SW", "MDLZ", "COST", "WMT", "TSN", "ADM", "K"],
        "Energie": ["XOM", "CVX", "SHEL", "BP", "TTE", "ENI.MI", "RWE.DE", "EON.DE", "NEE", "SLB"],
        "Pharma": ["PFE", "JNJ", "ABBV", "LLY", "NVO", "MRK", "AZN", "GSK", "BAYN.DE", "RHHBY"]
    }
    candidates = sectors.get(industry, [])
    sb_list = []
    for s in candidates:
        try:
            t = yf.Ticker(s)
            info = t.info
            rating = info.get('recommendationMean')
            if rating and rating <= 2.2:
                p = (info.get('currentPrice') or info.get('regularMarketPrice') or 0) * eur_val
                div = (info.get('dividendYield', 0) or 0) * 100
                sb_list.append({"Symbol": s, "Name": info.get('shortName', s), "Preis (€)": round(p, 2), "Rating": rating, "Dividende": round(div, 2)})
        except: continue
    return pd.DataFrame(sb_list).sort_values(by="Preis (€)").head(10)

# --- 2. KONFIGURATION & STYLING ---
st.set_page_config(page_title="StockIntelligence Pro", layout="wide")
st.markdown("""
<style>
    .main { background-color: #0e1117; color: white; }
    div[data-testid="stMetric"] { background-color: #000 !important; border: 1px solid #333; padding: 15px; border-radius: 10px; }
    div.stButton > button { background-color: #1e1e1e; color: white; border: 1px solid #444; }
    div[data-testid="column"]:nth-child(odd) .stButton > button { border-radius: 20px 0 0 20px !important; border-right: none !important; }
    div[data-testid="column"]:nth-child(even) .stButton > button { border-radius: 0 20px 20px 0 !important; color: #ef5350 !important; }
    .sb-card { background-color: #1e1e1e; padding: 15px; border-radius: 12px; border-left: 5px solid #bb86fc; margin-bottom: 12px; border-right: 1px solid #333;}
    .div-badge { background-color: #26a69a; color: white; padding: 2px 8px; border-radius: 5px; font-size: 0.8em; font-weight: bold; }
    .ai-box { background-color: #1a1c23; border: 1px solid #00d1ff; padding: 25px; border-radius: 15px; margin-top: 25px; }
    .ai-tag { background-color: #00d1ff; color: black; padding: 3px 10px; border-radius: 5px; font-weight: bold; font-size: 0.8em; }
</style>
""", unsafe_allow_html=True)

# --- 3. SESSION STATE ---
if 'watchlist' not in st.session_state: st.session_state.watchlist = ["RIOT", "AAPL", "MSFT"]
if 'search_query' not in st.session_state: st.session_state.search_query = "RIOT"
if 'period' not in st.session_state: st.session_state.period = '1y'

# --- 4. HEADER ---
st.title("📈 StockIntelligence Pro")
col_search, col_add, col_clear = st.columns([4, 0.5, 0.8])
search_input = col_search.text_input("Ticker suchen:", value=st.session_state.search_query).strip().upper()

if search_input != st.session_state.search_query:
    st.session_state.search_query = search_input

if col_add.button("⭐"):
    if search_input and search_input not in st.session_state.watchlist:
        st.session_state.watchlist.append(search_input)
        st.rerun()

if col_clear.button("🗑️"):
    st.session_state.watchlist = []
    st.rerun()

# Favoriten Pillen
if st.session_state.watchlist:
    for i in range(0, len(st.session_state.watchlist), 4):
        row = st.session_state.watchlist[i:i+4]
        cols = st.columns([2, 0.6, 2, 0.6, 2, 0.6, 2, 0.6])
        for idx, symbol in enumerate(row):
            with cols[idx*2]:
                if st.button(symbol, key=f"n_{symbol}", use_container_width=True):
                    st.session_state.search_query = symbol
                    st.rerun()
            with cols[idx*2 + 1]:
                if st.button("×", key=f"x_{symbol}", use_container_width=True):
                    st.session_state.watchlist.remove(symbol)
                    st.rerun()

st.write("---")
mode = st.radio("Menü:", ["Analyse", "Prognosen", "Strong Buy", "Positionsrechner"], horizontal=True)

try:
    eur_usd_rate = yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)
    eur_to_usd_factor = 1 / eur_usd_rate
except: eur_to_usd_factor = 0.92

# --- 5. LOGIK ---
if mode == "Analyse" and st.session_state.search_query:
    try:
        ticker = yf.Ticker(st.session_state.search_query)
        period_map = {"1d": ("1d", "1m"), "5d": ("5d", "5m"), "1mo": ("1mo", "1d"), "6mo": ("6mo", "1d"), "1y": ("1y", "1d")}
        p, interval = period_map.get(st.session_state.period, ("1y", "1d"))
        
        df_full = ticker.history(period="2y", interval="1d")
        plot_df = ticker.history(period=p, interval=interval)
        
        if not plot_df.empty:
            info = ticker.info
            st.subheader(f"{info.get('longName', st.session_state.search_query)}")
            
            t_cols = st.columns(5)
            for i, (label, pk) in enumerate([("1T", "1d"), ("1W", "5d"), ("1M", "1mo"), ("6M", "6mo"), ("1J", "1y")]):
                if t_cols[i].button(label, key=f"z_{pk}", type="primary" if st.session_state.period == pk else "secondary", use_container_width=True):
                    st.session_state.period = pk
                    st.rerun()

            start_p = plot_df['Close'].iloc[0]
            end_p = plot_df['Close'].iloc[-1]
            perf_pct = ((end_p / start_p) - 1) * 100
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Preis (€)", f"{end_p * eur_to_usd_factor:.2f} €", delta=f"{perf_pct:.2f}%")
            m2.metric("Preis ($)", f"{end_p:.2f} $")
            
            df_full['SMA50'] = df_full['Close'].rolling(50).mean()
            df_full['SMA200'] = df_full['Close'].rolling(200).mean()
            df_full['RSI'] = calculate_rsi(df_full)
            latest_rsi = df_full['RSI'].iloc[-1]
            m3.metric("RSI (14)", f"{latest_rsi:.1f}")
            m4.metric("Dividende", f"{(info.get('dividendYield', 0) or 0)*100:.2f} %")

            st.write("---")
            sc1, sc2, sc3 = st.columns(3)
            s50, s100, s200 = sc1.checkbox("SMA 50"), sc2.checkbox("SMA 100"), sc3.checkbox("SMA 200")

            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.5, 0.2, 0.3], vertical_spacing=0.07, subplot_titles=("Kurs", "Volumen", "RSI Indicator"))
            fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name="Kurs"), row=1, col=1)
            
            if s50: fig.add_trace(go.Scatter(x=df_full.tail(len(plot_df)).index, y=df_full['SMA50'].tail(len(plot_df)), name="SMA 50", line=dict(color='#00d1ff')), row=1, col=1)
            if s200: fig.add_trace(go.Scatter(x=df_full.tail(len(plot_df)).index, y=df_full['SMA200'].tail(len(plot_df)), name="SMA 200", line=dict(color='#ff4b4b')), row=1, col=1)
            fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['Volume'], name="Volumen", marker_color='#333'), row=2, col=1)
            
            rsi_plot = df_full['RSI'].tail(len(plot_df))
            fig.add_trace(go.Scatter(x=plot_df.index, y=rsi_plot, name="RSI", line=dict(color='#bb86fc', width=2)), row=3, col=1)
            fig.add_hrect(y0=70, y1=100, fillcolor="red", opacity=0.1, line_width=0, row=3, col=1)
            fig.add_hrect(y0=0, y1=30, fillcolor="green", opacity=0.1, line_width=0, row=3, col=1)
            fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            # --- KI ZUSAMMENFASSUNG & VOLATILITÄT ---
            volatility = plot_df['Close'].pct_change().std() * np.sqrt(252) * 100
            target_price = end_p * (1 + (perf_pct/100))
            
            st.markdown('<div class="ai-box">', unsafe_allow_html=True)
            st.markdown('<h3><span class="ai-tag">PRO</span> KI-Trend-Analyse</h3>', unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.write("**Risiko-Profil:**")
                st.write(f"Vola: {volatility:.1f}% (" + ("Hoch" if volatility > 30 else "Normal") + ")")
            with c2:
                st.write("**Trend-Projektion:**")
                st.write(f"Ziel (€): ~{target_price * eur_to_usd_factor:.2f} €")
            with c3:
                st.write("**RSI-Status:**")
                st.write("🟢 Überverkauft" if latest_rsi < 30 else "🔴 Überkauft" if latest_rsi > 70 else "🟡 Neutral")
            
            st.write("---")
            advice = "Warten auf Rücksetzer." if latest_rsi > 65 else "Einstieg prüfen." if latest_rsi < 35 else "Trend folgen (Hold)."
            st.write(f"**Fazit:** Basierend auf dem RSI von {latest_rsi:.1f} und dem aktuellen Trend ({perf_pct:.1f}%): **{advice}**")
            st.markdown('</div>', unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Fehler: {e}")

elif mode == "Strong Buy":
    st.subheader("🔥 Top 10 Sektor-Favoriten")
    selected_ind = st.radio("Sektor:", ["Verteidigung/Militär", "Lebensmittel", "Energie", "Pharma"], horizontal=True)
    df_sb = get_industry_recommendations(selected_ind, eur_to_usd_factor)
    if not df_sb.empty:
        c1, c2 = st.columns(2)
        for idx, row in df_sb.iterrows():
            with (c1 if idx < 5 else c2):
                st.markdown(f'<div class="sb-card"><b>{row["Symbol"]}</b>: {row["Preis (€)"]} € <span class="div-badge">💎 {row["Dividende"]}%</span><br><small>{row["Name"]}</small></div>', unsafe_allow_html=True)
