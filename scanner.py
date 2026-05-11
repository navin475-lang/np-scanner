sent_alerts = set()
import yfinance as yf
import pandas as pd
import requests
import schedule
import time
from datetime import datetime

from flask import Flask
from threading import Thread

app = Flask(__name__)

# =========================
# HOME ROUTE
# =========================

@app.route("/")
def home():
    return "NP Scanner Running 🚀"

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
# SCANNER FUNCTION
# ====================================

def scan_market():

    print(f"\nScanning Started : {datetime.now()}")

    for stock in stocks:

        try:

            df = yf.download(
                stock,
                period="60d",
                interval="15m",
                progress=False
            )

            # =========================
            # EMPTY DATA CHECK
            # =========================

            if df.empty:
                continue

            # =========================
            # INDICATORS
            # =========================

            df["EMA20"] = df["Close"].ewm(span=20).mean()

            df["EMA50"] = df["Close"].ewm(span=50).mean()

            # =========================
            # LATEST VALUES
            # =========================

            close = float(df["Close"].iloc[-1])

            ema20 = float(df["EMA20"].iloc[-1])

            ema50 = float(df["EMA50"].iloc[-1])

            # =========================
            # BUY CONDITION
            # =========================

            buy_signal = True

            # Example real condition:
            # buy_signal = (
            #     close > ema20
            #     and ema20 > ema50
            # )

            # =========================
            # SELL CONDITION
            # =========================

            sell_signal = (
                close < ema20
                and ema20 < ema50
            )

            # =========================
            # BUY ALERT
            # =========================

            if buy_signal and stock not in sent_alerts:

                message = f"""
🚀 BUY SIGNAL

Stock : {stock}

Price : {round(close, 2)}

EMA20 : {round(ema20, 2)}

EMA50 : {round(ema50, 2)}

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

EMA20 : {round(ema20, 2)}

EMA50 : {round(ema50, 2)}

Time : {datetime.now()}
"""

                print(message)

                send_telegram(message)

        except Exception as e:

            print(stock, e)
# ====================================
# RUN FIRST TIME
# ====================================

scan_market()

# ====================================
# AUTO SCAN EVERY 15 MINUTES
# ====================================

schedule.every(15).minutes.do(scan_market)

print("Scanner Running 🚀")

def run_scanner():

    while True:

        scan_market()

        time.sleep(900)

Thread(target=run_scanner).start()

if __name__ == "__main__":

    app.run(host="0.0.0.0", port=10000)
