sent_alerts = set()
# ====================================
# NP MOMENTUM SCANNER PRO
# DAILY + WEEKLY VERSION
# ====================================

import yfinance as yf
import pandas as pd
import requests
import time
import ta
import sqlite3

from datetime import datetime
from flask import Flask
from threading import Thread

# ====================================
# FLASK APP
# ====================================

app = Flask(__name__)

@app.route("/")
def home():
    return "NP Momentum Scanner Running 🚀"

# ====================================
# TELEGRAM CONFIG
# ====================================

BOT_TOKEN = "8657217148:AAHicOlpVqUqmu4olHwGnnFvhkQqNvxGPKs"

CHAT_ID = "1190014186"

# ====================================
# STOCK LIST
# ====================================

stocks = [

    "HBLENGINE.NS",
    "NEULANDLAB.NS",
    "POWERGRID.NS",
    "POWERINDIA.NS",
    "SYRMA.NS",
    "TATAPOWER.NS",
    "BAJAJ-AUTO.NS",
    "TIPSMUSIC.NS",
    "KSB.NS",
    "OFSS.NS",
    "APARINDS.NS",
    "ESABINDIA.NS",
    "KRISHANA.NS",
    "NH.NS",
    "SIEMENS.NS",
    "SBCL.NS",
    "TIMKEN.NS",
    "TITAN.NS",
    "DATAPATTNS.NS",
    "SOLARINDS.NS",
    "DMART.NS",
    "NESCO.NS",
    "NESTLEIND.NS",
    "KOVAI.NS",
    "CCL.NS",
    "TDPOWERSYS.NS",
    "GVT&D.NS"

]

# ====================================
# SETTINGS
# ====================================

rsiLen = 14
rsiLevel = 65

emaFast = 5
emaSlow = 50

volPeriod = 10

atrLen = 14
atrMult = 1.2

addPct = 1.0
dcUpperLen = 20

# ====================================
# DATABASE
# ====================================

conn = sqlite3.connect(
    "signals.db",
    check_same_thread=False
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS signals (
    stock TEXT,
    signal TEXT,
    signal_time TEXT
)
""")

conn.commit()

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
# DUPLICATE CHECK
# ====================================

def already_sent(stock, signal):

    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
    SELECT * FROM signals
    WHERE stock=? AND signal=? AND signal_time LIKE ?
    """, (
        stock,
        signal,
        f"{today}%"
    ))

    return cursor.fetchone()

# ====================================
# SAVE SIGNAL
# ====================================

def save_signal(stock, signal):

    cursor.execute("""
    INSERT INTO signals VALUES (?, ?, ?)
    """, (
        stock,
        signal,
        str(datetime.now())
    ))

    conn.commit()

# ====================================
# SCAN TIME FILTER
# RUN AFTER MARKET CLOSE
# ====================================

def scan_time_ok():

    now = datetime.now()

    return (
        now.hour == 16
    )

# ====================================
# SCANNER FUNCTION
# ====================================

def scan_market():

    print(f"\nScanning Started : {datetime.now()}")

    for stock in stocks:

        try:

            df = yf.download(
                stock,
                period="6mo",
                interval="1d",
                progress=False,
                auto_adjust=True
            )

            if df.empty or len(df) < 50:
                continue

            # =========================
            # EMA
            # =========================

            df["EMA20"] = ta.trend.ema_indicator(df["Close"], window=20)
            df["EMA50"] = ta.trend.ema_indicator(df["Close"], window=50)

            # =========================
            # RSI
            # =========================

            df["RSI"] = ta.momentum.rsi(df["Close"], window=14)

            latest = df.iloc[-1]

            close = float(latest["Close"])
            ema20 = float(latest["EMA20"])
            ema50 = float(latest["EMA50"])
            rsi = float(latest["RSI"])

            # =========================
            # BUY CONDITION
            # =========================

            buy_signal = (
                close > ema20
                and ema20 > ema50
                and rsi > 60
            )

            # =========================
            # SELL CONDITION
            # =========================

            sell_signal = (
                close < ema20
                and ema20 < ema50
                and rsi < 40
            )

            # =========================
            # BUY ALERT
            # =========================

            if buy_signal and stock not in sent_alerts:

                message = f"""
🚀 BUY SIGNAL

Stock : {stock}

Price : {round(close, 2)}

RSI : {round(rsi, 2)}

Time : {datetime.now()}
"""

                print(message)

                send_telegram(message)

                sent_alerts.add(stock)

            # =========================
            # SELL ALERT
            # =========================

            if sell_signal:

                message = f"""
🔻 SELL SIGNAL

Stock : {stock}

Price : {round(close, 2)}

RSI : {round(rsi, 2)}

Time : {datetime.now()}
"""

                print(message)

                send_telegram(message)

        except Exception as e:

            print(stock, e)

            # ====================================
            # MOMENTUM SCORE
            # ====================================

            score = 0

            if is_stage2:
                score += 20

            if is_rs_positive:
                score += 20

            if c_ema5:
                score += 15

            if c_ema50:
                score += 15

            if c_rsi:
                score += 15

            if c_vol:
                score += 15

            # ====================================
            # BUY ALERT
            # ====================================

            if (
                buy_signal
                and not already_sent(stock, "BUY")
            ):

                message = f"""
🚀 BUY SIGNAL

Stock : {stock}

Price : {round(close, 2)}

RSI : {round(rsi, 2)}

RS Score : {round(rs_ratio, 2)}

Momentum Score : {score}/100

Stage : 2

Time : {datetime.now()}
"""

                print(message)

                send_telegram(message)

                save_signal(stock, "BUY")

            # ====================================
            # ADD ALERT
            # ====================================

            if (
                add_signal
                and not already_sent(stock, "ADD")
            ):

                message = f"""
➕ ADD SIGNAL

Stock : {stock}

Price : {round(close, 2)}

Donchian Breakout Confirmed

Time : {datetime.now()}
"""

                print(message)

                send_telegram(message)

                save_signal(stock, "ADD")

            # ====================================
            # SELL ALERT
            # ====================================

            if (
                sell_signal
                and not already_sent(stock, "SELL")
            ):

                message = f"""
🔻 SELL SIGNAL

Stock : {stock}

Price : {round(close, 2)}

Weakness Detected

Time : {datetime.now()}
"""

                print(message)

                send_telegram(message)

                save_signal(stock, "SELL")

        except Exception as e:

            print(stock, e)

# ====================================
# BACKGROUND LOOP
# ====================================

def run_scanner():

    while True:

        scan_market()

        # CHECK EVERY HOUR
        time.sleep(3600)

# ====================================
# START THREAD
# ====================================

Thread(target=run_scanner).start()

# ====================================
# RUN FLASK APP
# ====================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=10000
    )
