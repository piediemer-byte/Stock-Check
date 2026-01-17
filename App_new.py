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
                price = (info.get('currentPrice') or info.get('regularMarketPrice') or 0) * eur_val
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
    .sb-card { background-color: #1e1e1e; padding: 15px; border-radius: 12px; border-left: 5px solid #bb86fc; margin-bottom: 12px; border-right: 1px solid #333;}
    .div-badge { background-color: #26a69a; color: white; padding: 2px 8px; border-radius: 5px; font-size: 0.8em; font-weight: bold; }
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

# Suche/State Sync
if search_input != st.session_state.search_query:
    st.session_state.search_query = search_input

if col_add.button("⭐"):
    if search_input and search_input not in st.session_state.watchlist:
        st.session_state.watchlist.append(search_input)
        st.rerun()

if col_clear.button("🗑️ Alle"):
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
mode = st.radio("Hauptmenü:", ["Analyse", "Prognosen", "Strong Buy", "Positionsrechner"], horizontal=True)
eur_usd = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

# --- 5. LOGIK ---
if mode == "Analyse" and st.session_state.search_query:
    try:
        current_symbol = st.session_state.search_query
        ticker = yf.Ticker(current_symbol)
        df_full = ticker.history(period="2y")
        
        if not df_full.empty:
            info = ticker.info
            st.subheader(f"{info.get('longName', current_symbol)}")
            
            # --- ZEITACHSEN BUTTONS (Synchronisiert & Markiert) ---
            t_cols = st.columns(5)
            periods = [("1T", "1d"), ("1W", "5d"), ("1M", "1mo"), ("6M", "6mo"), ("1J", "1y")]
            for i, (label, p) in enumerate(periods):
                # Button wird blau (primary), wenn p == st.session_state.period
                btn_type = "primary" if st.session_state.period == p else "secondary"
                if t_cols[i].button(label, key=f"z_{p}", type=btn_type, use_container_width=True):
                    st.session_state.period = p
                    st.rerun()

            # Kennzahlen
            m1, m2, m3, m4, m5 = st.columns(5)
            curr_p = info.get('currentPrice') or df_full['Close'].iloc[-1]
            m1.metric("Preis (€)", f"{curr_p * eur_usd:.2f} €")
            
            df_full['SMA50'] = df_full['Close'].rolling(50).mean()
            df_full['SMA100'] = df_full['Close'].rolling(100).mean()
            df_full['SMA200'] = df_full['Close'].rolling(200).mean()
            df_full['RSI'] = calculate_rsi(df_full)
            
            m2.metric("RSI (14)", f"{df_full['RSI'].iloc[-1]:.1f}")
            m3.metric("KGV", f"{info.get('forwardPE', 'N/A')}")
            m4.metric("Dividende", f"{(info.get('dividendYield', 0) or 0)*100:.2f} %")
            
            rating = info.get('recommendationMean', 3.0)
            rec_text = "👍 Strong Buy" if rating <= 2.1 else "✅ Buy" if rating <= 2.6 else "➡️ Hold"
            m5.metric("Rating", rec_text)

            # --- SMA CHECKBOXEN ---
            st.write("---")
            sc1, sc2, sc3 = st.columns(3)
            show_50 = sc1.checkbox("SMA 50 (Blau)", value=False)
            show_100 = sc2.checkbox("SMA 100 (Gelb)", value=False)
            show_200 = sc3.checkbox("SMA 200 (Rot)", value=False)

            # Chart Ausschnitt
            days_map = {"1d": 2, "5d": 7, "1mo": 30, "6mo": 180, "1y": 365}
            plot_df = df_full.tail(days_map.get(st.session_state.period, 365))

            # --- MULTI-CHART (Preis, Volumen, RSI) ---
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                                row_heights=[0.5, 0.2, 0.3], vertical_spacing=0.05,
                                subplot_titles=("Chart", "Volumen", "RSI (14)"))
            
            # Candlestick & SMAs
            fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name="Kurs"), row=1, col=1)
            if show_50: fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA50'], name="SMA 50", line=dict(color='#00d1ff', width=1.5)), row=1, col=1)
            if show_100: fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA100'], name="SMA 100", line=dict(color='#ffea00', width=1.5)), row=1, col=1)
            if show_200: fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA200'], name="SMA 200", line=dict(color='#ff4b4b', width=1.5)), row=1, col=1)
            
            # Volumen
            fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['Volume'], name="Volumen", marker_color='#333'), row=2, col=1)
            
            # RSI
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['RSI'], name="RSI", line=dict(color='#bb86fc', width=2)), row=3, col=1)
            # RSI Grenzlinien (30 & 70)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

            fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False, margin=dict(t=30,b=0,l=0,r=0))
            st.plotly_chart(fig, use_container_width=True)
            
    except Exception as e:
        st.error(f"Fehler: {e}. Bitte Ticker prüfen.")

elif mode == "Strong Buy":
    # (Bleibt identisch mit der funktionierenden Vorversion)
    st.subheader("🔥 Top 10 Sektor-Favoriten")
    selected_industry = st.radio("Sektor wählen:", ["Verteidigung/Militär", "Lebensmittel", "Energie", "Pharma"], horizontal=True)
    with st.spinner("Scanne Analysten-Ratings..."):
        df_sb = get_industry_recommendations(selected_industry, eur_usd)
        if not df_sb.empty:
            c1, c2 = st.columns(2)
            for idx, row in df_sb.iterrows():
                with (c1 if idx < (len(df_sb)/2) else c2):
                    st.markdown(f"""<div class="sb-card"><div style="display:flex; justify-content:space-between;"><b>{row['Symbol']}</b> <span>{row['Preis (€)']} €</span></div><small>{row['Name']}</small><br><span style="color:#00ff00;">Rating: {row['Rating']}</span> <span class="div-badge">💎 {row['Dividende']}%</span></div>""", unsafe_allow_html=True)
