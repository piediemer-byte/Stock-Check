import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. FUNKTION FÜR KOMBI-SCANNER (RATING + CHART) ---
def get_pro_signals(usd_to_eur):
    candidates = [
        "NVDA", "AMZN", "MSFT", "GOOGL", "META", "AAPL", 
        "XOM", "CVX", "ABBV", "JNJ", "KO", "PG", "ASML", "SAP", "TSMC"
    ]
    results = []
    
    progress_bar = st.progress(0)
    for i, symbol in enumerate(candidates):
        try:
            t = yf.Ticker(symbol)
            info = t.info
            rating = info.get('recommendationMean')
            
            # Filter: Nur starke Ratings (Strong Buy / Buy)
            if rating and rating <= 2.1:
                # Hole Chart-Daten für SMA Check
                hist = t.history(period="1y")
                sma50 = hist['Close'].rolling(window=50).mean().iloc[-1]
                sma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
                
                is_bullish = sma50 > sma200
                price = (info.get('currentPrice') or hist['Close'].iloc[-1]) * usd_to_eur
                
                results.append({
                    "Symbol": symbol,
                    "Name": info.get('shortName', symbol),
                    "Preis": round(price, 2),
                    "Rating": rating,
                    "Bullish": is_bullish
                })
        except:
            continue
        progress_bar.progress((i + 1) / len(candidates))
    progress_bar.empty()
    
    if not results: return pd.DataFrame()
    return pd.DataFrame(results).sort_values(by="Preis").head(5)

# --- 2. APP KONFIGURATION ---
st.set_page_config(page_title="StockIntelligence Pro", layout="wide")

st.markdown("""
<style>
    .main { background-color: #0e1117; color: white; }
    .sb-card { 
        background-color: #1e1e1e; padding: 18px; border-radius: 12px; margin-bottom: 12px; 
        border-left: 6px solid #00ff00; box-shadow: 2px 2px 10px rgba(0,0,0,0.4);
    }
    .badge { padding: 3px 10px; border-radius: 6px; font-weight: bold; font-size: 0.75em; margin-right: 5px; }
    .badge-rating { background-color: #bb86fc; color: black; }
    .badge-bullish { background-color: #00d1ff; color: black; }
</style>
""", unsafe_allow_html=True)

# --- 3. SESSION STATE & HEADER (Wie zuvor) ---
if 'watchlist' not in st.session_state: st.session_state.watchlist = ["RIOT", "AAPL"]
if 'current_symbol' not in st.session_state: st.session_state.current_symbol = "RIOT"

st.title("📈 StockIntelligence Pro")
# (Hier Suche und Watchlist-Buttons wie im vorherigen Code...)

st.write("---")
mode = st.radio("Menü:", ["Analyse", "Prognosen", "Strong Buy", "Positionsrechner"], horizontal=True)

eur_usd = 1 / yf.Ticker("EURUSD=X").info.get('regularMarketPrice', 1.09)

# --- 4. LOGIK ---
if mode == "Strong Buy":
    st.subheader("🔥 Top 5 Expert-Picks")
    st.write("Gefiltert nach Analysten-Rating & technischem Trend.")
    
    df_res = get_pro_signals(eur_usd)
    
    if not df_res.empty:
        for _, row in df_res.iterrows():
            bullish_tag = f'<span class="badge badge-bullish">📈 Bullisch (SMA)</span>' if row['Bullish'] else ""
            st.markdown(f"""
            <div class="sb-card">
                <div style="display: flex; justify-content: space-between;">
                    <span style="font-size: 1.2em; font-weight: bold; color: #bb86fc;">{row['Symbol']}</span>
                    <span style="font-size: 1.2em;">{row['Preis']} €</span>
                </div>
                <div style="color: #999; margin-bottom: 10px;">{row['Name']}</div>
                <div>
                    <span class="badge badge-rating">Rating: {row['Rating']}</span>
                    {bullish_tag}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("Keine Treffer im aktuellen Scan.")

elif mode == "Analyse":
    # (Bestehende Analyse-Logik einfügen...)
    st.info(f"Wähle eine Aktie aus der Watchlist oder nutze die Suche für die Detail-Analyse.")
