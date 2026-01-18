import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# =========================================================
# 1. CACHING & DATA ACCESS
# =========================================================

@st.cache_data(ttl=3600)
def get_ticker_info(symbol: str) -> dict:
    return yf.Ticker(symbol).info

@st.cache_data(ttl=900)
def get_history(symbol: str, period: str):
    return yf.Ticker(symbol).history(period=period)

@st.cache_data(ttl=3600)
def get_eur_usd_rate() -> float:
    try:
        hist = yf.Ticker("EURUSD=X").history(period="1d")
        return 1 / float(hist['Close'].iloc[-1])
    except:
        return 0.92

def get_ticker_from_any(query: str) -> str:
    return query.upper() if len(query) <= 6 else query.upper()

# =========================================================
# 2. TECHNICAL INDICATORS
# =========================================================

def calculate_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / (loss + 1e-10)
    return float(100 - (100 / (1 + rs.iloc[-1])))

def calculate_atr(hist: pd.DataFrame, period: int = 14) -> float:
    tr = pd.concat([
        hist['High'] - hist['Low'],
        (hist['High'] - hist['Close'].shift()).abs(),
        (hist['Low'] - hist['Close'].shift()).abs()
    ], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])

def analyze_news_sentiment(news: list) -> float:
    if not news:
        return 0.0

    pos = ['upgraded', 'buy', 'growth', 'beats', 'profit', 'bull', 'chance']
    neg = ['risk', 'sell', 'loss', 'misses', 'bear', 'warn', 'problem']

    score = 0
    now = datetime.now(timezone.utc)

    for n in news[:5]:
        title = n.get("title", "").lower()
        ts = datetime.fromtimestamp(
            n.get("providerPublishTime", now.timestamp()),
            timezone.utc
        )
        age_h = (now - ts).total_seconds() / 3600
        w = 1.0 if age_h < 24 else 0.5 if age_h < 72 else 0.2

        if any(p in title for p in pos): score += 5 * w
        if any(n in title for n in neg): score -= 7 * w

    return float(np.clip(score, -15, 15))

# =========================================================
# 3. KI ANALYSE ENGINE (11 FAKTOREN)
# =========================================================

def get_ki_verdict(symbol: str):
    info = get_ticker_info(symbol)
    hist = get_history(symbol, "1y")

    if len(hist) < 200:
        return "➡️ HOLD", "Zu wenig historische Daten.", 0, 0, 50

    close = hist['Close']
    curr_p = float(close.iloc[-1])

    score = 50
    reasons = []

    # --- 1. Trend (SMA + Strength)
    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]
    trend_strength = (sma50 - sma200) / sma200
    reversal_p = sma200

    if trend_strength > 0.03:
        score += 15
        reasons.append("📈 Starker Aufwärtstrend (SMA50 > SMA200).")
    elif curr_p < sma200:
        score -= 15
        reasons.append("📉 Unter langfristigem Trend (SMA200).")

    # --- 2. RSI
    rsi = calculate_rsi(close)
    if rsi > 70:
        score -= 10
        reasons.append(f"🔥 RSI überkauft ({rsi:.1f}).")
    elif rsi < 30:
        score += 10
        reasons.append(f"🧊 RSI überverkauft ({rsi:.1f}).")

    # --- 3. Volatilität (ATR)
    atr = calculate_atr(hist)
    vola_ratio = (atr / curr_p) * 100
    if vola_ratio > 4:
        score -= 5
        reasons.append(f"⚠️ Hohe Volatilität ({vola_ratio:.1f}%).")

    # --- 4/5. Fundamentale Stabilität
    margin = info.get("operatingMargins", 0) or 0
    if margin > 0.15:
        score += 10
        reasons.append(f"💰 Hohe operative Marge ({margin*100:.1f}%).")

    cash = info.get("totalCash", 0) or 0
    debt = info.get("totalDebt", 0) or 0
    if cash > debt:
        score += 5
        reasons.append("🏦 Net-Cash Bilanz.")

    # --- 6. Bewertung
    pe = info.get("forwardPE")
    ps = info.get("priceToSalesTrailing12Months")

    if pe and 0 < pe < 18:
        score += 10
        reasons.append(f"💎 Attraktives KGV ({pe:.1f}).")
    elif (not pe or pe <= 0) and ps and ps < 3:
        score += 10
        reasons.append(f"🚀 Attraktives KUV ({ps:.1f}).")

    # --- 7. Volumen
    vol_avg = hist['Volume'].tail(20).mean()
    if hist['Volume'].iloc[-1] > vol_avg * 1.3:
        score += 10
        reasons.append("📊 Starkes Handelsvolumen.")

    # --- 8. News
    score += analyze_news_sentiment(yf.Ticker(symbol).news)

    # --- 9. Relative Stärke
    perf_1y = (curr_p / close.iloc[0]) - 1
    if perf_1y > 0.2:
        score += 10
        reasons.append("🏆 Klare 1Y-Outperformance.")

    # --- 10. MACD
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()

    if macd.iloc[-1] > signal.iloc[-1]:
        score += 5
        reasons.append("🌊 MACD bullish.")

    # --- 11. PEG
    peg = info.get("pegRatio")
    if peg and 0.5 < peg < 1.5:
        score += 5
        reasons.append(f"⚖️ PEG optimal ({peg:.2f}).")

    # --- Score Clamp
    score = int(np.clip(score, 0, 100))

    verdict = (
        "💎 STRONG BUY" if score >= 80 else
        "🚀 BUY" if score >= 60 else
        "➡️ HOLD" if score >= 35 else
        "🛑 SELL"
    )

    return verdict, "\n".join(reasons), vola_ratio, reversal_p, score

