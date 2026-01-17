import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. KI-LOGIK MIT BILANZ-CHECK ---
@st.cache_data(ttl=3600)
def get_ai_sector_picks(industry, eur_val):
    sectors = {
        "Verteidigung/Militär": ["LMT", "RTX", "NOC", "GD", "RHM.DE", "HENS.DE", "BAESY", "LHX", "RKLB"],
        "Lebensmittel": ["KO", "PEP", "PG", "NESN.SW", "MDLZ", "COST", "WMT", "TSN", "ADM"],
        "Energie": ["XOM", "CVX", "SHEL", "BP", "TTE", "RWE.DE", "EON.DE", "NEE", "SLB"],
        "Pharma": ["PFE", "JNJ", "ABBV", "LLY", "NVO", "MRK", "AZN", "GSK", "BAYN.DE"]
    }
    candidates = sectors.get(industry, [])
    scored_list = []

    for s in candidates:
        try:
            t = yf.Ticker(s)
            info = t.info
            hist = t.history(period="1mo")
            if len(hist) < 10: continue

            # --- FUNDAMENTAL-DATEN ---
            debt_to_equity = info.get('debtToEquity', 100) # Verschuldung
            margin = info.get('profitMargins', 0) # Marge
            pe_ratio = info.get('forwardPE', 20) # KGV
            price = (info.get('currentPrice') or info.get('regularMarketPrice', 0))
            target = info.get('targetMedianPrice', price)
            upside = ((target / price) - 1) * 100 if price > 0 else 0
            rsi = calculate_rsi(hist).iloc[-1]
            
            # --- KI-SCORING LOGIK ---
            score = 10 
            score += (upside / 4) # Bonus für Kurspotential
            score += (margin * 20) # Bonus für hohe Profitabilität
            if debt_to_equity > 150: score -= 5 # Abzug für hohe Schulden
            if pe_ratio > 40: score -= 4 # Abzug für hohe Bewertung
            if rsi > 70: score -= 6 # Abzug für Überkauft
            if rsi < 35: score += 3 # Bonus für Kaufsignal

            scored_list.append({
                "Symbol": s,
                "Name": info.get('shortName', s),
                "Preis (€)": round(price * eur_val, 2),
                "Upside": round(upside, 1),
                "Score": round(score, 1),
                "Verschuldung": debt_to_equity,
                "Marge": round(margin * 100, 1),
                "KGV": round(pe_ratio, 1),
                "Div": round((info.get('dividendYield', 0) or 0) * 100, 2)
            })
        except: continue
    
    return pd.DataFrame(scored_list).sort_values(by="Score", ascending=False).head(8)

def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

# --- 2. STYLING ---
st.set_page_config(page_title="StockIntelligence AI Fundamental", layout="wide")
st.markdown("""
<style>
    .main { background-color: #0e1117; color: white; }
    div[data-testid="stMetric"] { background-color: #000 !important; border: 1px solid #333; padding: 15px; border-radius: 10px; }
    .pick-card { background: #161b22; border: 1px solid #333; padding: 18px; border-radius: 12px; margin-bottom: 12px; }
    .section-header { background: linear-gradient(90deg, #00d1ff, #bb86fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.8em; font-weight: bold; margin-top: 30px; border-bottom: 1px solid #333; padding-bottom: 10px; }
    .stat-label { font-size: 0.75em; color: #888; text-transform: uppercase; }
    .stat-value { font-size: 0.9em; font-weight: bold; color: #eee; }
</style>
""", unsafe_allow_html=True)

# --- 3. HEADER & ANALYSE ---
if 'search_query' not in st.session_state: st.session_state.search_query = "MSFT"
st.title("💎 StockIntelligence AI Fundamental")

search_input = st.text_input("Aktie analysieren:", value=st.session_state.search_query).upper()
if search_input != st.session_state.search_query:
    st.session_state.search_query = search_input
    st.rerun()

eur_usd = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

try:
    ticker = yf.Ticker(st.session_state.search_query)
    df = ticker.history(period="1y")
    curr_p_eur = df['Close'].iloc[-1] * eur_usd
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Preis (€)", f"{curr_p_eur:.2f} €")
    m2.metric("KGV", f"{ticker.info.get('forwardPE', 'N/A')}")
    m3.metric("Marge", f"{ticker.info.get('profitMargins', 0)*100:.1f} %")

    # Chart
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
    fig.update_layout(template="plotly_dark", height=450, xaxis_rangeslider_visible=False, margin=dict(t=0,b=0,l=0,r=0))
    st.plotly_chart(fig, use_container_width=True)

    # --- 4. POSITIONSRECHNER ---
    st.markdown('<p class="section-header">🧮 Risiko-Kalkulation</p>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    entry = c1.number_input("Einstieg (€)", value=curr_p_eur)
    stop = c2.number_input("Stop-Loss (€)", value=entry * 0.95)
    risk = c3.number_input("Max. Risiko (€)", value=100.0)
    if entry > stop:
        st.info(f"👉 Kaufe **{int(risk/(entry-stop))} Aktien**")

    # --- 5. KI SEKTOR-PICKS (MIT BILANZ-LOGIK) ---
    st.markdown('<p class="section-header">🤖 KI-Picks: Bilanz & Fundamental Check</p>', unsafe_allow_html=True)
    sel_sector = st.radio("Sektor:", ["Verteidigung/Militär", "Lebensmittel", "Energie", "Pharma"], horizontal=True)
    
    with st.spinner("KI berechnet Bilanz-Scores..."):
        picks = get_ai_sector_picks(sel_sector, eur_usd)
        c_p1, c_p2 = st.columns(2)
        for i, row in picks.iterrows():
            with (c_p1 if i < 4 else c_p2):
                st.markdown(f"""
                <div class="pick-card">
                    <div style="display:flex; justify-content:space-between;">
                        <b style="color:#00d1ff;">{row['Symbol']}</b> <b>{row['Preis (€)']} €</b>
                    </div>
                    <div style="color:#888; font-size:0.8em; margin-bottom:10px;">{row['Name']}</div>
                    <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
                        <div><div class="stat-label">Upside</div><div class="stat-value">+{row['Upside']}%</div></div>
                        <div><div class="stat-label">KGV</div><div class="stat-value">{row['KGV']}</div></div>
                        <div><div class="stat-label">Marge</div><div class="stat-value">{row['Marge']}%</div></div>
                    </div>
                    <div style="margin-top:10px; padding-top:10px; border-top:1px solid #222; display:flex; justify-content:space-between;">
                        <span style="font-size:0.8em; color:#bb86fc;">KI-Score: {row['Score']}</span>
                        <span style="font-size:0.8em; color:{'#ff4b4b' if row['Verschuldung'] > 150 else '#00ff00'}">Schulden: {row['Verschuldung']}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

except Exception as e:
    st.error(f"Fehler: {e}")
