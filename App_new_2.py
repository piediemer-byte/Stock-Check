import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# =========================================================
# 1. DATA LOADING (CACHED)
# =========================================================

@st.cache_data(ttl=1800)
def load_ticker(symbol: str):
    ticker = yf.Ticker(symbol)
    return ticker.info or {}, ticker.history(period="1y"), ticker.news or []

# =========================================================
# 2. TECHNICAL INDICATORS
# =========================================================

def calculate_rsi(close: pd.Series, period: int = 14) -> float:
    if len(close) < period + 1:
        return 50.0
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / (loss + 1e-9)
    return float(100 - (100 / (1 + rs.iloc[-1])))

def calculate_atr(hist: pd.DataFrame, period: int = 14) -> float:
    if len(hist) < period + 1:
        return 0.0
    tr = pd.concat(
        [
            hist["High"] - hist["Low"],
            (hist["High"] - hist["Close"].shift()).abs(),
            (hist["Low"] - hist["Close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])

# =========================================================
# 3. NEWS SENTIMENT
# =========================================================

def analyze_news_sentiment(news: list) -> float:
    if not news:
        return 0.0
    pos = ["upgraded", "buy", "growth", "beats", "profit", "bull", "chance"]
    neg = ["risk", "sell", "loss", "misses", "bear", "warn", "problem"]
    score = 0.0
    now = datetime.now(timezone.utc)
    for item in news[:5]:
        title = item.get("title", "").lower()
        ts = datetime.fromtimestamp(
            item.get("providerPublishTime", now.timestamp()), timezone.utc
        )
        age_h = (now - ts).total_seconds() / 3600
        w = 1.0 if age_h < 24 else 0.5 if age_h < 72 else 0.2
        if any(p in title for p in pos):
            score += 5 * w
        if any(n in title for n in neg):
            score -= 7 * w
    return float(np.clip(score, -15, 15))

# =========================================================
# 4. KI ANALYSE ENGINE (11 FAKTOREN)
# =========================================================

def get_ki_verdict(symbol: str):
    info, hist, news = load_ticker(symbol)
    if hist.empty or len(hist) < 200:
        return None

    close = hist["Close"]
    curr_p = float(close.iloc[-1])
    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]
    atr = calculate_atr(hist)
    rsi = calculate_rsi(close)
    vola_ratio = (atr / curr_p) * 100
    score = 50
    reasons = []

    # Trend / SMA
    trend_strength = (sma50 - sma200) / sma200
    reversal_p = sma200
    if trend_strength > 0.03:
        score += 15
        reasons.append("📈 Starker Aufwärtstrend (SMA50 > SMA200).")
    elif curr_p < sma200:
        score -= 15
        reasons.append("📉 Unter langfristigem Trend (SMA200).")

    # RSI
    if rsi > 70:
        score -= 10
        reasons.append(f"🔥 RSI überkauft ({rsi:.1f}).")
    elif rsi < 30:
        score += 10
        reasons.append(f"🧊 RSI überverkauft ({rsi:.1f}).")

    # Volatilität
    if vola_ratio > 4:
        score -= 5
        reasons.append(f"⚠️ Hohe Volatilität ({vola_ratio:.1f}%).")

    # Fundamentale Stabilität
    margin = info.get("operatingMargins") or 0
    if margin > 0.15:
        score += 10
        reasons.append(f"💰 Hohe operative Marge ({margin*100:.1f}%).")

    cash = info.get("totalCash") or 0
    debt = info.get("totalDebt") or 0
    if cash > debt:
        score += 5
        reasons.append("🏦 Net-Cash Bilanz.")

    # Bewertung
    pe = info.get("forwardPE")
    ps = info.get("priceToSalesTrailing12Months")
    if pe and 0 < pe < 18:
        score += 10
        reasons.append(f"💎 Attraktives KGV ({pe:.1f}).")
    elif ps and ps < 3:
        score += 10
        reasons.append(f"🚀 Attraktives KUV ({ps:.1f}).")

    # Volumen
    vol_avg = hist["Volume"].tail(20).mean()
    if hist["Volume"].iloc[-1] > vol_avg * 1.3:
        score += 10
        reasons.append("📊 Starkes Handelsvolumen.")

    # News Sentiment
    score += analyze_news_sentiment(news)

    # Relative Stärke 1Y
    perf_1y = (curr_p / close.iloc[0]) - 1
    if perf_1y > 0.2:
        score += 10
        reasons.append("🏆 Klare 1Y-Outperformance.")

    # MACD
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    if macd.iloc[-1] > signal.iloc[-1]:
        score += 5
        reasons.append("🌊 MACD bullish.")

    # PEG
    peg = info.get("pegRatio")
    if peg and 0.5 < peg < 1.5:
        score += 5
        reasons.append(f"⚖️ PEG optimal ({peg:.2f}).")

    score = int(np.clip(score, 0, 100))

    verdict = (
        "💎 STRONG BUY" if score >= 80 else
        "🚀 BUY" if score >= 60 else
        "➡️ HOLD" if score >= 35 else
        "🛑 SELL"
    )

    return {
        "verdict": verdict,
        "reasons": reasons,
        "current_price": curr_p,
        "sma50": sma50,
        "sma200": sma200,
        "rsi": rsi,
        "atr": atr,
        "volatility": vola_ratio,
        "score": score
    }

# =========================================================
# 5. STREAMLIT UI
# =========================================================

st.title("📈 KI Aktienanalyse – 11-Faktoren-Modell")

symbol = st.text_input("Ticker", "AAPL").upper()
analysis = get_ki_verdict(symbol)

if not analysis:
    st.warning("Nicht genügend historische Daten.")
    st.stop()

# --- Aktuelle Kurse & Key-Metriken ---
st.subheader(f"{symbol} – Aktuelle Kennzahlen")
st.metric("Aktueller Kurs", f"{analysis['current_price']:.2f} USD")
st.metric("SMA50", f"{analysis['sma50']:.2f}")
st.metric("SMA200", f"{analysis['sma200']:.2f}")
st.metric("RSI", f"{analysis['rsi']:.1f}")
st.metric("ATR", f"{analysis['atr']:.2f}")
st.metric("Volatilität (%)", f"{analysis['volatility']:.2f}")

# --- KI Score & Verdict ---
st.metric("KI-Score", analysis["score"])
st.success(analysis["verdict"])

# --- Entscheidungsgründe ---
st.subheader("📌 Entscheidungsgründe")
st.markdown("\n".join(analysis["reasons"]))

# =========================================================
# 6. STRATEGISCHER DEEP DIVE (Original aus Prompt)
# =========================================================

st.divider()
st.subheader("🔍 Strategischer Deep Dive: Die 11-Faktor-Matrix")
st.markdown(f"""
### 1. Markt-Phasierung (Institutionelles Sentiment) ±15
Der Kurs zum **SMA 200 ({analysis['sma200']:.2f} USD)** zeigt langfristigen Trend.  
Über SMA200 → gesund, darunter → Schwäche.  

### 2. Dynamik (RSI 14) ±10
Aktuell: **{analysis['rsi']:.1f}**  
> Überkauft (>70) → Korrekturgefahr  
> Überverkauft (<30) → antizyklischer Einstiegspunkt  

### 3. Volatilitäts-Profil (ATR-Ratio) −5
ATR: **{analysis['atr']:.2f}**, Volatilität: **{analysis['volatility']:.2f}%**  
Werte über 4 % deuten auf spekulatives Verhalten hin.  

### 4 & 5. Fundamentale Resilienz (Marge & Cash) +15
Hohes Operating Margin & Net-Cash → stabile Bilanz, Preissetzungsmacht, Krisenfestigkeit  

### 6. Value-Check (KGV/KUV) +10
KGV <18 oder KUV <3 → Wachstum zu attraktivem Preis  

### 7. Smart-Money Flow (Volumen) +10
Starkes Handelsvolumen signalisiert institutionelle Akkumulation  

### 8. Mediales Echo (NLP-Sentiment) ±20
News der letzten 5 Headlines, zeitgewichtete Analyse  

### 9. Relative Stärke +10
1Y Outperformance >20% → Alpha-Tier  

### 10. Momentum-Bestätigung (MACD) +5
Bullishes MACD-Crossover → Trendbestätigung  

### 11. PEG-Ratio (GARP) +5
PEG ~1 → fair bewertet, PEG <1 → Unterbewertung trotz Wachstum
""")

# =========================================================
# 7. AUTO-SCREENER: Top 5 STRONG BUY Aktien
# =========================================================

st.divider()
st.subheader("🚀 Auto Screener: Top 5 STRONG BUY Aktien auf Watchlist")
watchlist = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL",
    "META", "TSLA", "BRK-B", "JPM", "V", "PG",
    "UNH", "HD", "MA", "DIS"
]

results = []
for w in watchlist:
    data = get_ki_verdict(w)
    if data:
        results.append((w, data["verdict"], data["score"]))

strong_buys = [r for r in results if r[1] == "💎 STRONG BUY"]
strong_buys_sorted = sorted(strong_buys, key=lambda x: x[2], reverse=True)

if strong_buys_sorted:
    st.markdown("### 🔝 Top 5 STRONG BUY Aktien heute")
    for ticker, verdict, score in strong_buys_sorted[:5]:
        st.write(f"- **{ticker}** — {verdict} (Score: {score})")
else:
    st.info("Keine STRONG BUY Signale auf der Watchlist heute.")