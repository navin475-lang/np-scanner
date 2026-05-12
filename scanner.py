sent_alerts = set()
# ====================================
# NP MOMENTUM SCANNER PRO
# DAILY + WEEKLY VERSION
# ====================================

import yfinance as yf
import pandas as pd
import requests
import schedule
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

            # =========================
            # DOWNLOAD DATA
            # =========================

            df = yf.download(
                stock,
                period="6mo",
                interval="1d",
                progress=False,
                auto_adjust=True
            )

            if df.empty or len(df) < 100:
                continue

            # =========================
            # EMA
            # =========================

            df["EMA20"] = df["Close"].ewm(span=20).mean()
            df["EMA50"] = df["Close"].ewm(span=50).mean()

            # =========================
            # RSI
            # =========================

            delta = df["Close"].diff()

            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)

            avg_gain = gain.rolling(14).mean()
            avg_loss = loss.rolling(14).mean()

            rs = avg_gain / avg_loss

            df["RSI"] = 100 - (100 / (1 + rs))

            # =========================
            # VOLUME
            # =========================

            df["VOL_MA"] = df["Volume"].rolling(20).mean()

            # =========================
            # LATEST VALUES
            # =========================

            latest = df.iloc[-1]

            close = float(latest["Close"])
            ema20 = float(latest["EMA20"])
            ema50 = float(latest["EMA50"])
            rsi = float(latest["RSI"])
            volume = float(latest["Volume"])
            vol_ma = float(latest["VOL_MA"])

            # =========================
            # BUY CONDITION
            # =========================

            buy_signal = (
                close > ema20
                and ema20 > ema50
                and rsi > 60
                and volume > vol_ma
            )

            # =========================
            # SELL CONDITION
            # =========================

            sell_signal = (
                close < ema20
                and ema20 < ema50
                and rsi < 45
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
