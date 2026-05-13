from flask import Flask, render_template
from threading import Thread
import yfinance as yf
import pandas as pd
import requests
import time
import sqlite3
from datetime import datetime
import threading

# ====================================
# SQLITE DATABASE
# ====================================

conn = sqlite3.connect(
    "signals.db",
    check_same_thread=False,
    timeout=30
)

cursor = conn.cursor()
db_lock = threading.Lock()
# ====================================
# CREATE TABLE
# ====================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS signals (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    stock TEXT,

    signal_type TEXT,

    price REAL,

    rsi REAL,

    score REAL,

    timeframe TEXT,

    created_at TEXT

)
""")

conn.commit()
# ====================================
# SAVE SIGNAL
# ====================================
def save_signal(
    stock,
    signal_type,
    price,
    rsi,
    score,
    timeframe
):

    with db_lock:

        cursor.execute(
            """
            INSERT INTO signals (

                stock,
                signal_type,
                price,
                rsi,
                score,
                timeframe,
                created_at

            )

            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,

            (
                stock,
                signal_type,
                price,
                rsi,
                score,
                timeframe,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )

        conn.commit()

# ====================================
# FLASK APP
# ====================================

app = Flask(__name__)

# ===========================================
# SCANNER STATUS
# ===========================================

scanner_status = {
    "running": True,
    "last_scan": None,
    "stocks_scanned": 0,
    "active_signals": 0
}

# ===========================================
# HOME PAGE
# ===========================================

@app.route("/")
def home():

    return render_template(
        "dashboard.html"
    )

# ===========================================
# LIVE ALERTS PAGE
# ===========================================

@app.route("/live-alerts")
def live_alerts():

    cursor.execute(
        """
        SELECT * FROM signals
        ORDER BY id DESC
        LIMIT 50
        """
    )

    alerts = cursor.fetchall()

    return render_template(
        "live_alerts.html",
        alerts=alerts
    )

# ===========================================
# OPEN SIGNALS PAGE
# ===========================================

@app.route("/open-signals")
def open_signals():

    cursor.execute(
        """
        SELECT * FROM signals
        WHERE signal_type IN ('BUY', 'ADD')
        ORDER BY id DESC
        """
    )

    data = cursor.fetchall()

    return render_template(
        "open_signals.html",
        data=data
    )

# ===========================================
# SIGNAL HISTORY PAGE
# ===========================================

@app.route("/signal-history")
def signal_history():

    cursor.execute(
        """
        SELECT * FROM signals
        ORDER BY id DESC
        LIMIT 500
        """
    )

    history = cursor.fetchall()

    return render_template(
        "signal_history.html",
        history=history
    )

# ===========================================
# STATUS PAGE
# ===========================================

@app.route("/status")
def status():

    return render_template(
        "status.html",
        status=scanner_status
    )

# ====================================
# TELEGRAM SETTINGS
# ====================================

BOT_TOKEN = "8657217148:AAHicOlpVqUqmu4olHwGnnFvhkQqNvxGPKs"
CHAT_ID = "1190014186"

# ====================================
# NIFTY STOCKS
# ====================================
from nifty500 import stocks
# ====================================
# ALERT MEMORY
# ====================================

sent_alerts = set()

# ====================================
# TELEGRAM FUNCTION
# ====================================

def send_telegram(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }

    requests.post(url, json=payload)

# ====================================
# SAVE ALERT
# ====================================

def save_alert(stock, signal, price, rsi):

    cursor.execute("""
    INSERT INTO alerts(stock, signal, price, rsi, time)
    VALUES (?, ?, ?, ?, ?)
    """, (
        stock,
        signal,
        price,
        rsi,
        str(datetime.now())
    ))

    conn.commit()

# ====================================
# MARKET HOURS FILTER
# ====================================

def market_open():

    now = datetime.now()

    current_time = now.strftime("%H:%M")

    return current_time >= "09:15" and current_time <= "15:30"

