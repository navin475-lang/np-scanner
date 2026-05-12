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

def scan_market():

    print(f"\nScanning Started : {datetime.now()}")

    for stock in stocks:

        try:

            df = yf.download(
                stock,
                period="60d",
                interval="15m",
                progress=False,
                auto_adjust=True
            )

            if df.empty or len(df) < 60:
                continue

            # ====================================
            # CLEAN DATA
            # ====================================

            df = df.dropna()

            # ====================================
            # INDICATORS
            # ====================================

            df["EMA5"] = ta.trend.ema_indicator(
                df["Close"],
                window=emaFast
            )

            df["EMA50"] = ta.trend.ema_indicator(
                df["Close"],
                window=emaSlow
            )

            df["RSI"] = ta.momentum.rsi(
                df["Close"],
                window=rsiLen
            )

            df["VOL_MA"] = df["Volume"].rolling(volPeriod).mean()

            df["ATR"] = ta.volatility.average_true_range(
                df["High"],
                df["Low"],
                df["Close"],
                window=atrLen
            )

            df["DC_UPPER"] = (
                df["High"]
                .shift(1)
                .rolling(dcUpperLen)
                .max()
            )

            # ====================================
            # LATEST VALUES
            # ====================================

            latest = df.iloc[-1]

            close = float(latest["Close"])

            ema5 = float(latest["EMA5"])
            ema50 = float(latest["EMA50"])

            rsi = float(latest["RSI"])

            volume = float(latest["Volume"])
            vol_ma = float(latest["VOL_MA"])

            atr = float(latest["ATR"])

            dc_upper = float(latest["DC_UPPER"])

            high = float(latest["High"])
            low = float(latest["Low"])
            open_price = float(latest["Open"])

            # ====================================
            # UPPER WICK %
            # ====================================

            candle_range = max(high - low, 0.01)

            upper_wick = high - max(open_price, close)

            upper_wick_pct = (
                upper_wick / candle_range
            ) * 100

            # ====================================
            # CONDITIONS
            # ====================================

            c_ema5 = close > ema5

            c_ema50 = close > ema50

            c_rsi = rsi > rsiLevel

            c_vol = volume > vol_ma

            c_dc = close > dc_upper * (1 + addPct / 100)

            c_buy_wick_ok = upper_wick_pct <= 25

            # ====================================
            # BUY SIGNAL
            # ====================================

            buy_signal = (
                c_ema5
                and c_ema50
                and c_rsi
                and c_vol
                and c_buy_wick_ok
            )

            # ====================================
            # ADD SIGNAL
            # ====================================

            add_signal = (
                c_dc
                and c_ema50
                and c_vol
            )

            # ====================================
            # SELL SIGNAL
            # ====================================

            sell_signal = (
                close < ema5
                or close < ema50
            )

            # ====================================
            # BUY ALERT
            # ====================================

            if buy_signal:

                message = f"""
🚀 BUY SIGNAL

Stock : {stock}

Price : {round(close, 2)}

RSI : {round(rsi, 2)}

Volume Boost : YES

Time : {datetime.now()}
"""

                print(message)

                send_telegram(message)

            # ====================================
            # ADD ALERT
            # ====================================

            if add_signal:

                message = f"""
➕ ADD SIGNAL

Stock : {stock}

Price : {round(close, 2)}

Breakout Above Donchian

Time : {datetime.now()}
"""

                print(message)

                send_telegram(message)

            # ====================================
            # SELL ALERT
            # ====================================

            if sell_signal:

                message = f"""
🔻 SELL SIGNAL

Stock : {stock}

Price : {round(close, 2)}

Weakness Detected

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