# =========================================================
# STRATEGISCHER DEEP DIVE – 11-FAKTOR-MATRIX (ORIGINAL)
# =========================================================

st.divider()
st.subheader("🔍 Strategischer Deep Dive: Die 11-Faktor-Matrix")

# Faktor 1: Markt-Phasierung
st.markdown(
    "### 1. Markt-Phasierung (Institutionelles Sentiment) "
    "<span class='weight-badge'>±15</span>",
    unsafe_allow_html=True
)
st.markdown(f"""
Die Position des Kurses zum **SMA 200** ({reversal_p:.2f} $) ist der wichtigste Indikator für den langfristigen Trend. 
* **Bullish:** Liegt der Kurs über dem SMA 200, gilt das Asset als 'gesund'. Große Fonds und Institutionen nutzen diese Linie oft als Kaufzone.
* **Trend-Bestätigung:** Ein Kurs über dem SMA 50 signalisiert kurzfristiges Momentum innerhalb des langfristigen Aufwärtstrends.
""")

# Faktor 2: Dynamik (RSI)
st.markdown(
    "### 2. Relative Stärke Index (RSI 14) "
    "<span class='weight-badge'>±10</span>",
    unsafe_allow_html=True
)
st.markdown("""
Der RSI ist ein Oszillator, der die Geschwindigkeit und Veränderung von Kursbewegungen misst. 
* **Überkauft (>70):** Die Gier im Markt ist hoch, eine Korrektur ist statistisch wahrscheinlich.
* **Überverkauft (<30):** Extreme Panik herrscht vor – oft ein antizyklischer Einstiegspunkt.
""")

# Faktor 3: Volatilitäts-Check (ATR)
st.markdown(
    "### 3. Volatilitäts-Profil (ATR-Ratio) "
    "<span class='weight-badge'>-5</span>",
    unsafe_allow_html=True
)
st.markdown(f"""
Die **Average True Range (ATR)** misst das Marktrauschen. 
Dein aktueller Wert liegt bei **{current_vola:.2f}%**. 
Ein Wert über 4% deutet auf spekulatives Verhalten hin. 
Hohe Volatilität erhöht die Wahrscheinlichkeit, unglücklich aus einem Stop-Loss geworfen zu werden.
""")

