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

    if not scan_time_ok():

        print("Waiting For Market Close")

        return

    print(f"\nScanning Started : {datetime.now()}")

    # ====================================
    # NIFTY DATA
    # ====================================

    nifty = yf.download(
        "^NSEI",
        period="1y",
        interval="1d",
        progress=False,
        auto_adjust=True
    )

    nifty = nifty.dropna()

    nifty_return = (
        float(nifty["Close"].iloc[-1])
        /
        float(nifty["Close"].iloc[-50])
    )

    # ====================================
    # STOCK LOOP
    # ====================================

    for stock in stocks:

        try:

            # ====================================
            # DAILY DATA
            # ====================================

            df = yf.download(
                stock,
                period="1y",
                interval="1d",
                progress=False,
                auto_adjust=True
            )

            if df.empty or len(df) < 60:
                continue

            df = df.dropna()

            # ====================================
            # WEEKLY DATA
            # ====================================

            df_weekly = yf.download(
                stock,
                period="3y",
                interval="1wk",
                progress=False,
                auto_adjust=True
            )

            if df_weekly.empty:
                continue

            # ====================================
            # DAILY INDICATORS
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

            df["VOL_MA"] = (
                df["Volume"]
                .rolling(volPeriod)
                .mean()
            )

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
            # WEEKLY EMA
            # ====================================

            df_weekly["W_EMA"] = ta.trend.ema_indicator(
                df_weekly["Close"],
                window=21
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
            # WEEKLY STAGE 2
            # ====================================

            w_close = float(
                df_weekly["Close"].iloc[-1]
            )

            w_ema = float(
                df_weekly["W_EMA"].iloc[-1]
            )

            old_ema = float(
                df_weekly["W_EMA"].iloc[-6]
            )

            ema_slope = (
                (w_ema - old_ema)
                /
                old_ema
            )

            is_stage2 = (
                w_close > w_ema
                and ema_slope > 0.0005
            )

            # ====================================
            # RELATIVE STRENGTH
            # ====================================

            stock_return = (
                float(df["Close"].iloc[-1])
                /
                float(df["Close"].iloc[-50])
            )

            rs_ratio = (
                stock_return
                /
                nifty_return
            )

            is_rs_positive = rs_ratio > 1

            # ====================================
            # CONDITIONS
            # ====================================

            c_ema5 = close > ema5

            c_ema50 = close > ema50

            c_rsi = rsi > rsiLevel

            c_vol = volume > vol_ma

            c_dc = close > dc_upper * (
                1 + addPct / 100
            )

            c_buy_wick_ok = (
                upper_wick_pct <= 25
            )

            # ====================================
            # BUY SIGNAL
            # ====================================

            buy_signal = (

                is_stage2

                and is_rs_positive

                and c_ema5

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

            trailing_stop = close - (
                atr * atrMult
            )

            sell_signal = (

                close < ema5

                or close < ema50

                or close < trailing_stop

            )

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
