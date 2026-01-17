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

@st.cache_data(ttl=3600)
def get_industry_recommendations(industry, usd_to_eur):
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
                price = (info.get('currentPrice') or info.get('regularMarketPrice') or 0) * usd_to_eur
                div = (info.get('dividendYield', 0) or 0) * 100
                sb_list.append({"Symbol": s, "Name": info.get('shortName', s), "Preis (€)": round(price, 2), "Rating": rating, "Dividende": round(div, 2)})
        except: continue
    return pd.DataFrame(sb_list).sort_values(by="Preis (€)").head(10)

# --- 2. KONFIGURATION & STYLING ---
st.set_page_config(page_title="StockIntelligence Pro", layout="wide")

st.markdown("""
<style>
    .main { background-color: #0e1117; color: white; }
    div[data-testid="stMetric"] { background-color: #000; border: 1px solid #333; padding: 15px; border-radius: 10px; }
    div.stButton > button { background-color: #1e1e1e; color: white; border: 1px solid #444; }
    div[data-testid="column"]:nth-child(odd) .stButton > button { border-radius: 20px 0 0 20px !important; border-right: none !important; }
    div[data-testid="column"]:nth-child(even) .stButton > button { border-radius: 0 20px 20px 0 !important; color: #ef5350 !important; }
    .sb-card { background-color: #1e1e1e; padding: 15px; border-radius: 12px; border-left: 5px solid #bb86fc; margin-bottom: 12px; }
    .div-badge { background-color: #26a69a; color: white; padding: 2px 8px; border-radius: 5px; font-size: 0.8em; }
</style>
""", unsafe_allow_html=True)

# --- 3. SESSION STATE ---
if 'watchlist' not in st.session_state: st.session_state.watchlist = ["RIOT", "AAPL", "MSFT"]
if 'search_query' not in st.session_state: st.session_state.search_query = "RIOT"
if 'period' not in st.session_state: st.session_state.period = '1y'

# --- 4. HEADER ---
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

# Favoriten Pillen
if st.session_state.watchlist:
    cols_wrap = st.columns(4)
    for idx, symbol in enumerate(st.session_state.watchlist):
        with cols_wrap[idx % 4]:
            c1, c2 = st.columns([2, 0.6])
            if c1.button(symbol, key=f"n_{symbol}", use_container_width=True):
                st.session_state.search_query = symbol
                st.rerun()
            if c2.button("×", key=f"x_{symbol}", use_container_width=True):
                st.session_state.watchlist.remove(symbol)
                st.rerun()

st.write("---")
mode = st.radio("Menü:", ["Analyse", "Prognosen", "Strong Buy", "Positionsrechner"], horizontal=True)
eur_usd = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

# --- 5. LOGIK ---
if mode == "Analyse" and search_input:
    try:
        ticker = yf.Ticker(search_input)
        # Immer 2 Jahre laden für SMA-Berechnung
        df_full = ticker.history(period="2y")
        
        if not df_full.empty:
            info = ticker.info
            st.subheader(f"{info.get('longName', search_input)}")
            
            # ZEITACHSEN BUTTONS
            t_cols = st.columns(5)
            periods = [("1T", "1d"), ("1W", "5d"), ("1M", "1mo"), ("6M", "6mo"), ("1J", "1y")]
            for i, (label, p) in enumerate(periods):
                if t_cols[i].button(label, key=f"z_{p}", type="primary" if st.session_state.period == p else "secondary", use_container_width=True):
                    st.session_state.period = p
                    st.session_state.search_query = search_input
                    st.rerun()

            # SMA CHECKBOXEN (Default: False/Aus)
            st.write("Indikatoren einblenden:")
            sc1, sc2, sc3 = st.columns(3)
            show_50 = sc1.checkbox("SMA 50 (Blau)", value=False)
            show_100 = sc2.checkbox("SMA 100 (Gelb)", value=False)
            show_200 = sc3.checkbox("SMA 200 (Rot)", value=False)

            # Datenaufbereitung
            df_full['SMA50'] = df_full['Close'].rolling(50).mean()
            df_full['SMA100'] = df_full['Close'].rolling(100).mean()
            df_full['SMA200'] = df_full['Close'].rolling(200).mean()
            df_full['RSI'] = calculate_rsi(df_full)

            days_map = {"1d": 2, "5d": 7, "1mo": 30, "6mo": 180, "1y": 365}
            plot_df = df_full.tail(days_map.get(st.session_state.period, 365))

            # Metriken
            m1, m2, m3, m4, m5 = st.columns(5)
            curr_p = info.get('currentPrice') or df_full['Close'].iloc[-1]
            m1.metric("Preis (€)", f"{curr_p * eur_usd:.2f} €")
            m2.metric("RSI (14)", f"{df_full['RSI'].iloc[-1]:.1f}")
            m3.metric("KGV", f"{info.get('forwardPE', 'N/A')}")
            m4.metric("Dividende", f"{(info.get('dividendYield', 0) or 0)*100:.2f} %")
            rating = info.get('recommendationMean', 3.0)
            m5.metric("Rating", "👍 Strong Buy" if rating <= 2.0 else "✅ Buy" if rating <= 2.5 else "➡️ Hold")

            # Chart
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name="Kurs"), row=1, col=1)
            
            if show_50: fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA50'], name="SMA 50", line=dict(color='#00d1ff')), row=1, col=1)
            if show_100: fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA100'], name="SMA 100", line=dict(color='#ffea00')), row=1, col=1)
            if show_200: fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA200'], name="SMA 200", line=dict(color='#ff4b4b')), row=1, col=1)
            
            fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['Volume'], name="Volumen", marker_color='#333'), row=2, col=1)
            fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
    except:
        st.error("Daten konnten nicht geladen werden.")

elif mode == "Strong Buy":
    st.subheader("🔥 Top 10 Sektor-Favoriten")
    selected_industry = st.radio("Branche:", ["Verteidigung/Militär", "Lebensmittel", "Energie", "Pharma"], horizontal=True)
    with st.spinner("Scanne Markt..."):
        df_sb = get_industry_recommendations(selected_industry, eur_usd)
        if not df_sb.empty:
            c1, c2 = st.columns(2)
            for idx, row in df_sb.iterrows():
                with (c1 if idx < 5 else c2):
                    st.markdown(f"""<div class="sb-card"><b>{row['Symbol']}</b> - {row['Preis (€)']} € <span class="div-badge">{row['Dividende']}% Div.</span><br><small>{row['Name']}</small></div>""", unsafe_allow_html=True)
        else: st.warning("Keine Treffer.")

elif mode == "Prognosen":
    st.subheader(f"Ziele für {search_input}")
    info = yf.Ticker(search_input).info
    target = info.get('targetMeanPrice', 0)
    if target > 0: st.success(f"Kursziel: {target * eur_usd:.2f} €")
    else: st.info("Keine Daten.")

elif mode == "Positionsrechner":
    st.subheader("🧮 Risiko-Planer")
    entry = st.number_input("Einstieg €", value=100.0)
    stop = st.number_input("Stop €", value=95.0)
    risk = st.number_input("Risiko €", value=50.0)
    if entry > stop: st.info(f"Stückzahl: {int(risk/(entry-stop))}")