# Faktor 4 & 5: Bilanz-Qualität
st.markdown(
    "### 4. & 5. Fundamentale Resilienz (Marge & Cash) "
    "<span class='weight-badge'>+15</span>",
    unsafe_allow_html=True
)
st.markdown("""
Hier prüft die KI die 'Burganlage' (Moat) des Unternehmens:
* **Operating Margin > 15%:** Beweist Preismacht. Das Unternehmen kann steigende Kosten an Kunden weitergeben.
* **Net-Cash:** Ein Unternehmen, das mehr Cash als Schulden hat, ist immun gegen steigende Zinsen und kann in Krisen Konkurrenten aufkaufen.
""")

# Faktor 6: Bewertung (Multiples)
st.markdown(
    "### 6. Value-Check (KGV/KUV) "
    "<span class='weight-badge'>+10</span>",
    unsafe_allow_html=True
)
st.markdown("""
Wachstum darf nicht um jeden Preis gekauft werden. 
* Ein **KGV < 18** gilt historisch als attraktiv für etablierte Firmen. 
* Bei jungen Tech-Werten ohne Gewinn weicht die KI auf das **KUV (< 3)** aus, um eine Überbewertung (Hype) zu vermeiden.
""")

# Faktor 7: Smart-Money Flow
st.markdown(
    "### 7. Volumen-Analyse "
    "<span class='weight-badge'>+10</span>",
    unsafe_allow_html=True
)
st.markdown("""
'Volume precedes price' (Volumen geht dem Preis voraus). 
Steigt der Kurs bei einem Volumen, das 30% über dem Schnitt liegt, 
deutet dies auf **Akkumulation** durch institutionelle Anleger hin. 
Es ist kein Zufall, sondern gezieltes Kaufen.
""")

# Faktor 8: NLP Sentiment-Score
st.markdown(
    "### 8. Mediales Echo (Sentiment) "
    "<span class='weight-badge'>±20</span>",
    unsafe_allow_html=True
)
st.markdown("""
Die KI scannt die letzten 5 Schlagzeilen. 
Wir nutzen eine Zeitgewichtung: News der letzten 24h zählen voll, ältere News weniger. 
Dies fängt plötzliche Gewinnwarnungen oder Upgrades von Analysten 
(Goldman Sachs, Morgan Stanley etc.) sofort ab.
""")

# Faktor 9: Relative Stärke (Sektor)
st.markdown(
    "### 9. Outperformance-Check "
    "<span class='weight-badge'>+10</span>",
    unsafe_allow_html=True
)
st.markdown("""
Ein Bonus wird nur vergeben, wenn die Aktie eine Performance von >20% im letzten Jahr zeigt. 
Wir suchen die 'Alpha-Tiere' eines Sektors, nicht die Nachzügler.
""")

# Faktor 10: Momentum-Bestätigung (MACD)
st.markdown(
    "### 10. MACD Trend-Konvergenz "
    "<span class='weight-badge'>+5</span>",
    unsafe_allow_html=True
)
st.markdown("""
Der **Moving Average Convergence Divergence** zeigt das Zusammenspiel zweier exponentieller Durchschnitte. 
Ein bullishes Crossover signalisiert, dass das Kaufinteresse gerade massiv zunimmt 
und ein neuer Aufwärtstrend geboren wird.
""")

# Faktor 11: Wachstums-Preis-Effizienz (PEG)
st.markdown(
    "### 11. PEG-Ratio (Growth at a Reasonable Price) "
    "<span class='weight-badge'>+5</span>",
    unsafe_allow_html=True
)
st.markdown("""
Das **PEG-Ratio** ist die Königsklasse der Bewertung. 
Es setzt das KGV ins Verhältnis zum erwarteten Gewinnwachstum. 
Ein PEG von **1.0** bedeutet: Die Aktie ist exakt so teuer, wie sie wächst. 
Ein Wert darunter ist ein massives Kaufsignal (Unterbewertung trotz Wachstum).
""")