# ====================================
# SCANNER FUNCTION
# ====================================

def scan_market():

    print(f"\nScanning Started : {datetime.now()}")
    
    scanner_status["last_scan"] = datetime.now()
    
    scanner_status["stocks_scanned"] = len(stocks)

    if not market_open():

        print("Market Closed ❌")

        return

    momentum_rankings = []

    for stock in stocks:

        try:

            # ====================================
            # INTRADAY DATA
            # ====================================

            df = yf.download(
                stock,
                period="60d",
                interval="15m",
                progress=False,
                auto_adjust=True
            )

            if df.empty or len(df) < 100:
                continue

            # ====================================
            # EMA
            # ====================================

            df["EMA10"] = df["Close"].ewm(span=10).mean()

            df["EMA50"] = df["Close"].ewm(span=50).mean()

            # ====================================
            # RSI
            # ====================================

            delta = df["Close"].diff()

            gain = delta.clip(lower=0)

            loss = -delta.clip(upper=0)

            avg_gain = gain.rolling(14).mean()

            avg_loss = loss.rolling(14).mean()

            rs = avg_gain / avg_loss

            df["RSI"] = 100 - (100 / (1 + rs))

            # ====================================
            # VOLUME
            # ====================================

            df["VOL_MA"] = df["Volume"].rolling(20).mean()

            # ====================================
            # ATR
            # ====================================

            df["H-L"] = df["High"] - df["Low"]

            df["H-PC"] = abs(df["High"] - df["Close"].shift(1))

            df["L-PC"] = abs(df["Low"] - df["Close"].shift(1))

            df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1)

            df["ATR"] = df["TR"].rolling(14).mean()
            
            # ====================================
            # ATR STOP
            # ====================================

            

            # ====================================
            # DAILY TREND
            # ====================================

            daily = yf.download(
                stock,
                period="1y",
                interval="1d",
                progress=False,
                auto_adjust=True
            )

            daily["EMA10"] = daily["Close"].ewm(span=10).mean()

            daily["EMA50"] = daily["Close"].ewm(span=50).mean()

            daily_close = float(daily["Close"].iloc[-1])

            daily_ema10 = float(daily["EMA10"].iloc[-1])

            daily_ema50 = float(daily["EMA50"].iloc[-1])

            daily_bullish = (
                daily_close > daily_ema10
                and daily_ema10 > daily_ema50
            )

            # ====================================
            # WEEKLY TREND
            # ====================================

            weekly = yf.download(
                stock,
                period="5y",
                interval="1wk",
                progress=False,
                auto_adjust=True
            )

            weekly["EMA10"] = weekly["Close"].ewm(span=10).mean()

            weekly["EMA50"] = weekly["Close"].ewm(span=50).mean()

            weekly_close = float(weekly["Close"].iloc[-1])

            weekly_ema10 = float(weekly["EMA10"].iloc[-1])

            weekly_ema50 = float(weekly["EMA50"].iloc[-1])

            weekly_bullish = (
                weekly_close > weekly_ema10
                and weekly_ema10 > weekly_ema50
            )
            weekly_high = float(
                weekly["High"]
                .rolling(20)
                .max()
                .iloc[-1]
            )
            # ====================================
            # LATEST VALUES
            # ====================================

            latest = df.iloc[-1]

            close = float(latest["Close"])

            ema10 = float(latest["EMA10"])

            ema50 = float(latest["EMA50"])

            rsi = float(latest["RSI"])

            volume = float(latest["Volume"])

            vol_ma = float(latest["VOL_MA"])

            volume_confirmation = volume > vol_ma

            atr = float(latest["ATR"])

            # ====================================
            # BUY SIGNAL
            # ====================================

            buy_signal = (
                close > ema10
                and ema10 > ema50
                and rsi > 60
                and volume > vol_ma
                and daily_bullish
                and weekly_bullish
            )           
            # ====================================
            # MOMENTUM SCORE
            # ====================================

            score = 0

            if close > ema10:
                score += 20

            if ema10 > ema50:
                score += 20

            if rsi > 60:
                score += 15

            if rsi > 70:
                score += 10

            if volume > vol_ma:
                score += 15

            if daily_bullish:
                score += 10

            if weekly_bullish:
                score += 10

            momentum_rankings.append({
                "stock": stock,
                "score": score,
                "price": close,
                "rsi": rsi
            })

            # ====================================
            # ADD SIGNAL
            # ====================================

            add_signal = (

                close > weekly_high
                and close > ema10
                and rsi > 60
                and volume_confirmation

            )

            # ====================================
            # SELL SIGNAL
            # ====================================

            sell_signal = (

                close < ema10
                and ema10 < ema50
                and rsi < 45
                and volume_confirmation

            )

            # ====================================
            # BUY ALERT
            # ====================================

            if buy_signal and f"{stock}_BUY" not in sent_alerts:

                message = f"""
🚀 BUY SIGNAL

Stock : {stock}

Price : {round(close, 2)}

RSI : {round(rsi, 2)}

Score : {score}

Time : {datetime.now()}
"""

                print(message)

                send_telegram(message)

                save_signal(
                    stock,
                    "BUY",
                    close,
                    rsi,
                    score,
                    "15m"
                )

                sent_alerts.add(f"{stock}_BUY")

            # ====================================
            # ADD ALERT
            # ====================================

            if add_signal:

                message = f"""
➕ ADD SIGNAL

Stock : {stock}

Price : {round(close, 2)}

RSI : {round(rsi, 2)}

Score : {score}

Time : {datetime.now()}
"""

                print(message)

                send_telegram(message)

                save_signal(
                    stock,
                    "ADD",
                    close,
                    rsi,
                    score,
                    "15m"
                )

            # ====================================
            # SELL ALERT
            # ====================================

            if sell_signal and f"{stock}_SELL" not in sent_alerts:

                message = f"""
🔻 SELL SIGNAL

Stock : {stock}

Price : {round(close, 2)}

RSI : {round(rsi, 2)}

Score : {score}

Time : {datetime.now()}
"""

                print(message)

                send_telegram(message)

                save_signal(
                    stock,
                    "SELL",
                    close,
                    rsi,
                    score,
                    "15m"
                )

                sent_alerts.add(f"{stock}_SELL")

        except Exception as e:

            print(stock, e) 
    # ====================================
    # FILTER STRONG MOMENTUM STOCKS
    # ====================================
    
    strong_stocks = [
        stock for stock in momentum_rankings
        if stock["score"] >= 50
    ]
    
    # ====================================
    # TOP MOMENTUM RANKING
    # ====================================
    
    top_stocks = sorted(
        strong_stocks,
        key=lambda x: x["score"],
        reverse=True
    )[:10]    
    # ====================================
    # CREATE MESSAGE
    # ====================================
    
    ranking_message = "🔥 TOP MOMENTUM STOCKS 🔥\n\n"
    
    # ====================================
    # CHECK STOCKS FOUND
    # ====================================
    
    if len(top_stocks) == 0:
    
        ranking_message += "No strong momentum stocks found."
    
    else:
    
        for i, stock_data in enumerate(top_stocks, start=1):
    
            ranking_message += (
                f"{i}. "
                f"{stock_data['stock']} "
                f"| Score: {stock_data['score']} "
                f"| RSI: {round(stock_data['rsi'], 2)}\n"
            )
    
    # ====================================
    # PRINT + TELEGRAM
    # ====================================
    
    print(ranking_message)
    
    send_telegram(ranking_message)
# ====================================
# RUN SCANNER LOOP
# ====================================

def run_scanner():

    while True:

        scan_market()

        print("Next Scan After 1 Hour ⏳")

        time.sleep(3600)

# ====================================
# START THREAD
# ====================================

Thread(
    target=run_scanner,
    daemon=True
).start()

# ====================================
# RUN FLASK
# ====================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=10000
    )
