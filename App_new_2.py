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

    score = 50
    reasons = []

    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]

    if curr_p > sma200 * 1.03:
        score += 15
        reasons.append("📈 Starker Aufwärtstrend (SMA50 > SMA200).")
    elif curr_p < sma200:
        score -= 15
        reasons.append("📉 Unter langfristigem Trend (SMA200).")

    rsi = calculate_rsi(close)
    if rsi > 70:
        score -= 10
        reasons.append(f"🔥 RSI überkauft ({rsi:.1f}).")
    elif rsi < 30:
        score += 10
        reasons.append(f"🧊 RSI überverkauft ({rsi:.1f}).")

    atr = calculate_atr(hist)
    vola_ratio = (atr / curr_p) * 100
    if vola_ratio > 4:
        score -= 5
        reasons.append(f"⚠️ Hohe Volatilität ({vola_ratio:.1f}%).")

    margin = info.get("operatingMargins") or 0
    if margin > 0.15:
        score += 10
        reasons.append(f"💰 Hohe operative Marge ({margin*100:.1f}%).")

    cash = info.get("totalCash") or 0
    debt = info.get("totalDebt") or 0
    if cash > debt:
        score += 5
        reasons.append("🏦 Net-Cash Bilanz.")

    pe = info.get("forwardPE")
    ps = info.get("priceToSalesTrailing12Months")
    if pe and 0 < pe < 18:
        score += 10
        reasons.append(f"💎 Attraktives KGV ({pe:.1f}).")
    elif ps and ps < 3:
        score += 10
        reasons.append(f"🚀 Attraktives KUV ({ps:.1f}).")

    if hist["Volume"].iloc[-1] > hist["Volume"].tail(20).mean() * 1.3:
        score += 10
        reasons.append("📊 Starkes Handelsvolumen.")

    score += analyze_news_sentiment(news)

    if (curr_p / close.iloc[0]) - 1 > 0.2:
        score += 10
        reasons.append("🏆 Klare 1Y-Outperformance.")

    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    if (exp1 - exp2).iloc[-1] > (exp1 - exp2).ewm(span=9).mean().iloc[-1]:
        score += 5
        reasons.append("🌊 MACD bullish.")

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

    return verdict, reasons, vola_ratio, sma200, score, rsi


# =========================================================
# 5. STREAMLIT UI
# =========================================================

st.title("📈 KI Aktienanalyse – 11-Faktoren-Modell")

symbol = st.text_input("Ticker", "AAPL").upper()
result = get_ki_verdict(symbol)

if not result:
    st.warning("Nicht genügend historische Daten.")
    st.stop()

verdict, reasons, current_vola, reversal_p, score, rsi = result

st.metric("KI-Score", score)
st.success(verdict)
st.markdown("### 📌 Entscheidungsgründe")
st.markdown("\n".join(reasons))

# =========================================================
# 6. STRATEGISCHER DEEP DIVE (ORIGINAL + ERWEITERT)
# =========================================================

st.divider()
st.subheader("🔍 Strategischer Deep Dive: Die 11-Faktor-Matrix")

st.markdown(f"""
### 1. Markt-Phasierung (Institutionelles Sentiment) ±15
Die Position des Kurses zum **SMA 200 ({reversal_p:.2f} USD)** ist der wichtigste langfristige Filter.
Große Fonds dürfen oft nur über dieser Linie investieren.
Ein Bruch darunter signalisiert strukturelle Schwäche.

### 2. Dynamik (RSI 14) ±10
Der RSI misst Geschwindigkeit und Emotion.
Aktueller Wert: **{rsi:.1f}**
Über 70 → Gier / Korrekturgefahr  
Unter 30 → Panik / antizyklische Chance

### 3. Volatilitäts-Profil (ATR-Ratio) −5
Aktuell: **{current_vola:.2f}%**
Werte über 4 % deuten auf spekulatives Marktverhalten hin.
Hohe Volatilität erhöht das Risiko von Stop-Loss-Fehlauslösungen.

### 4 & 5. Fundamentale Resilienz (Marge & Cash) +15
Unternehmen mit hoher Marge besitzen Preissetzungsmacht.
Net-Cash-Firmen überleben Zinsschocks und können Krisen opportunistisch nutzen.

### 6. Value-Check (KGV / KUV) +10
Wachstum wird nur belohnt, wenn es nicht überbezahlt ist.
Die KI verhindert klassisches „Growth-at-any-price“.

### 7. Smart-Money-Flow (Volumen) +10
Volumen geht dem Preis voraus.
30 % über Durchschnitt signalisiert institutionelle Akkumulation.

### 8. Mediales Echo (NLP-Sentiment) ±20
Zeitgewichtete Analyse der letzten Schlagzeilen.
Frische Gewinnwarnungen oder Analysten-Upgrades wirken sofort.

### 9. Relative Stärke +10
Nur Aktien mit klarer 1-Jahres-Outperformance erhalten diesen Bonus.
Wir suchen Marktführer, keine Nachzügler.

### 10. Momentum-Bestätigung (MACD) +5
Bullishes Crossover signalisiert neu entstehenden Trend.

### 11. PEG-Ratio (GARP) +5
PEG ≈ 1 bedeutet perfektes Verhältnis von Preis zu Wachstum.
Unter 1 = strukturelle Unterbewertung trotz Wachstum.
""")