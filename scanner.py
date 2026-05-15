import pytz
import datetime
from flask import Flask, render_template
from threading import Thread
import yfinance as yf
import pandas as pd
import requests
import time
import sqlite3
import threading
import socket
from nsepython import *
import concurrent.futures


IST = pytz.timezone("Asia/Kolkata")

socket.setdefaulttimeout(20)

print("NEW CODE VERSION LOADED 🚀")

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
                datetime.datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
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
    with db_lock:
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
    with db_lock:
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
    with db_lock:
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

    try:

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        payload = {
            "chat_id": CHAT_ID,
            "text": message
        }

        requests.post(
            url,
            json=payload,
            timeout=10
        )

    except Exception as e:

        print("Telegram Error:", e)   



# ====================================
# NSE MARKET TIME
# ====================================

def market_open():

    return True

# ====================================
# SCANNER FUNCTION
# ====================================

def scan_market():

    print("Inside scan_market() ✅")

    print(f"Total Stocks: {len(stocks)}")

    print("Checking market hours...")

    print("Scanner Time Started ✅")

    scanner_status["last_scan"] = datetime.datetime.now(IST).strftime("%d-%m-%Y %I:%M:%S %p")

    scanner_status["stocks_scanned"] = len(stocks)

    print("Market Timing Disabled ✅")

    momentum_rankings = []

    # ====================================
    # STOCK LOOP
    # ====================================

    for stock in stocks:
    
        try:
    
            print(f"Downloading {stock}")
    
            ticker = yf.Ticker(stock)
    
            df = ticker.history(
                interval="90m",
                period="60d",
                auto_adjust=True
            )
    
            if df.empty:
                continue
    
            # EMA
            df["EMA10"] = df["Close"].ewm(span=10).mean()
    
            df["EMA20"] = df["Close"].ewm(span=20).mean()

            df["EMA50"] = df["Close"].ewm(span=50).mean()

            print(f"{stock} indicators calculated ✅")
    
            # RSI
            delta = df["Close"].diff()
    
            gain = delta.clip(lower=0)
    
            loss = -delta.clip(upper=0)
    
            avg_gain = gain.rolling(14).mean()
    
            avg_loss = loss.rolling(14).mean()
    
            rs = avg_gain / avg_loss
    
            df["RSI"] = 100 - (100 / (1 + rs))
    
            print(f"{stock} SUCCESS ✅")
    
                      
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
            #==============================
            latest = df.iloc[-1]
            
            close = float(latest["Close"])
            
            ema10 = float(latest["EMA10"])
            
            ema50 = float(latest["EMA50"])
            
            # ====================================
            # WEEKLY TREND
            # ====================================

            weekly = yf.download(
                stock,
                interval="1wk",
                period="2y",
                progress=False,
                auto_adjust=True
            )
            
            if weekly.empty or len(weekly) < 20:
            
                print(f"{stock} weekly data failed ❌")
            
                continue
            
            weekly["EMA10"] = weekly["Close"].ewm(span=10).mean()
            
            weekly["EMA20"] = weekly["Close"].ewm(span=20).mean()
            
            weekly_close = float(weekly["Close"].iloc[-1])

            weekly_ema10 = float(weekly["EMA10"].iloc[-1])

            weekly_ema20 = float(weekly["EMA20"].iloc[-1])

            weekly_bullish = (
                weekly_close > weekly_ema10
                and weekly_ema10 > weekly_ema20
            )
            weekly_high = float(
                weekly["High"]
                .rolling(20)
                .max()
                .shift(1)
                .iloc[-1]
            )

            if weekly.empty or len(weekly) < 20:
            
                print(f"{stock} weekly data failed ❌")
            
                continue
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

            daily_bullish = (

                close > ema10
                and ema10 > ema50
            )
            # ====================================
            # ATR STOP LOSS
            # ====================================
            
            stop_loss = ema10 - (atr * 1.2)
            
            # ====================================
            # BUY SIGNAL
            # ====================================

            buy_signal = close > ema10
            
            print(
                stock,
                "Close:", close,
                "EMA10:", ema10,
                "EMA50:", ema50,
                "RSI:", rsi,
                "BUY:", buy_signal
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
            
                close > ema10
                and rsi > 65
                and volume > vol_ma
            )
            
            # ====================================
            # SELL SIGNAL
            # ====================================
            
            sell_signal = (
            
                close < stop_loss
                and rsi < 45
            
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

Time : {datetime.datetime.now(IST).strftime(
        "%Y-%m-%d %H:%M:%S")}
"""

                print(message)

                send_telegram(message)

                save_signal(
                    stock,
                    "BUY",
                    close,
                    rsi,
                    score,
                    "90m"
                )

                sent_alerts.add(f"{stock}_BUY")

            # ====================================
            # ADD ALERT
            # ====================================

            if add_signal and f"{stock}_ADD" not in sent_alerts:

                message = f"""
➕ ADD SIGNAL

Stock : {stock}

Price : {round(close, 2)}

RSI : {round(rsi, 2)}

Score : {score}

Time : {datetime.datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")}
"""

                print(message)

                send_telegram(message)

                save_signal(
                    stock,
                    "ADD",
                    close,
                    rsi,
                    score,
                    "90m"
                )

                sent_alerts.add(f"{stock}_ADD")

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

Time : {datetime.datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")}
"""

                print(message)

                send_telegram(message)

                save_signal(
                    stock,
                    "SELL",
                    close,
                    rsi,
                    score,
                    "90m"
                )

                sent_alerts.add(f"{stock}_SELL")
                
        except Exception as e:

            print(f"{stock} failed ❌ {e}")

            continue
    
    # ====================================
    # FILTER STRONG MOMENTUM STOCKS
    # ====================================
    
    strong_stocks = [
        stock for stock in momentum_rankings
        if stock["score"] >= 35
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
    
    if len(top_stocks) > 0:
    
        print(ranking_message)
    
        send_telegram(ranking_message)
    
    else:
    
        print("No strong momentum stocks found.")
# ====================================
# RUN SCANNER LOOP
# ====================================

def run_scanner():

    while True:

        try:

            print("SCANNER STARTED 🚀")

            scan_market()

            print("SCAN COMPLETED ✅")

        except Exception as e:

            print(f"SCANNER ERROR: {e}")

        print("Next Scan After 15 Min ⏳")

        time.sleep(900)


# ====================================
# RUN FLASK
# ====================================

if __name__ == "__main__":

    scanner_thread = threading.Thread(
        target=run_scanner,
        daemon=True
    )

    scanner_thread.start()

    app.run(
        host="0.0.0.0",
        port=10000,
        debug=False
    )
