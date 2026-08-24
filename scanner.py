import socket
socket.setdefaulttimeout(20)
from flask_socketio import SocketIO
import threading
import requests
import yfinance as yf
import pandas as pd
import sqlite3
import time
import pytz
import numpy as np
from bs4 import BeautifulSoup

from flask import Flask, render_template, request, jsonify, redirect
from datetime import datetime, timedelta

app = Flask(__name__)

socketio = SocketIO(
    app,
    cors_allowed_origins="*"
)



IST = pytz.timezone("Asia/Kolkata")

# ====================================
# DATABASE
# ====================================

DATABASE = "signals.db"

# ====================================
# CALCULATE RSI
# ====================================

def calculate_rsi(df):

    delta = df["Close"].diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()

    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss

    df["RSI"] = 100 - (100 / (1 + rs))

    return df
# ====================================
# FLASK APP
# ====================================

app = Flask(__name__)

socketio = SocketIO(app)

# ====================================
# DATABASE CONNECTION
# ====================================

def get_db_connection():

    conn = sqlite3.connect(
        "signals.db",
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    return conn
# ====================================
# CREATE FUNDAMENTAL TABLE
# ====================================

def create_fundamental_table():

    conn = sqlite3.connect("signals.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS company_fundamentals (

        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT UNIQUE,

        roe REAL,
        roce REAL,
        sales_growth REAL,
        profit_growth REAL,
        eps_growth REAL,

        opm REAL,
        npm REAL,

        debt_equity REAL,
        market_cap REAL,

        revenue REAL,
        net_profit REAL,
        eps REAL,
        fundamental_score REAL,

        updated_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

    #print("Fundamental table ready ✅")

    # ====================================
    # ADD TECHNOFUNDA RANK COLUMN (RUN ONCE)
    # ====================================

    conn = sqlite3.connect("signals.db")
    cursor = conn.cursor()

    try:

        cursor.execute("""
        ALTER TABLE stock_analysis
        ADD COLUMN technofunda_rank REAL
        """)

        #print(
        #    "technofunda_rank column added ✅"
        #)

    except Exception:

        print(
            "technofunda_rank already exists"
        )

    conn.commit()
    conn.close()

    # ====================================
    # ADD FUNDAMENTAL SCORE COLUMN (RUN ONCE)
    # ====================================

    conn = sqlite3.connect("signals.db")
    cursor = conn.cursor()

    try:
        cursor.execute("""
        ALTER TABLE company_fundamentals
        ADD COLUMN fundamental_score REAL
        """)
        #print("fundamental_score column added ✅")

    except Exception as e:
        print("Column already exists")

    conn.commit()
    conn.close()
# ====================================
# CREATE SIGNAL TABLE
# ====================================

def create_signal_table():

    conn = sqlite3.connect("signals.db")

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock TEXT,
            signal_type TEXT,
            price REAL,
            rsi REAL,
            volume_ratio REAL,
            signal_time TEXT
        )
    """)

    conn.commit()
    

    conn.close()

    #print("Signal table ready ✅")

#print("NEW CODE VERSION LOADED 🚀")


# ====================================
# CREATE TABLE
# ====================================
def create_active_trades_table():

    conn = sqlite3.connect(
        "signals.db"
    )

    cursor = conn.cursor()

    # ======================
    # ACTIVE TRADES
    # ======================

    cursor.execute(
        """

        CREATE TABLE IF NOT EXISTS active_trades (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            stock TEXT,
            timeframe TEXT,

            status TEXT,
            entry_price REAL,
            last_signal TEXT,
            updated_time TEXT,

            UNIQUE(stock, timeframe)

        )

        """
    )

    # ======================
    # SENT ALERTS
    # ======================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sent_alerts(

            id INTEGER
            PRIMARY KEY AUTOINCREMENT,

            stock TEXT,

            alert_type TEXT,

            created_at
            TIMESTAMP DEFAULT
            CURRENT_TIMESTAMP
        )
        """
    )

    # ====================================
    # COMPANY RANKING TABLE
    # ====================================

    cursor.execute("""

    CREATE TABLE IF NOT EXISTS company_ranking (

        stock TEXT PRIMARY KEY,

        market_score REAL,

        sector_rs INTEGER,

        demand_score INTEGER,

        earnings_score INTEGER,

        four_cylinder_score INTEGER,

        machine_score INTEGER,

        canslim_score INTEGER,

        orders_score INTEGER,

        fund_score INTEGER,

        valuation_score INTEGER,

        technical_score INTEGER,

        news_score INTEGER,

        sentiment_score INTEGER,

        total_score INTEGER,

        rating TEXT,

        updated_at TEXT

    )

    """)

    conn.commit()

    conn.close()
  
# ====================================
# SAVE SIGNAL
# ====================================
def save_signal(
        stock,
        signal_type,
        price,
        rsi,
        volume_ratio,
        timeframe,

        daily_close,
        adx,
        rs_daily,
        rs_weekly,
        ema10,
        ema20,
        ema50,

        score,
        fund_score=0,
        technofunda_rank=0,
        sector="Unknown",
        status="NONE",
        signal="NONE",

        ema10_h=0,
        ema20_h=0,
        ema50_h=0,
        atr_h=0,

        ema10_d=0,
        ema20_d=0,
        ema50_d=0,
        atr_d=0,

        ema10_w=0,
        ema20_w=0,
        ema50_w=0,
        atr_w=0
    ):

    conn = sqlite3.connect(
        "signals.db",
        timeout=30
    )

    cursor = conn.cursor()

    # CHECK LAST SIGNAL
    cursor.execute("""
        SELECT signal_type
        FROM signals
        WHERE stock=?
        AND timeframe=?
        ORDER BY id DESC
        LIMIT 1
    """, (
        stock,
        timeframe
    ))

    last_signal = cursor.fetchone()

    # AVOID DUPLICATE BUY SIGNALS
    if last_signal and last_signal[0] == signal_type:

        #print(f"Duplicate {signal_type} skipped for {stock} ⚠️")

        conn.close()

        return

    # INSERT NEW SIGNAL
    #print("INSERTING SIGNAL...")
   
    cursor.execute("""
        INSERT INTO signals (
        stock,
        signal_type,
        price,
        rsi,
        volume_ratio,
        timeframe,
        signal_time
    )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
            stock,
            signal_type,
            price,
            rsi,
            volume_ratio,
            timeframe,
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )
    )

    # OPTIONAL DEBUG
    cursor.execute(
        "SELECT COUNT(*) FROM signals"
    )

    count = cursor.fetchone()[0]

    #print(
    #    "TOTAL DB RECORDS:",
    #    count
    #)

    conn.commit()
    
    # ====================================
    # SAVE STOCK ANALYSIS DATA
    # ====================================

    cursor.execute(
        """
        DELETE FROM stock_analysis
        WHERE stock=?
        """,
        (stock,)
    )

    #print(
    #    "DB INSERT:",
    #    stock,
    #    fund_score,
    #    technofunda_rank
    #)

    cursor.execute("""
        INSERT OR REPLACE INTO stock_analysis (

            stock,
            daily_close,
            rsi,
            adx,
            rs_daily,
            rs_weekly,
            volume_ratio,
            ema10,
            ema20,
            ema50,
            score,
            status,
            signal,
            updated_at,

            ema10_h,
            ema20_h,
            ema50_h,
            atr_h,

            ema10_d,
            ema20_d,
            ema50_d,
            atr_d,

            ema10_w,
            ema20_w,
            ema50_w,
            atr_w,

            technofunda_rank,
            sector,
            fund_score

        )
        VALUES (
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,
            ?,?,?,?,?,?,?,?,
            ?,?,?,?,?,?,?
        )
    """, (

        stock,
        daily_close,
        rsi,
        adx,
        rs_daily,
        rs_weekly,
        volume_ratio,
        ema10,
        ema20,
        ema50,
        score,
        str(status),
        signal,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        ema10_h,
        ema20_h,
        ema50_h,
        atr_h,

        ema10_d,
        ema20_d,
        ema50_d,
        atr_d,

        ema10_w,
        ema20_w,
        ema50_w,
        atr_w,

        technofunda_rank,
        sector,
        fund_score
    ))

    conn.commit()

    cursor.execute(
        "SELECT COUNT(*) FROM signals"
    )

    count = cursor.fetchone()[0]

    #print(
    #   "TOTAL DB RECORDS:",
    #    count
    #)

    conn.commit()
# =====================================
# MY TRADES TABLE
# =====================================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS my_trades (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        stock TEXT NOT NULL,

        buy_date TEXT NOT NULL,
        buy_price REAL NOT NULL,
        qty INTEGER NOT NULL,

        timeframe TEXT,
        strategy TEXT,

        tranche INTEGER DEFAULT 1,

        initial_sl REAL,
        advanced_sl REAL,

        cmp REAL,

        risk_status TEXT,
        status TEXT DEFAULT 'OPEN',

        sell_signal INTEGER DEFAULT 0,
        ema10_exit INTEGER DEFAULT 0,

        exit_price REAL,
        exit_date TEXT,

        pnl REAL,
        pnl_percent REAL,

        remarks TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()

    conn.close()

    #print(f"{signal_type} saved for {stock} ✅")
# ====================================
# SAVE STOCK ANALYSIS (ALL STOCKS)
# ====================================

def save_stock_analysis(

    stock,
    sector,
    daily_close,
    rsi,
    adx,
    rs_daily,
    rs_weekly,
    volume_ratio,
    ema10,
    ema20,
    ema50,

    score,
    fund_score,
    technofunda_rank,

    final_score,
    rating,

    earnings_score,
    four_cylinder_score,
    machine_score,
    canslim_score,
    valuation_score,
    demand_score,

    sales_growth,
    profit_growth,
    eps_growth,

    roe,
    roce,
    debt_equity,

    pe_ratio,
    pb_ratio,

    status,
    signal,

    ema10_h,
    ema20_h,
    ema50_h,
    atr_h,

    ema10_d,
    ema20_d,
    ema50_d,
    atr_d,

    ema10_w,
    ema20_w,
    ema50_w,
    atr_w

):

    conn = sqlite3.connect(
        "signals.db",
        timeout=30
    )

    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM stock_analysis
        WHERE stock=?
        """,
        (stock,)
    )

    cursor.execute(
        """
        INSERT INTO stock_analysis (

            stock,
            sector,
            daily_close,
            rsi,
            adx,
            rs_daily,
            rs_weekly,
            volume_ratio,
            ema10,
            ema20,
            ema50,
            score,
            fund_score,
            technofunda_rank,
            final_score,
            rating,

            earnings_score,
            four_cylinder_score,
            machine_score,
            canslim_score,
            valuation_score,
            demand_score,

            sales_growth,
            profit_growth,
            eps_growth,

            roe,
            roce,
            debt_equity,

            pe_ratio,
            pb_ratio,
            status,
            signal,

            ema10_h,
            ema20_h,
            ema50_h,
            atr_h,

            ema10_d,
            ema20_d,
            ema50_d,
            atr_d,

            ema10_w,
            ema20_w,
            ema50_w,
            atr_w,

            updated_at

        )
        VALUES (
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
            ?,?,?,?,
            ?,?,?,?,
            ?,?,?,?,
            ?
        )
        """,
        (

            stock,
            sector,
            daily_close,
            rsi,
            adx,
            rs_daily,
            rs_weekly,
            volume_ratio,
            ema10,
            ema20,
            ema50,
            score,
            fund_score,
            technofunda_rank,
            final_score,
            rating,

            earnings_score,
            four_cylinder_score,
            machine_score,
            canslim_score,
            valuation_score,
            demand_score,

            sales_growth,
            profit_growth,
            eps_growth,

            roe,
            roce,
            debt_equity,

            pe_ratio,
            pb_ratio,
            str(status),
            signal,

            ema10_h,
            ema20_h,
            ema50_h,
            atr_h,

            ema10_d,
            ema20_d,
            ema50_d,
            atr_d,

            ema10_w,
            ema20_w,
            ema50_w,
            atr_w,

            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )
    )

    conn.commit()
    conn.close()
   
# ====================================
# GET SIGNALS
# ====================================

def get_signals():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""

        SELECT *
        FROM signals
        ORDER BY id DESC
        LIMIT 50

    """)

    rows = cursor.fetchall()

    conn.close()

    return [dict(row) for row in rows]
# ====================================
# DASHBOARD COUNTS
# ====================================

def get_dashboard_counts():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""

        SELECT

            COUNT(*) as total,

            SUM(
                CASE
                WHEN signal_type LIKE '%BUY%'
                THEN 1
                ELSE 0
                END
            ) as buy_count,

            SUM(
                CASE
                WHEN signal_type LIKE '%SELL%'
                THEN 1
                ELSE 0
                END
            ) as sell_count

        FROM signals

        WHERE signal_type != 'NONE'

    """)

    row = cursor.fetchone()

    conn.close()

    return dict(row)
#=======================================
def get_buy_signals():

    conn = sqlite3.connect("signals.db")

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""

        SELECT *
        FROM signals
        WHERE signal_type LIKE '%BUY%'
        ORDER BY id DESC

    """)

    rows = cursor.fetchall()

    conn.close()

    return [dict(row) for row in rows]
#======================================
def get_active_trades():

    conn = sqlite3.connect("signals.db")

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""

        SELECT *
        FROM active_trades
        ORDER BY updated_time DESC

    """)

    rows = cursor.fetchall()

    conn.close()

    return [dict(row) for row in rows]

# ==========================================
# WIN RATE CALCULATION
# ==========================================

def get_win_rate():

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""

        SELECT
            stock,
            signal_type,
            price

        FROM signals

        WHERE signal_time >= datetime('now','-90 day')

        AND signal_type != 'NONE'

        AND (

            signal_type LIKE '%BUY%'

            OR

            signal_type LIKE '%SELL%'

        )

        ORDER BY id ASC

    """)

    rows = cursor.fetchall()

    conn.close()

    stats = {

        "HOURLY": {
            "win":0,
            "loss":0
        },

        "DAILY": {
            "win":0,
            "loss":0
        },

        "WEEKLY": {
            "win":0,
            "loss":0
        }

    }

    open_trades = {}

    for row in rows:

        print(
            row["stock"],
            row["signal_type"],
            row["price"]
        )

        stock = row["stock"]

        signal = str(
            row["signal_type"]
        ).upper()

        price = float(
            row["price"]
        )

        # ======================
        # HOURLY
        # ======================

        key = stock + "_HOURLY"

        if "HOURLY BUY" in signal:

            if key in open_trades and open_trades[key]["type"] == "SELL":

                entry = open_trades[key]["price"]

                if price < entry:

                    stats["HOURLY"]["win"] += 1

                else:

                    stats["HOURLY"]["loss"] += 1

                del open_trades[key]

            else:

                open_trades[key] = {

                    "type":"BUY",
                    "price":price

                }

        elif "HOURLY SELL" in signal:

            if key in open_trades and open_trades[key]["type"] == "BUY":

                entry = open_trades[key]["price"]

                print(
                    "HOURLY DEBUG:",
                    stock,
                    "BUY=",
                    entry,
                    "SELL=",
                    price
                )

                if price >= entry:

                    stats["HOURLY"]["win"] += 1

                else:

                    stats["HOURLY"]["loss"] += 1

                del open_trades[key]

            else:

                open_trades[key] = {

                    "type":"SELL",
                    "price":price

                }

        # ======================
        # DAILY
        # ======================

        key = stock + "_DAILY"

        if "DAILY BUY" in signal:

            if key in open_trades and open_trades[key]["type"] == "SELL":

                entry = open_trades[key]["price"]

                if price < entry:

                    stats["DAILY"]["win"] += 1

                else:

                    stats["DAILY"]["loss"] += 1

                del open_trades[key]

            else:

                open_trades[key] = {

                    "type":"BUY",
                    "price":price

                }

        elif "DAILY SELL" in signal:

            if key in open_trades and open_trades[key]["type"] == "BUY":

                entry = open_trades[key]["price"]

                if price >= entry:

                    stats["DAILY"]["win"] += 1

                else:

                    stats["DAILY"]["loss"] += 1

                del open_trades[key]

            else:

                open_trades[key] = {

                    "type":"SELL",
                    "price":price

                }

        # ======================
        # WEEKLY
        # ======================

        key = stock + "_WEEKLY"

        if "WEEKLY BUY" in signal:

            if key in open_trades and open_trades[key]["type"] == "SELL":

                entry = open_trades[key]["price"]

                if price < entry:

                    stats["WEEKLY"]["win"] += 1

                else:

                    stats["WEEKLY"]["loss"] += 1

                del open_trades[key]

            else:

                open_trades[key] = {

                    "type":"BUY",
                    "price":price

                }

        elif "WEEKLY SELL" in signal:

            if key in open_trades and open_trades[key]["type"] == "BUY":

                entry = open_trades[key]["price"]

                if price >= entry:

                    stats["WEEKLY"]["win"] += 1

                else:

                    stats["WEEKLY"]["loss"] += 1

                del open_trades[key]

            else:

                open_trades[key] = {

                    "type":"SELL",
                    "price":price

                }

    # ==========================
    # WIN %
    # ==========================

    for tf in stats:

        total = (

            stats[tf]["win"]

            +

            stats[tf]["loss"]

        )

        stats[tf]["rate"] = (

            round(

                stats[tf]["win"]

                *100

                /total,

                2

            )

            if total > 0

            else 0

        )

    return stats
# ===========================================
# SCANNER STATUS
# ===========================================

scanner_status = {
    "running": True,
    "last_scan": None,
    "stocks_scanned": 0,
    "active_signals": 0
}

momentum_data = []
stock_analysis_data = []
sector_data = []

def get_momentum_data():
    return momentum_data



# =========================
# ROUTES
# =========================


# ====================================
# DASHBOARD PAGE
# ====================================

@app.route("/")
def dashboard():

    signals = [

        s for s in get_signals()

        if s["signal_type"] != "NONE"

    ]

    counts = get_dashboard_counts()

    win_stats = get_win_rate()

    return render_template(

        "dashboard.html",

        signals=signals,

        buy_count=counts["buy_count"],

        sell_count=counts["sell_count"],

        total_signals=counts["total"],

        win_stats=win_stats

    )

@app.route("/active-trades")
def active_trades():

    trades = get_active_trades()

    return render_template(

        "active_trades.html",

        trades=trades

    )

# ===========================================
# LIVE ALERTS PAGE
# ===========================================

@app.route("/live-alerts")
def live_alerts():

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""

        SELECT * FROM signals
        ORDER BY id DESC
        LIMIT 50

    """)

    alerts = cursor.fetchall()

    conn.close()

    return render_template(
        "live_alerts.html",
        alerts=alerts
    )
# ===========================================
# OPEN SIGNALS PAGE
# ===========================================

@app.route("/open-signals")
def open_signals():

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""

        SELECT * FROM signals
        WHERE signal_type IN ('BUY', 'ADD')
        ORDER BY id DESC

    """)

    data = cursor.fetchall()

    conn.close()

    return render_template(
        "open_signals.html",
        data=data
    )

# ===========================================
# SIGNAL HISTORY PAGE
# ===========================================

@app.route("/signals")
def signals_page():

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""

        SELECT *
        FROM signals
        WHERE signal_type != 'NONE'
        ORDER BY id DESC
        LIMIT 5000

    """)

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "signals.html",
        history=history
    )

# ===========================================
# STATUS PAGE
# ===========================================

@app.route("/momentum-ranking")
def momentum_ranking():

    if momentum_data:
        print(momentum_data[0].keys())

    return render_template(
        "momentum_ranking.html",
        rankings=momentum_data
    )
#===============================
@app.route("/stock-analysis")
def stock_analysis():

    return render_template(
        "stock_analysis.html",
        data=stock_analysis_data
    )
# =========================
# COMPANY ANALYSIS
# =========================

@app.route("/company-analysis")
def company_analysis():

    stock = request.args.get(
        "stock",
        ""
    ).upper()

    conn = sqlite3.connect(
        "signals.db"
    )

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    # =========================
    # STOCK DROPDOWN
    # =========================

    cursor.execute("""
        SELECT stock
        FROM stock_analysis
        ORDER BY stock
    """)

    stock_list = [

        row["stock"]

        for row in cursor.fetchall()

    ]

    latest_data = None
    signal_rows = []

    # =========================
    # COMPANY DATA
    # =========================

    if stock:

        cursor.execute(
            """
            SELECT *
            FROM stock_analysis
            WHERE stock=?
            """,
            (stock,)
        )

        latest_data = cursor.fetchone()

        cursor.execute(
            """
            SELECT *
            FROM signals
            WHERE stock=?
            ORDER BY id DESC
            LIMIT 20
            """,
            (stock,)
        )

        signal_rows = cursor.fetchall()

    conn.close()

    return render_template(

        "company_analysis.html",

        stock=stock,
        latest=latest_data,
        signals=signal_rows,
        stock_list=stock_list

    )
#===========================
@app.route("/sector-ranking")
def sector_ranking():

    return render_template(

        "sector_ranking.html",

        sectors=sector_data
    )
# =========================
# WATCHLIST
# =========================

@app.route(
    "/toggle-watchlist/<stock>"
)
def toggle_watchlist(stock):

    conn = sqlite3.connect(
        "signals.db"
    )

    cursor = conn.cursor()

    cursor.execute(

        """
        SELECT *
        FROM watchlist
        WHERE stock=?
        """,

        (stock,)
    )

    existing = cursor.fetchone()

    if existing:

        cursor.execute(

            """
            DELETE
            FROM watchlist
            WHERE stock=?
            """,

            (stock,)
        )

    else:

        cursor.execute(

            """
            INSERT OR IGNORE
            INTO watchlist(stock)
            VALUES(?)
            """,

            (stock,)
        )

    conn.commit()
    conn.close()

    return redirect(
        request.referrer
    )

#======
@app.route("/watchlist")
def watchlist():

    conn = sqlite3.connect(
        "signals.db"
    )

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            sa.stock,
            sa.score,
            sa.fund_score,
            sa.technofunda_rank,
            sa.signal,
            sa.sector,
            sa.status
        FROM stock_analysis sa
        JOIN watchlist w
            ON sa.stock = w.stock
        ORDER BY sa.stock
        """
    )

    watched_stocks = cursor.fetchall()

    conn.close()

    return render_template(

        "watchlist.html",

        stocks=watched_stocks
    )
# =========================
# ACTIVE TRADES
# =========================

# =========================
# MY TRADES
# =========================

@app.route("/my-trades")
def my_trades():

    conn = sqlite3.connect(
        "signals.db"
    )
    company_filter = request.args.get(
        "company",
        ""
    ).upper()
    portfolio_filter = request.args.get(
        "portfolio",
        "All"
    )

    date_filter = request.args.get(
        "date",
        "All"
    )

    status_filter = request.args.get(
        "status",
        "All"
    )

    sort_filter = request.args.get(
        "sort",
        "date"
    )

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    query = """
    SELECT *
    FROM my_trades
    WHERE 1=1
    """

    params = []

    if portfolio_filter != "All":

        query += """
        AND portfolio=?
        """

        params.append(
            portfolio_filter
        )

    if company_filter:

        query += """
        AND stock LIKE ?
        """

        params.append(
            "%" +
            company_filter +
            "%"
        )

    if date_filter == "Today":

        query += """
        AND date(created_at)=date('now')
        """

    elif date_filter == "Week":

        query += """
        AND date(created_at)
        >=
        date('now','-7 day')
        """

    elif date_filter == "Month":

        query += """
        AND strftime(
            '%Y-%m',
            created_at
        )
        =
        strftime(
            '%Y-%m',
            'now'
        )
        """

        query += """
        AND stock LIKE ?
        """

        params.append(
            "%" +
            company_filter +
            "%"
        )

    query += """
    ORDER BY id DESC
    """

    cursor.execute(
        query,
        params
    )

    trades = cursor.fetchall()

    if not trades:
        trade_list = []
    else:
        trade_list = []

    total_pl = 0
    open_trades = 0
    closed_trades = 0
    invested_capital = 0
    total_rr = 0
    

    trade_list = []

    alerts = []

    for t in trades:

        # =====================
        # STATUS FILTER
        # =====================

        if (
            status_filter != "All"
            and
            t["status"] != status_filter
        ):
            continue

        cursor.execute(
            """
            SELECT
                daily_close,
                signal
            FROM stock_analysis
            WHERE stock=?
            """,
            (t["stock"],)
        )

        row = cursor.fetchone()

        cmp_price = (
            row["daily_close"]
            if row
            else 0
        )

        signal_text = ""

        if row and row["signal"]:
            signal_text = row["signal"]

        # =====================
        # SL ALERT
        # =====================

        if (
            t["status"] == "OPEN"
            and
            cmp_price <= t["stoploss"]
        ):

            msg = (
                f"⚠ SL Trigger "
                f"{t['stock']} "
                f"CMP:{cmp_price:.2f} "
                f"SL:{t['stoploss']:.2f}"
            )

            alerts.append(msg)

            if not alert_sent(
                cursor,
                t["stock"],
                "SL"
            ):

                send_telegram(msg)

                save_alert(
                    conn,
                    cursor,
                    t["stock"],
                    "SL"
                )

        # =====================
        # TARGET ALERT
        # =====================

        if (
            t["status"] == "OPEN"
            and
            cmp_price >= t["target"]
        ):

            msg = (
                f"🎯 Target Achieved\n"
                f"{t['stock']}\n"
                f"CMP:{cmp_price:.2f}"
            )

            alerts.append(msg)

            if not alert_sent(
                cursor,
                t["stock"],
                "TARGET"
            ):

                send_telegram(msg)

                save_alert(
                    conn,
                    cursor,
                    t["stock"],
                    "TARGET"
                )

        # =====================
        # SIGNALS
        # =====================

        sell_signal = (

            signal_text
            ==
            "SELL"

        )
        

        add_signal = (

            signal_text
            ==
            "ADD"

        )

        # ==========================
        # TIMEFRAME EMA
        # ==========================

        ema_value = None

        if t["timeframe"] == "H":

            ema_value = row["ema10_h"]

        elif t["timeframe"] == "D":

            ema_value = row["ema10_d"]

        elif t["timeframe"] == "W":

            ema_value = row["ema10_w"]

        # =====================
        # 10 EMA EXIT
        # AFTER 3RD TRANCHE
        # =====================

        ema_exit = False

        if (
            row
            and
            t["tranche"] >= 3
            and
            ema_value is not None
            and
            cmp_price < ema_value
        ):

            ema_exit = True


        # =====================
        # EXIT ALERT
        # =====================

        exit_alert = (

            t["status"]
            ==
            "OPEN"

            and

            t["tranche"]
            >=
            3

            and

            (

                sell_signal
                or
                ema_exit

            )
        )
        # =====================
        # EXIT ALERT
        # =====================

        if exit_alert:

            msg = (
                f"🔴 EXIT Alert "
                f"{t['stock']} "
                f"CMP:{cmp_price:.2f}"
            )

            alerts.append(msg)

            if not alert_sent(
                cursor,
                t["stock"],
                "EXIT_ALERT"
            ):

                send_telegram(msg)

                save_alert(
                    conn,
                    cursor,
                    t["stock"],
                    "EXIT_ALERT"
                )

        # =====================
        # ADD ALERT
        # =====================

        if (
            t["status"] == "OPEN"
            and
            add_signal
        ):

            msg = (
                f"🔵 ADD Alert "
                f"{t['stock']} "
                f"CMP:{cmp_price:.2f}"
            )

            alerts.append(msg)

            if not alert_sent(
                cursor,
                t["stock"],
                "ADD"
            ):

                send_telegram(msg)

                save_alert(
                    conn,
                    cursor,
                    t["stock"],
                    "ADD"
                )

        # =====================
        # P/L
        # =====================

        realized_pl = (
            t["pl"]
            or
            0
        )

        live_pl = round(
            (
                cmp_price
                -
                t["entry"]
            )
            *
            t["qty"],
            2
        )

        pl = round(
            live_pl
            +
            realized_pl,
            2
        )

        # =====================
        # RR
        # =====================

        risk = (
            t["entry"]
            -
            t["stoploss"]
        )

        if risk > 0:

            rr = round(
                (
                    cmp_price
                    -
                    t["entry"]
                )
                /
                risk,
                2
            )

        else:

            rr = 0

        # =====================
        # TOTALS
        # =====================

        total_pl += pl

        invested_capital += (
            t["entry"]
            *
            t["qty"]
        )

        total_rr += rr

        if t["status"] == "OPEN":
            open_trades += 1
        else:
            closed_trades += 1

        trade_list.append({

            "id":t["id"],
            "portfolio":t["portfolio"],
            "timeframe":t["timeframe"],
            "strategy":t["strategy"],
            "tranche":t["tranche"],
            "remarks":t["remarks"],

            "stock":t["stock"],
            "entry":t["entry"],
            "qty":t["qty"],
            "stoploss":t["stoploss"],
            "target":t["target"],
            "status":t["status"],
            "created_at":t["created_at"],
            "cmp":cmp_price,
            "pl":pl,
            "rr":rr
        })

    # ======================
    # SORTING
    # ======================

    if sort_filter == "date":

        trade_list = sorted(
            trade_list,
            key=lambda x:
            x["created_at"],
            reverse=True
        )

    elif sort_filter == "pl":

        trade_list = sorted(
            trade_list,
            key=lambda x:
            x["pl"],
            reverse=True
        )

    elif sort_filter == "rr":

        trade_list = sorted(
            trade_list,
            key=lambda x:
            x["rr"],
            reverse=True
        )

        # ======================
        # TRADE LOG
        # ======================

        
        
    cursor.execute(
        """
        SELECT
            tt.*,
            mt.stock
        FROM
            trade_transactions tt
        LEFT JOIN
            my_trades mt
        ON
            tt.trade_id = mt.id
        ORDER BY
            tt.created_at DESC
        """
    )

    transactions = cursor.fetchall()

    company_query = """
    SELECT DISTINCT stock
    FROM my_trades
    """

    company_params = []

    if portfolio_filter != "All":

        company_query += """
        WHERE portfolio=?
        """

        company_params.append(
            portfolio_filter
        )

    company_query += """
    ORDER BY stock
    """

    cursor.execute(
        company_query,
        company_params
    )

    

    companies = cursor.fetchall()          
        
        
    conn.close()
    return render_template(

        "my_trades.html",

        trades=trade_list,

        transactions=transactions,

        alerts=alerts,

        portfolio_filter=
        portfolio_filter,

        companies=
        companies,

        company_filter=
        company_filter,

        date_filter=
        date_filter,

        status_filter=
        status_filter,

        sort_filter=
        sort_filter,

        total_pl=round(
            total_pl,
            2
        ),

        total_trades=len(
            trade_list
        ),

        open_trades=open_trades,

        closed_trades=closed_trades,

        invested_capital=round(
            invested_capital,
            2
        ),

        portfolio_rr=round(

            total_rr

            /

            max(
                len(trade_list),
                1
            ),

            2
        )
    )

# ====================================
# COMPANY RANKING
# ====================================

@app.route("/ranking")
def ranking():

    conn = sqlite3.connect(
        "signals.db"
    )

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT

            r.*,

            f.roe,
            f.roce,
            f.sales_growth,
            f.profit_growth,
            f.eps_growth,
            f.opm,
            f.npm,
            f.debt_equity

        FROM company_ranking r

        LEFT JOIN company_fundamentals f
        ON r.stock = f.symbol

        ORDER BY r.final_score DESC
        """
    )

    rankings = cursor.fetchall()

    conn.close()

    return render_template(
        "ranking.html",
        rankings=rankings
    )
       
# =========================
# ADD MY TRADE
# =========================

@app.route(
    "/add-my-trade",
    methods=["POST"]
)
def add_my_trade():

    portfolio = request.form[
        "portfolio"
    ]
    
    trade_date = request.form[
        "trade_date"
    ]

    timeframe = request.form["timeframe"]

    strategy = request.form["strategy"]

    tranche = int(
        request.form["tranche"]
    )

    stock = (
        request.form["stock"]
        .upper()
        .strip()
    )

    # AUTO NSE SYMBOL
    if not stock.endswith(".NS"):
        stock += ".NS"

    entry = float(
        request.form["entry"]
    )

    qty = int(
        request.form["qty"]
    )

    stoploss = float(
        request.form["stoploss"]
    )

    target = float(
        request.form["target"]
    )

    remarks = request.form.get(
        "remarks",
        ""
    )

    conn = sqlite3.connect(
        "signals.db"
    )

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO my_trades(

            portfolio,
            created_at,
            timeframe,
            strategy,
            tranche,
            stock,
            entry,
            qty,
            stoploss,
            target,
            remarks

        )
        VALUES(

            ?,?,?,?,?,?,?,?,?,?,?

        )
        """,
        (
            portfolio,
            trade_date,
            timeframe,
            strategy,
            tranche,
            stock,
            entry,
            qty,
            stoploss,
            target,
            remarks
        )
    )
    # SAVE ACTIVITY LOG

    trade_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO trade_transactions(

            trade_id,
            action,
            qty,
            price

        )
        VALUES(

            ?,?,?,?

        )
        """,
        (
            trade_id,
            "ADD_TRADE",
            qty,
            entry
        )
    )
    conn.commit()
    print(
        "Saving log:",
        stock,
        qty,
        entry
    )
    conn.close()

    return redirect(
        "/my-trades"
    )
# =========================
# PARTIAL SELL
# =========================

@app.route(
    "/partial-sell/<int:trade_id>",
    methods=["POST"]
)
def partial_sell(trade_id):

    qty = int(
        request.form[
            "qty"
        ]
    )

    price = float(
        request.form[
            "price"
        ]
    )

    conn = sqlite3.connect(
        "signals.db"
    )

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # GET TRADE
    cursor.execute(
        """
        SELECT *
        FROM my_trades
        WHERE id=?
        """,
        (trade_id,)
    )

    trade = cursor.fetchone()

    if trade:

        current_qty = trade["qty"]
        entry_price = trade["entry"]

        # INVALID SELL
        if qty > current_qty:

            conn.close()

            return redirect(
                "/my-trades"
            )

        # REALIZED P/L
        realized_pl = (
            price
            -
            entry_price
        ) * qty

        remaining_qty = (
            current_qty
            -
            qty
        )

        # ACTION TYPE

        action_type = (
            "SELL"
            if remaining_qty == 0
            else
            "PARTIAL_SELL"
        )

        # SAVE TRANSACTION
        cursor.execute(
            """
            INSERT INTO
            trade_transactions
            (
                trade_id,
                action,
                qty,
                price
            )
            VALUES
            (?, ?, ?, ?)
            """,
            (
                trade_id,
                action_type,
                qty,
                price
            )
        )

        # UPDATE TRADE
        if remaining_qty == 0:

            cursor.execute(
                """
                UPDATE my_trades
                SET
                qty=0,
                status='CLOSED',
                pl=COALESCE(pl,0)+?
                WHERE id=?
                """,
                (
                    realized_pl,
                    trade_id
                )
            )

        else:

            cursor.execute(
                """
                UPDATE my_trades
                SET
                qty=?,
                pl=COALESCE(pl,0)+?
                WHERE id=?
                """,
                (
                    remaining_qty,
                    realized_pl,
                    trade_id
                )
            )

    conn.commit()
    conn.close()

    return redirect(
        "/my-trades"
    )
# =========================
# ADD POSITION
# =========================

@app.route(
    "/add-position/<int:trade_id>",
    methods=["POST"]
)
def add_position(trade_id):

    qty = int(
        request.form[
            "qty"
        ]
    )

    price = float(
        request.form[
            "price"
        ]
    )

    conn = sqlite3.connect(
        "signals.db"
    )

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM my_trades
        WHERE id=?
        """,
        (trade_id,)
    )

    trade = cursor.fetchone()

    if trade:

        old_qty = trade["qty"]
        old_entry = trade["entry"]

        total_qty = (
            old_qty
            +
            qty
        )

        avg_entry = (

            (
                old_qty
                *
                old_entry
            )

            +

            (
                qty
                *
                price
            )

        ) / total_qty

        # AUTO SL LOGIC

        old_sl = trade["stoploss"]
        tranche = trade["tranche"]

        # ORIGINAL TOTAL RISK

        original_risk = (

            (
                old_entry
                -
                old_sl
            )

            *

            old_qty
        )

        # =====================
        # 2ND TRANCHE
        # SAME TOTAL RISK
        # =====================

        if tranche == 1:

            new_sl = (

                avg_entry

                -

                (
                    original_risk
                    /
                    total_qty
                )
            )

            new_tranche = 2


        # =====================
        # 3RD TRANCHE
        # ZERO RISK
        # =====================

        elif tranche == 2:

            new_sl = avg_entry

            new_tranche = 3


        # =====================
        # AFTER 3RD
        # KEEP SAME
        # =====================

        else:

            new_sl = old_sl

            new_tranche = tranche


        cursor.execute(
            """
            UPDATE my_trades
            SET
            qty=?,
            entry=?,
            stoploss=?,
            tranche=?
            WHERE id=?
            """,
            (
                total_qty,
                avg_entry,
                new_sl,
                new_tranche,
                trade_id
            )
        )

        # SAVE LOG
        cursor.execute(
            """
            INSERT INTO
            trade_transactions
            (
                trade_id,
                action,
                qty,
                price
            )
            VALUES
            (?, ?, ?, ?)
            """,
            (
                trade_id,
                "ADD",
                qty,
                price
            )
        )

    conn.commit()
    conn.close()

    return redirect(
        "/my-trades"
    )
# =========================
# UPDATE TSL
# =========================

@app.route(
    "/update-tsl/<int:trade_id>",
    methods=["POST"]
)
def update_tsl(trade_id):

    new_tsl = float(
        request.form["new_tsl"]
    )

    conn = sqlite3.connect(
        "signals.db"
    )

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE my_trades
        SET stoploss=?
        WHERE id=?
        """,
        (
            new_tsl,
            trade_id
        )
    )

    cursor.execute(
        """
        INSERT INTO
        trade_transactions
        (
            trade_id,
            action,
            qty,
            price
        )
        VALUES
        (?, ?, ?, ?)
        """,
        (
            trade_id,
            "TSL_UPDATE",
            0,
            new_tsl
        )
    )

    conn.commit()
    conn.close()

    return redirect(
        "/my-trades"
    )
# =========================
# UPDATE TRADE DATE
# =========================

@app.route(
    "/update-date/<int:trade_id>",
    methods=["POST"]
)
def update_trade_date(trade_id):

    new_date = request.form[
        "new_date"
    ]

    conn = sqlite3.connect(
        "signals.db"
    )

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE my_trades
        SET created_at=?
        WHERE id=?
        """,
        (
            new_date,
            trade_id
        )
    )

    conn.commit()
    conn.close()

    return redirect(
        "/my-trades"
    )
# =========================
# UPDATE TARGET
# =========================

@app.route(
    "/update-target/<int:trade_id>",
    methods=["POST"]
)
def update_target(trade_id):

    new_target = float(
        request.form["new_target"]
    )

    conn = sqlite3.connect(
        "signals.db"
    )

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE my_trades
        SET target=?
        WHERE id=?
        """,
        (
            new_target,
            trade_id
        )
    )

    cursor.execute(
        """
        INSERT INTO
        trade_transactions
        (
            trade_id,
            action,
            qty,
            price
        )
        VALUES
        (?, ?, ?, ?)
        """,
        (
            trade_id,
            "TARGET_UPDATE",
            0,
            new_target
        )
    )

    conn.commit()
    conn.close()

    return redirect(
        "/my-trades"
    )

#==============
@app.route(
    "/close-trade/<int:trade_id>"
)
def close_trade(trade_id):

    conn = sqlite3.connect(
        "signals.db"
    )

    cursor = conn.cursor()

    cursor.execute(

        """
        UPDATE my_trades
        SET status='CLOSED'
        WHERE id=?
        """,

        (trade_id,)
    )

    conn.commit()
    conn.close()

    return redirect(
        "/my-trades"
    )
# =========================
# TRADE ENTRY PAGE
# =========================

@app.route("/trade-add")
def trade_add():

    return render_template(
        "trade_add.html"
    )
# =========================================
# COMPANY ANALYSIS V2
# =========================================

@app.route("/company-analysis-v2")
def company_analysis_v2():

    stock = request.args.get(
        "stock",
        ""
    ).upper()

    conn = sqlite3.connect(
        "signals.db"
    )

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    # =========================
    # STOCK DROPDOWN
    # =========================

    cursor.execute("""
        SELECT stock
        FROM stock_analysis
        ORDER BY stock
    """)

    stock_list = [

        row["stock"]

        for row in cursor.fetchall()

    ]

    latest_data = None
    signal_rows = []

    # =========================
    # COMPANY DATA
    # =========================

    if stock:

        cursor.execute(
            """
            SELECT *
            FROM stock_analysis
            WHERE stock=?
            """,
            (stock,)
        )

        latest_data = cursor.fetchone()

        cursor.execute(
            """
            SELECT *
            FROM signals
            WHERE stock=?
            ORDER BY id DESC
            LIMIT 20
            """,
            (stock,)
        )

        signal_rows = cursor.fetchall()

    conn.close()

    return render_template(

        "company_analysis_v2.html",

        stock=stock,
        latest=latest_data,
        signals=signal_rows,
        stock_list=stock_list

    )
# ====================================
# LIVE SOCKET UPDATE FUNCTION
# ====================================

def background_signal_updater():

    #print("SOCKET UPDATER STARTED 🚀")

    conn = sqlite3.connect(DATABASE)

    cursor = conn.cursor()

    cursor.execute("""

        SELECT MAX(id)
        FROM signals

    """)

    last = cursor.fetchone()[0]

    conn.close()

    # ====================================
    # INITIAL LAST ID
    # ====================================

    if last is None:

        last_id = 0

    else:

        last_id = last

    #print("INITIAL LAST ID:", last_id)

    # ====================================
    # LIVE LOOP
    # ====================================

    while True:

        try:

            conn = sqlite3.connect(DATABASE)

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute("""

                SELECT *
                FROM signals
                WHERE id > ?
                ORDER BY id ASC

            """, (last_id,))

            new_rows = cursor.fetchall()

            conn.close()

            # ====================================
            # EMIT LIVE SIGNALS
            # ====================================

            for row in new_rows:

                signal = dict(row)

                #print("LIVE SIGNAL:", signal)

                socketio.emit(

                    "new_signal",
                    signal

                )

                last_id = signal["id"]

            # ====================================
            # SMALL DELAY
            # ====================================

            time.sleep(2)

        except Exception as e:

            #print("SOCKET ERROR:", e)

            time.sleep(5)
# ====================================
# TELEGRAM SETTINGS
# ====================================
DATABASE = "signals.db"

BOT_TOKEN = "8657217148:AAGUftF7a8zQNeb1AnJsx2CVBFehJ-Oi1Ko"
CHAT_ID = "1190014186"

# ====================================
# NIFTY STOCKS
# ====================================
from nifty500 import stocks
from sector_map import sector_map
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
# COMPANY RATING
# ====================================

def get_rating(score):

    if score >= 80:
        return "🚀 Elite"

    elif score >= 65:
        return "📈 Strong Buy"

    elif score >= 50:
        return "👀 Watchlist"

    elif score >= 35:
        return "⚠️ Accumulate"

    else:
        return "❌ Avoid"  
# =================================
# ALERT MEMORY
# =================================

def alert_sent(
    cursor,
    stock,
    alert_type
):

    cursor.execute(
        """
        SELECT id
        FROM sent_alerts
        WHERE stock=?
        AND alert_type=?
        """,
        (
            stock,
            alert_type
        )
    )

    return (
        cursor.fetchone()
        is not None
    )


def save_alert(
    conn,
    cursor,
    stock,
    alert_type
):

    cursor.execute(
        """
        INSERT INTO sent_alerts(

            stock,
            alert_type

        )
        VALUES(?,?)
        """,
        (
            stock,
            alert_type
        )
    )

    conn.commit()
# =================================
# ALERT MEMORY
# =================================

def alert_sent(
    cursor,
    stock,
    alert_type
):

    cursor.execute(
        """
        SELECT id
        FROM sent_alerts
        WHERE stock=?
        AND alert_type=?
        """,
        (
            stock,
            alert_type
        )
    )

    return (
        cursor.fetchone()
        is not None
    )


def save_alert(
    conn,
    cursor,
    stock,
    alert_type
):

    cursor.execute(
        """
        INSERT INTO
        sent_alerts(

            stock,
            alert_type

        )
        VALUES(?,?)
        """,
        (
            stock,
            alert_type
        )
    )

    conn.commit()

# ====================================
# NSE MARKET TIME
# ====================================
def market_open():

    now = datetime.now()

    # NSE MARKET HOURS
    if now.weekday() >= 5:
        return False
# ====================================
# FUNDAMENTAL FETCH ENGINE
# ====================================

def fetch_fundamentals(symbol):

    try:
        ticker = yf.Ticker(symbol + ".NS")

        info = ticker.info

        # =====================================
        # GET SECTOR
        # =====================================

        try:

            sector = info.get("sector", "Unknown")

            if sector is None or sector == "":
                sector = "Unknown"

        except:

            sector = "Unknown"

        financials = ticker.financials
        balance_sheet = ticker.balance_sheet

        roce = 0

        try:

            if (
                not financials.empty and
                not balance_sheet.empty
            ):

                ebit = 0

                if "EBIT" in financials.index:
                    ebit = financials.loc["EBIT"].iloc[0]

                total_assets = 0

                if "Total Assets" in balance_sheet.index:
                    total_assets = balance_sheet.loc[
                        "Total Assets"
                    ].iloc[0]

                current_liabilities = 0

                if "Current Liabilities" in balance_sheet.index:
                    current_liabilities = balance_sheet.loc[
                        "Current Liabilities"
                    ].iloc[0]

                capital_employed = (
                    total_assets -
                    current_liabilities
                )

                if capital_employed > 0:

                    roce = (
                        ebit /
                        capital_employed
                    ) * 100

        except:
            pass

        market_cap = info.get("marketCap", 0)
        debt_equity = info.get("debtToEquity", 0)
        roe = info.get("returnOnEquity")

        roe = info.get("returnOnEquity")

        if roe is None:
            roe = 0
        else:
            roe = round(roe * 100, 2)


        pe_ratio = info.get("trailingPE", 0) or 0
        pb_ratio = info.get("priceToBook", 0) or 0

        revenue = 0
        net_profit = 0
        eps = info.get("trailingEps", 0)

        if not financials.empty:
            if "Total Revenue" in financials.index:
                revenue = financials.loc["Total Revenue"].iloc[0]

            if "Net Income" in financials.index:
                net_profit = financials.loc["Net Income"].iloc[0]

        
        # ROCE already calculated above

        # =====================================
        # GROWTH & MARGIN DATA
        # =====================================

        revenue_growth = (
            info.get("revenueGrowth", 0) or 0
        ) * 100

        earnings_growth = (
            info.get("earningsGrowth", 0) or 0
        ) * 100

        opm = (
            info.get("operatingMargins", 0) or 0
        ) * 100

        npm = (
            info.get("profitMargins", 0) or 0
        ) * 100

        return {
            "roe": round(roe, 2),

            # Temporary ROCE
            "roce": round(roce, 2),

            "pe_ratio": round(pe_ratio, 2),

            "pb_ratio": round(pb_ratio, 2),

            "sales_growth": round(
                revenue_growth,
                2
            ),

            "profit_growth": round(
                earnings_growth,
                2
            ),

            "eps_growth": round(
                earnings_growth,
                2
            ),

            "opm": round(
                opm,
                2
            ),

            "npm": round(
                npm,
                2
            ),
            

            "debt_equity": debt_equity,

            "market_cap": market_cap,

            "revenue": revenue,

            "net_profit": net_profit,

            "eps": eps
        }

    except Exception as e:
        print(f"Fundamental fetch error {symbol}: {e}")
        return None
# ====================================
# SAVE FUNDAMENTALS
# ====================================

def save_fundamentals(symbol, data):

    if data is None:
        return

    conn = sqlite3.connect("signals.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO company_fundamentals (

        symbol,
        roe,
        roce,
        pe_ratio,
        pb_ratio,
        sales_growth,
        profit_growth,
        eps_growth,
        opm,
        npm,
        debt_equity,
        market_cap,
        revenue,
        net_profit,
        eps,
        fundamental_score,
        updated_at

    ) VALUES (

        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP

    )
    """, (

        symbol,
        data["roe"],
        data["roce"],
        data.get("pe_ratio", 0),
        data.get("pb_ratio", 0),
        data["sales_growth"],
        data["profit_growth"],
        data["eps_growth"],
        data["opm"],
        data["npm"],
        data["debt_equity"],
        data["market_cap"],
        data["revenue"],
        data["net_profit"],
        data["eps"],
        data.get("fundamental_score", 0)

    ))
    conn.commit()
    conn.close()

    #print(f"Fundamental saved: {symbol} ✅")
# ====================================
# CHECK FUNDAMENTAL REFRESH
# ====================================

def fundamental_needs_update(symbol):

    conn = sqlite3.connect("signals.db")
    cursor = conn.cursor()

    cursor.execute("""

        SELECT updated_at
        FROM company_fundamentals
        WHERE symbol=?

    """, (symbol,))

    row = cursor.fetchone()

    conn.close()

    if row is None:
        return True

    updated_at = datetime.strptime(
        row[0],
        "%Y-%m-%d %H:%M:%S"
    )

    age = datetime.now() - updated_at

    return age.days >= 7
# ====================================
# FUNDAMENTAL SCORE ENGINE
# ====================================

def calculate_fundamental_score(data, rs_daily):

    score = 0

    # ======================
    # GROWTH
    # ======================

    if data["sales_growth"] > 15:
        score += 7

    if data["profit_growth"] > 15:
        score += 8

    # ======================
    # MARGINS
    # ======================

    if data["opm"] > 15:
        score += 7

    if data["npm"] > 10:
        score += 8

    # ======================
    # ROE / ROCE
    # ======================

    if data["roe"] >= 15:
        score += 7

    roce = data.get("roce", 0)

    if roce >= 30:
        score += 8
    elif roce >= 20:
        score += 6
    elif roce >= 15:
        score += 4

    # ======================
    # DEBT
    # ======================

    debt = data["debt_equity"] or 999

    if debt < 1:
        score += 15

    # ======================
    # EPS
    # ======================

    if data["eps_growth"] > 20:
        score += 15

    # ======================
    # RS LEADER
    # ======================

    rs_daily = rs_daily or 0

    if rs_daily > 0:
        score += 15

    # ======================
    # SIZE
    # ======================

    if data["market_cap"] > 1e10:
        score += 10

    return min(score, 100)  
# ====================================
# TECHNOFUNDA RANK ENGINE
# ====================================

def calculate_technofunda_rank(
    technical_score,
    fundamental_score
):

    technical_score = (
        technical_score or 0
    )

    fundamental_score = (
        fundamental_score or 0
    )

    rank = (

        technical_score * 0.55

        +

        fundamental_score * 0.45

    )

    return round(rank, 2)
# ====================================
# 4 CYLINDER GROWTH MODEL
# ====================================

def calculate_four_cylinder_score(data):

    if not fund_data:
        return 0

    score = 0

    sales_growth = data.get(
        "sales_growth", 0
    ) or 0

    profit_growth = data.get(
        "profit_growth", 0
    ) or 0

    opm = data.get(
        "opm", 0
    ) or 0

    debt_equity = data.get(
        "debt_equity", 999
    ) or 999

    # ======================
    # CYLINDER 1
    # SALES GROWTH
    # ======================

    if sales_growth > 25:
        score += 4

    elif sales_growth > 15:
        score += 3

    elif sales_growth > 10:
        score += 2

    elif sales_growth > 5:
        score += 1

    # ======================
    # CYLINDER 2
    # PROFIT GROWTH
    # ======================

    if profit_growth > 30:
        score += 4

    elif profit_growth > 20:
        score += 3

    elif profit_growth > 10:
        score += 2

    elif profit_growth > 5:
        score += 1

    # ======================
    # CYLINDER 3
    # MARGIN QUALITY
    # ======================

    if opm > 25:
        score += 4

    elif opm > 15:
        score += 3

    elif opm > 10:
        score += 2

    elif opm > 5:
        score += 1

    # ======================
    # CYLINDER 4
    # DEBT REDUCTION
    # ======================

    if debt_equity < 0.25:
        score += 3

    elif debt_equity < 0.50:
        score += 2

    elif debt_equity < 1:
        score += 1

    return min(score, 12)
# ====================================
# EARNINGS SCORE
# ====================================

def calculate_earnings_score(data):

    if not data:
        return 0

    if data is None:
        return 0

    sales_growth = data.get(
        "sales_growth",
        0
    ) or 0

    profit_growth = data.get(
        "profit_growth", 0
    ) or 0

    eps_growth = data.get(
        "eps_growth", 0
    ) or 0

    # SALES

    if sales_growth >= 25:
        score += 4

    elif sales_growth >= 15:
        score += 3

    elif sales_growth >= 10:
        score += 2

    elif sales_growth >= 5:
        score += 1

    # PROFIT

    if profit_growth >= 25:
        score += 4

    elif profit_growth >= 15:
        score += 3

    elif profit_growth >= 10:
        score += 2

    elif profit_growth >= 5:
        score += 1

    # EPS

    if eps_growth >= 25:
        score += 4

    elif eps_growth >= 15:
        score += 3

    elif eps_growth >= 10:
        score += 2

    elif eps_growth >= 5:
        score += 1

    return min(score, 12)
# ====================================
# MACHINE SCORE (/10)
# ====================================

def calculate_machine_score(
    data,
    rs_daily,
    volume_ratio,
    sector_avg
):
    if data is None:
        return 0

    score = 0

    sales_growth = data.get(
        "sales_growth", 0
    ) or 0

    profit_growth = data.get(
        "profit_growth", 0
    ) or 0

    roe = data.get("roe", 0) or 0
    roce = data.get("roce", 0) or 0

    roe_score = max(min(roe, 100), -100)
    roce_score = max(min(roce, 100), -100)

    # ======================
    # M = MEGATREND (1)
    # ======================

    if sector_avg >= 60:
        score += 1

    # ======================
    # A = ACTION (2)
    # ======================

    if rs_daily > 0:
        score += 1

    if volume_ratio > 1:
        score += 1

    # ======================
    # C = COMPETITIVE ADV. (1)
    # ======================

    if roe >= 15:
        score += 1

    # ======================
    # H = HIGH ROCE (2)
    # ======================

    if roce >= 20:
        score += 2

    elif roce >= 15:
        score += 1

    # ======================
    # I = IMPROVEMENT (1)
    # ======================

    if profit_growth > sales_growth:
        score += 1

    # ======================
    # N = NEW (0 FOR NOW)
    # ======================

    score += 0

    # ======================
    # E = EXECUTION (2)
    # ======================

    if sales_growth >= 15:
        score += 1

    if profit_growth >= 15:
        score += 1

    return min(score, 10)
# =====================================
# VALUATION SCORE (/5)
# =====================================

def calculate_valuation_score(fund_data):

    if not fund_data:
        return 0

    score = 0

    pe = fund_data.get("pe_ratio", 0) or 0
    pb = fund_data.get("pb_ratio", 0) or 0

    growth = max(
        fund_data.get("profit_growth", 0),
        fund_data.get("sales_growth", 0),
        1
    )

    # PEG

    if pe > 0:

        peg = pe / growth

        if peg < 1:
            score += 3

        elif peg < 2:
            score += 2

        elif peg < 3:
            score += 1

    # PB

    if pb > 0 and pb < 5:
        score += 2

    return min(score, 5)
# ====================================
# DEMAND SCORE
# ====================================
demand_score = 0
rs_daily = 0
volume_ratio = 0

def calculate_demand_score(
    volume_ratio,
    rs_daily,
    close_price,
    ema50,
    ema200,
    high_52w
):

    score = 0

    # ==================
    # VOLUME
    # ==================

    if volume_ratio >= 2:
        score += 4

    elif volume_ratio >= 1.5:
        score += 3

    elif volume_ratio >= 1.2:
        score += 2

    elif volume_ratio >= 0.8:
        score += 1

    # ==================
    # RS DAILY
    # ==================

    if rs_daily >= 0.05:
        score += 4

    elif rs_daily >= 0.03:
        score += 3

    elif rs_daily >= 0.01:
        score += 2

    elif rs_daily > 0:
        score += 1

    # ==================
    # BREAKOUT
    # ==================

    if close_price >= high_52w * 0.98:
        score += 2

    # ==================
    # EMA STRUCTURE
    # ==================

    if close_price > ema50 and ema50 > ema200:
        score += 2

    return min(score, 12)
#==========================================================================
# ====================================
# CANSLIM SCORE
# ====================================

def calculate_canslim_score(
    fund_data,
    rs_daily,
    volume_ratio
):
    if not fund_data:
        return 0

    score = 0

    eps_growth = (
        fund_data.get(
            "eps_growth",
            0
        ) or 0
    )

    profit_growth = (
        fund_data.get(
            "profit_growth",
            0
        ) or 0
    )

    rs_daily = rs_daily or 0

    volume_ratio = (
        volume_ratio or 0
    )

    # =====================
    # C = Current Earnings
    # =====================

    if eps_growth > 25:
        score += 2

    elif eps_growth > 10:
        score += 1

    # =====================
    # A = Annual Earnings
    # =====================

    if profit_growth > 25:
        score += 2

    elif profit_growth > 10:
        score += 1

    # =====================
    # L = Leader
    # =====================

    if rs_daily > 0.50:
        score += 2

    elif rs_daily > 0.20:
        score += 1

    # =====================
    # S = Supply / Demand
    # =====================

    if volume_ratio > 2:
        score += 2

    elif volume_ratio > 1.2:
        score += 1

    # =====================
    # N = New High Proxy
    # =====================

    if rs_daily > 0.50 and volume_ratio > 1:
        score += 2

    elif rs_daily > 0.20:
        score += 1

    return min(score, 10)
# ====================================
# TECHNOfUNDA FINAL SCORE
# ====================================

def calculate_final_score(
    technical_score,
    fund_score,
    four_cylinder_score,
    canslim_score
):

    technical_part = (
        (technical_score or 0) / 100
    ) * 40

    fundamental_part = (
        (fund_score or 0) / 100
    ) * 35

    four_cyl_part = (
        (four_cylinder_score or 0) / 15
    ) * 15

    canslim_part = (
        (canslim_score or 0) / 10
    ) * 10

    total = (

        technical_part

        +

        fundamental_part

        +

        four_cyl_part

        +

        canslim_part

    )

    return round(total, 2)
    
# =====================================
# GET LAST SIGNAL
# =====================================

def get_last_signal(stock):

    conn = sqlite3.connect("signals.db")
    cursor = conn.cursor()

    cursor.execute("""

        SELECT signal_type
        FROM signals
        WHERE stock = ?
        ORDER BY id DESC
        LIMIT 1

    """, (stock,))

    row = cursor.fetchone()

    conn.close()

    if row:
        return row[0]

    return None  
# ====================================
# SCANNER FUNCTION
# ====================================

def scan_market():

    print("Inside scan_market() ✅")
    print(f"Total Stocks = {len(stocks)}")

    global sector_data
    
    global momentum_data
    
    global stock_analysis_data

    #print("Inside scan_market() ✅")

    #print(f"Total Stocks: {len(stocks)}")

    #print("Checking market hours...")

    #print("Scanner Time Started ✅")

    scanner_status["last_scan"] = datetime.now(IST).strftime("%d-%m-%Y %I:%M:%S %p")

    scanner_status["stocks_scanned"] = len(stocks)

    #print("Market Timing Disabled ✅")

    momentum_rankings = []

    sector_scores = {}

    sector_avg_lookup = {}

    stock_analysis_data.clear()
    
    # ====================================
    # NIFTY DATA DOWNLOAD
    # ====================================
    
    market_trend = "NEUTRAL"
    nifty_close = 0
    df_nifty = pd.DataFrame()
    
    try:    
        time.sleep(2)

        df_nifty = yf.download(
            "^NSEI",
            period="6mo",
            interval="1d",
            progress=False,
            auto_adjust=True,
            threads=False
        )
    
    except Exception as e:

        print(f"NIFTY Download Error ❌ : {e}")

        df_nifty = pd.DataFrame()

        # ====================================
        # PROCESS NIFTY DATA
        # ====================================
    
        if df_nifty is None or df_nifty.empty:
    
            print("NIFTY dataframe empty ⚠️")
    
        else:
    
            # MULTIINDEX FIX
    
            if isinstance(
                df_nifty.columns,
                pd.MultiIndex
            ):
    
                df_nifty.columns = (
                    df_nifty.columns
                    .droplevel(1)
                )
    
            # CLEAN DATA
    
            df_nifty = (
                df_nifty
                .dropna(subset=["Close"])
                .ffill()
            )
    
            # ====================================
            # NIFTY FINAL CHECK
            # ====================================

            if not df_nifty.empty:

                latest_nifty = df_nifty.iloc[-1]

                nifty_close = float(
                    latest_nifty["Close"]
                )

                print(
                    f"NIFTY Close = {nifty_close}"
                )

            else:

                nifty_close = 0

                print(
                    "NIFTY unavailable ⚠️"
                )

            print("REACHED STOCK LOOP 🚀")
            print(f"Total Stocks = {len(stocks)}")
    # ====================================
    # STOCK LOOP
    # ====================================

    for stock in stocks:

        try:

            print(f"Scanning {stock} 🚀")

            # ====================================
            # FUNDAMENTAL UPDATE
            # ====================================

            try:

                symbol_clean = stock.replace(".NS", "")

                def load_fundamental_scores(symbol):

                        conn = sqlite3.connect("signals.db")
                        cursor = conn.cursor()

                        cursor.execute("""
                            SELECT
                                fundamental_score
                            FROM company_fundamentals
                            WHERE symbol=?
                        """, (symbol,))

                        row = cursor.fetchone()

                        conn.close()

                        if row:
                            return row[0]

                        return 0

                        fund_score = 0
                        technofunda_rank = 0
                    
                        if fundamental_needs_update(symbol_clean):

                            print(f"Updating Fundamentals: {symbol_clean}")

                            fund_data = fetch_fundamentals(symbol_clean)

                            print(
                                f"{symbol_clean} | "
                                f"PE={fund_data.get('pe_ratio')} | "
                                f"PB={fund_data.get('pb_ratio')} | "
                                f"PROFIT={fund_data.get('profit_growth')} | "
                                f"SALES={fund_data.get('sales_growth')}"
                            )

                        if fund_data:

                            fund_score = calculate_fundamental_score(
                                fund_data,
                                locals().get(
                                    "latest_rs_daily",
                                    0
                                )
                            )

                            fund_data["fundamental_score"] = fund_score

                            technofunda_rank = calculate_technofunda_rank(
                                locals().get(
                                    "technical_score",
                                    0
                                ),
                                fund_score
                            )

                            fund_data[
                                "technofunda_rank"
                            ] = technofunda_rank

                            save_fundamentals(
                                symbol_clean,
                                fund_data
                            )

                            # ======================
                            # ADD THIS HERE
                            # ======================

                            if fund_data:
                                earnings_score = calculate_earnings_score(
                                    fund_data
                                )
                            else:
                                earnings_score = 0

                            machine_score = calculate_machine_score(
                                fund_data
                            )

                            four_cylinder_score = calculate_four_cylinder_score(
                                fund_data
                            )

                            canslim_score = calculate_canslim_score(
                                fund_data,
                                locals().get("rs_daily", 0),
                                locals().get("volume_ratio", 0)
                            )        

                        else:

                            fund_score = load_fundamental_scores(
                                symbol_clean
                            )

                            technofunda_rank = calculate_technofunda_rank(
                                momentum_score
                                if "momentum_score" in locals()
                                else 0,
                                fund_score
                            )

                            print(
                                f"Updating Fundamentals: {symbol_clean}"
                            )

                            fund_data = fetch_fundamentals(
                                symbol_clean
                            )
                            if not fund_data:
                                print(
                                    f"NO FUNDAMENTALS: {symbol_clean}"
                                )

                            # ----------------------
                            # SCORE + SAVE
                            # ----------------------

                        if fund_data:

                            # -----------------
                            # FUND SCORE
                            # -----------------

                            fund_score = (
                                calculate_fundamental_score(
                                    fund_data,
                                    locals().get(
                                        "latest_rs_daily",
                                        0
                                    )
                                )
                            )

                            fund_data[
                                "fundamental_score"
                            ] = fund_score

                            print(
                                f"Fundamental Score: {fund_score}"
                            )

                            # -----------------
                            # TECHNOFUNDA RANK
                            # -----------------

                            technofunda_rank = (
                                calculate_technofunda_rank(
                                    locals().get(
                                        "technical_score",
                                        0
                                    ),
                                    fund_score
                                )
                            )

                            print(
                                f"Technofunda Rank: {technofunda_rank}"
                            )

                            # =====================
                            # TEMP RANKING SCORES
                            # =====================
                            market_score = 0
                            
                            sector_rs = 0

                            for s in sector_data:

                                if s["sector"] == sector:

                                    sector_rs = round(
                                        (s["avg_score"] / 100) * 10,
                                        2
                                    )

                                    break
                            earnings_score = calculate_earnings_score(
                                fund_data
                            )

                            
                            demand_score = 0
                                        
                            four_cylinder_score = calculate_four_cylinder_score(
                                fund_data
                            )

                            
                            sector_avg = 0
                            sector_rs = 0
                            
                            for s in sector_data:
                            
                                if s["sector"] == sector:
                            
                                    sector_avg = s["avg_score"]
                            
                                    sector_rs = round(
                                        (sector_avg / 100) * 10,
                                        2
                                    )
                            
                                    break

                            machine_score = calculate_machine_score(

                                fund_data,

                                locals().get("rs_daily", 0),

                                locals().get("volume_ratio", 0),

                                sector_avg

                            )
                            
                            valuation_score = calculate_valuation_score(
                                fund_data
                            )
                            
                            canslim_score = calculate_canslim_score(
                                fund_data,
                                locals().get("rs_daily", 0),
                                locals().get("volume_ratio", 0)
                            )
                            
                            orders_score = 0
                            
                            news_score = 0
                            sentiment_score = 0

                            technical_score = round(
                                technofunda_rank,
                                2
                            )                        

                            fund_display = round(
                                (fund_score / 100) * 7,
                                2
                            )

                            tech_display = round(
                                (technical_score / 100) * 5,
                                2
                            )                        

                            phase6_score = round(

                                (
                                    technical_score * 0.40
                                )

                                +

                                (
                                    fund_score * 0.35
                                )

                                +

                                four_cylinder_score

                                +

                                canslim_score,

                                2
                            )
                            #======================
                            #Display Total
                            #=====================
                            
                            display_total = round(

                                sector_rs +

                                demand_score +

                                earnings_score +

                                four_cylinder_score +

                                machine_score +

                                canslim_score +

                                orders_score +

                                fund_display +

                                valuation_score +

                                tech_display +

                                news_score +

                                sentiment_score,

                                2
                            )

                            total_score = phase6_score

                            final_score = round(

                                (sector_rs / 10) * 10 +

                                (demand_score / 12) * 10 +

                                (earnings_score / 12) * 15 +

                                (four_cylinder_score / 12) * 15 +

                                (machine_score / 10) * 10 +

                                (canslim_score / 10) * 10 +

                                (orders_score / 8) * 8 +

                                (fund_display / 7) * 8 +

                                (valuation_score / 5) * 5 +

                                (tech_display / 5) * 5 +

                                (news_score / 3) * 2 +

                                (sentiment_score / 2) * 2,

                                2
                            )
                            # ==========================
                            # RATING
                            # ==========================

                            if final_score >= 70:
                                rating = "🏆 Elite"

                            elif final_score >= 60:
                                rating = "🟢 Strong Buy"

                            elif final_score >= 50:
                                rating = "👀 Watchlist"

                            elif final_score >= 35:
                                rating = "⚠️ Accumulate"

                            else:
                                rating = "❌ Avoid"
                            
                            # store in dict
                            fund_data[
                                "technofunda_rank"
                            ] = technofunda_rank

                            save_fundamentals(
                                symbol_clean,
                                fund_data
                            )
                            
            except Exception as e:

                print(
                    f"Fundamental update failed {stock}: {e}"
                )

            # =========================
            # 1H DOWNLOAD
            # =========================

            df_1h = yf.download(
                stock,
                period="3mo",
                interval="1h",
                progress=False
            )

            if isinstance(
                df_1h.columns,
                pd.MultiIndex
            ):
                df_1h.columns = (
                    df_1h.columns
                    .droplevel(1)
                )

            # CLEAN

            df_1h = (
                df_1h
                .dropna(
                    subset=[
                        "Close",
                        "High",
                        "Low"
                    ]
                )
                .ffill()
            )
            # =========================
            # REMOVE HOLIDAY / ZERO VOL ROWS
            # =========================

            df_1h = df_1h[

                df_1h["Volume"] > 0

            ].copy()

            # =========================
            # DAILY DOWNLOAD
            # =========================

            df_daily = yf.download(
                stock,
                period="6mo",
                interval="1d",
                progress=False
            )

            if isinstance(
                df_daily.columns,
                pd.MultiIndex
            ):
                df_daily.columns = (
                    df_daily.columns
                    .droplevel(1)
                )

            df_daily = (
                df_daily
                .dropna(
                    subset=[
                        "Close",
                        "High",
                        "Low"
                    ]
                )
                .ffill()
            )

            # =========================
            # REMOVE HOLIDAY / ZERO VOL ROWS
            # =========================

            df_daily = df_daily[

                df_daily["Volume"] > 0

            ].copy()

            # =========================
            # WEEKLY DOWNLOAD
            # =========================

            df_weekly = yf.download(
                stock,
                period="2y",
                interval="1wk",
                progress=False
            )

            if isinstance(
                df_weekly.columns,
                pd.MultiIndex
            ):
                df_weekly.columns = (
                    df_weekly.columns
                    .droplevel(1)
                )

            df_weekly = (
                df_weekly
                .dropna(
                    subset=[
                        "Close",
                        "High",
                        "Low"
                    ]
                )
                .ffill()
            )

            #print(f"{stock} downloaded ✅") #yes
            
            timeframes = [df_1h, df_daily, df_weekly]

            for df in timeframes:

                if isinstance(df.columns, pd.MultiIndex):

                    df.columns = df.columns.droplevel(1)
                

            
            # ====================================
            # VALIDATE DATA
            # ====================================

            if (
                df_1h.empty
                or
                df_daily.empty
                or
                df_weekly.empty
            ):

                #print(f"{stock} empty dataframe ❌")

                continue
            # ======================================
            # CALCULATE INDICATORS
            # ======================================
            
            for df in timeframes:

                # EMA

                df["EMA10"] = df["Close"].ewm(span=10).mean()

                df["EMA20"] = df["Close"].ewm(span=20).mean()

                df["EMA50"] = df["Close"].ewm(span=50).mean()

                # ====================================
                # CALCULATE RSI
                # ====================================

                df_1h = calculate_rsi(df_1h)

                df_daily = calculate_rsi(df_daily)

                df_weekly = calculate_rsi(df_weekly)
                
                # VOLUME

                df["VOL_MA"] = df["Volume"].rolling(20).mean()

                df["VOL_RATIO"] = (

                    df["Volume"] / df["VOL_MA"]

                )

                # ATR

                df["H-L"] = (

                    df["High"] - df["Low"]

                )

                df["H-PC"] = abs(

                    df["High"] - df["Close"].shift(1)

                )

                df["L-PC"] = abs(

                    df["Low"] - df["Close"].shift(1)

                )

                df["TR"] = df[

                    ["H-L", "H-PC", "L-PC"]

                ].max(axis=1)

                df["ATR"] = (

                    df["TR"]

                    .rolling(14)

                    .mean()

                )                
                # ====================================
                # DONCHIAN CHANNEL
                # ====================================

                df["DC_UPPER"] = (

                    df["High"]

                    .rolling(20)

                    .max()

                )

                df["DC_LOWER"] = (

                    df["Low"]

                    .rolling(20)

                    .min()

                )
                # ====================================
                # ADX
                # ====================================

                plus_dm = df["High"].diff()
                minus_dm = -df["Low"].diff()

                plus_dm[plus_dm < 0] = 0
                minus_dm[minus_dm < 0] = 0

                tr1 = df["High"] - df["Low"]
                tr2 = abs(df["High"] - df["Close"].shift(1))
                tr3 = abs(df["Low"] - df["Close"].shift(1))

                tr = pd.concat(
                    [tr1, tr2, tr3],
                    axis=1
                ).max(axis=1)

                atr_adx = tr.rolling(14).mean()

                plus_di = (
                    100 *
                    (
                        plus_dm.rolling(14).mean()
                        /
                        atr_adx
                    )
                )

                minus_di = (
                    100 *
                    (
                        minus_dm.rolling(14).mean()
                        /
                        atr_adx
                    )
                )

                dx = (
                    abs(plus_di - minus_di)
                    /
                    (plus_di + minus_di)
                ) * 100

                df["ADX"] = dx.rolling(14).mean()
                               
            # ====================================
            # SAFE LATEST CANDLES
            # ====================================

            hourly_clean = (
                df_1h
                .dropna()
            )

            if hourly_clean.empty:

                #print(
                #    f"{stock} 1H empty ❌"
                #)

                continue

            latest_1h = (
                hourly_clean
                .iloc[-1]
            )

            daily_clean = (
                df_daily
                .dropna()
            )

            if daily_clean.empty:

                #print(
                #    f"{stock} daily empty ❌"
                #)

                continue

            latest_daily = (
                daily_clean
                .iloc[-1]
            )

            weekly_clean = (
                df_weekly
                .dropna()
            )

            if weekly_clean.empty:

                print(
                    f"{stock} weekly empty ❌"
                )

                continue

            latest_weekly = (
                weekly_clean
                .iloc[-1]
            )

            
            # ====================================
            # SAFE NIFTY CHECK
            # ====================================           
            
            
            adx_1h = latest_1h["ADX"]
            adx_daily = latest_daily["ADX"]
            adx_weekly = latest_weekly["ADX"]
                        
            hourly_status = get_trade_status(

                stock,
                "1H"

            )

            daily_status = get_trade_status(

                stock,
                "DAILY"

            )

            weekly_status = get_trade_status(

                stock,
                "WEEKLY"

            )

            if weekly_status[0]:

                status = weekly_status[0]

            elif daily_status[0]:

                status = daily_status[0]

            elif hourly_status[0]:

                status = hourly_status[0]

            else:

                status = "NONE"
            sector = sector_map.get(
                stock,
                "Unknown"
            )  
            # ====================================
            # SECTOR SCORE COLLECTION
            # ====================================

            if sector not in sector_scores:

                sector_scores[sector] = {

                    "total_score": 0,
                    "count": 0,
                    "stock_count": 0,
                    "strong_count": 0

                }

            prev_1h = df_1h.iloc[-2]
            # ====================================
            # EMA ALIGNMENT
            # ====================================

            # DAILY

            ema_alignment_daily = (

                latest_daily["EMA10"]
                >
                latest_daily["EMA20"]

                and

                latest_daily["EMA20"]
                >
                latest_daily["EMA50"]

            )

            # WEEKLY

            ema_alignment_weekly = (

                latest_weekly["EMA10"]
                >
                latest_weekly["EMA20"]

                and

                latest_weekly["EMA20"]
                >
                latest_weekly["EMA50"]

            )
            # ====================================
            # WEEKLY NIFTY
            # ====================================

            df_nifty_weekly = yf.download(
                "^NSEI",
                period="2y",
                interval="1wk",
                progress=False

            )

            if isinstance(
                df_nifty_weekly.columns,
                pd.MultiIndex
            ):
                df_nifty_weekly.columns = (
                    df_nifty_weekly.columns
                    .droplevel(1)
                )

            nifty_weekly_close = (
                df_nifty_weekly["Close"]
                .reindex(df_weekly.index)
                .ffill()
            )
            # ====================================
            # SAFE NIFTY DAILY CLOSE
            # ====================================
            
            if df_nifty.empty:
            
                print(
                    f"NIFTY unavailable - skipping RS for {stock} ⚠️"
                )
            
                rs_daily = 0
                rs_weekly = 0
            
                continue
            
            nifty_daily_close = (
                df_nifty["Close"]
                .reindex(df_daily.index)
                .ffill()
            )

            if isinstance(
                nifty_daily_close,
                pd.DataFrame
            ):
                nifty_daily_close = nifty_daily_close.iloc[:,0]

            stock_return = (
                df_daily["Close"]
                /
                df_daily["Close"].shift(55)
            )

            nifty_return = (
                nifty_daily_close
                /
                nifty_daily_close.shift(55)
            )

            df_daily["RS"] = (
                stock_return
                /
                nifty_return
            ) - 1

            df_daily["RS_MA"] = (
                df_daily["RS"]
                .rolling(10)
                .mean()
            )

            # ====================================
            # WEEKLY RS
            # ====================================

            df_weekly["RS_W"] = (
                (
                    df_weekly["Close"]
                    /
                    df_weekly["Close"].shift(52)
                )
                /
                (
                    nifty_weekly_close
                    /
                    nifty_weekly_close.shift(52)
                )
            ) - 1

            df_weekly["RS_W_MA"] = (
                df_weekly["RS_W"]
                .rolling(10)
                .mean()
            )

            #print(
            #    "RS DEBUG:",
            #   stock,
            #    df_daily["RS"].tail(5)
            #)
            #print(
            #    "RSW DEBUG:",
            #    stock,
            #   df_weekly["RS_W"].tail(5)
            #)

            # ====================================
            # LATEST RS VALUES
            # ====================================

            latest_rs_daily = (
                df_daily["RS"]
                .ffill()
                .iloc[-1]
            )

            previous_rs_daily = (
                df_daily["RS"]
                .ffill()
                .iloc[-5]
            )

            latest_rs_daily_ma = (
                df_daily["RS_MA"]
                .ffill()
                .iloc[-1]
            )

            previous_rs_daily_ma = (
                df_daily["RS_MA"]
                .ffill()
                .iloc[-5]
            )

            latest_rs_weekly = (
                df_weekly["RS_W"]
                .ffill()
                .iloc[-1]
            )

            previous_rs_weekly = (
                df_weekly["RS_W"]
                .ffill()
                .iloc[-5]
            )

            latest_rs_weekly_ma = (
                df_weekly["RS_W_MA"]
                .ffill()
                .iloc[-1]
            )

            previous_rs_weekly_ma = (
                df_weekly["RS_W_MA"]
                .ffill()
                .iloc[-5]
            )

            # ====================================
            # RS CONDITIONS BY TIMEFRAME
            # ====================================

            # ----- DAILY RS -----

            rs_daily_positive = (
                latest_rs_daily > 0
            )

            rs_daily_rising = (

                latest_rs_daily_ma
                >
                previous_rs_daily_ma

            )

            rs_daily_falling = (
                latest_rs_daily
                <
                previous_rs_daily
            )

            rs_daily_slope_up = (
                latest_rs_daily_ma
                >
                previous_rs_daily_ma
            )

            rs_daily_slope_down = (
                latest_rs_daily_ma
                <
                previous_rs_daily_ma
            )

            # ----- WEEKLY RS -----

            rs_weekly_positive = (
                latest_rs_weekly > 0
            )

            rs_weekly_rising = (

                latest_rs_weekly_ma
                >
                previous_rs_weekly_ma

            )

            rs_weekly_falling = (
                latest_rs_weekly
                <
                previous_rs_weekly
            )

            rs_weekly_slope_up = (
                latest_rs_weekly_ma
                >
                previous_rs_weekly_ma
            )

            rs_weekly_slope_down = (
                latest_rs_weekly_ma
                <
                previous_rs_weekly_ma
            )

            # ====================================
            # FINAL RS FILTER BY TIMEFRAME
            # ====================================

            # ----- DAILY -----

            rs_positive_daily = (
                rs_daily_positive
            )

            rs_rising_daily = (
                rs_daily_rising
            )

            rs_falling_daily = (
                rs_daily_falling
            )

            rs_slope_up_daily = (
                rs_daily_slope_up
            )

            rs_slope_down_daily = (
                rs_daily_slope_down
            )

            # ----- WEEKLY -----

            rs_positive_weekly = (
                rs_weekly_positive
            )

            rs_rising_weekly = (
                rs_weekly_rising
            )

            rs_falling_weekly = (
                rs_weekly_falling
            )

            rs_slope_up_weekly = (
                rs_weekly_slope_up
            )

            rs_slope_down_weekly = (
                rs_weekly_slope_down
            )

            # ====================================
            # PRINT RS
            # ====================================

            #print(
            #    f"RS(D)={round(float(latest_rs_daily),3)} "
            #    f"| D_Pos={rs_positive_daily} "
            #    f"| D_Rising={rs_daily_rising}"
            #)

            #print(
            #    f"RS(W)={round(float(latest_rs_weekly),3)} "
            #    f"| W_Pos={rs_positive_weekly} "
            #   f"| W_Rising={rs_weekly_rising}"
            #)

            
            
            # ATR Stoploss
            hourly_atr = latest_1h["ATR"]

            daily_atr = latest_daily["ATR"]

            weekly_atr = latest_weekly["ATR"]
            
            hourly_sl = (

                latest_1h["Close"]

                -

                (hourly_atr * 1.5)

            )
            daily_sl = (

                latest_daily["Close"]

                -

                (daily_atr * 1.8)

            )
            weekly_sl = (

                latest_weekly["Close"]

                -

                (weekly_atr * 1.8)

            )
            hourly_sl = round(float(hourly_sl), 2)

            daily_sl = round(float(daily_sl), 2)

            weekly_sl = round(float(weekly_sl), 2)

            #=== DC Breakout============
            
            latest_1h["Close"] > latest_1h["DC_UPPER"]

            latest_daily["Close"] > latest_daily["DC_UPPER"]

            latest_weekly["Close"] > latest_weekly["DC_UPPER"]

            df["DC_UPPER"] = (
                df["High"]
                .shift(1)
                .rolling(20)
                .max()
            )

            df["DC_LOWER"] = (
                df["Low"]
                .shift(1)
                .rolling(20)
                .min()
            )
            dc_breakout_1h = (
                min(
                    latest_1h["Open"],
                    latest_1h["Close"]
                )
                >
                latest_1h["DC_UPPER"] * 1.01
            )
            dc_breakout_daily = (
                min(
                    latest_daily["Open"],
                    latest_daily["Close"]
                )
                >
                latest_daily["DC_UPPER"] * 1.01
            )
            dc_breakout_weekly = (
                min(
                    latest_weekly["Open"],
                    latest_weekly["Close"]
                )
                >
                latest_weekly["DC_UPPER"] * 1.01
            )
            #===============================
            #           Breakout
            #================================

            hourly_breakout = (

                latest_1h["Close"]

                >

                df_1h["High"].iloc[-2]

            )

            daily_breakout = (

                latest_daily["Close"]

                >

                df_daily["High"].iloc[-2]

            )
            

            weekly_breakout = (

                latest_weekly["Close"]

                >

                df_weekly["High"].iloc[-2]

            )

           
            # ======================================
            # PRINT VALUES
            # ======================================

            #print("\n" + "="*50)

            print(stock)
            
            #print(
            #    f"RSI 1H={round(float(latest_1h["RSI"]), 2)} "
            #    f"| D={round(float(latest_daily["RSI"]), 2)} "
            #    f"| W={round(float(latest_weekly["RSI"]), 2)}"
            #)
            #print(
            #    f"ADX 1H={round(float(adx_1h),2)} "
            #    f"| D={round(float(adx_daily),2)} "
            #    f"| W={round(float(adx_weekly),2)}"
            #)
            
            # =====================================
            # TIMEFRAME EMA + ATR
            # =====================================

            # HOURLY
            ema10_h = round(
                df_1h["Close"].ewm(span=10).mean().iloc[-1],
                2
            )

            ema20_h = round(
                df_1h["Close"].ewm(span=20).mean().iloc[-1],
                2
            )

            ema50_h = round(
                df_1h["Close"].ewm(span=50).mean().iloc[-1],
                2
            )

            atr_h = round(
                df_1h["ATR"].iloc[-1],
                2
            )

            # DAILY
            ema10_d = round(
                df_daily["Close"].ewm(span=10).mean().iloc[-1],
                2
            )

            ema20_d = round(
                df_daily["Close"].ewm(span=20).mean().iloc[-1],
                2
            )

            ema50_d = round(
                df_daily["Close"].ewm(span=50).mean().iloc[-1],
                2
            )

            ema50_d = round(
                df_daily["Close"].ewm(span=50).mean().iloc[-1],
                2
            )

            atr_d = round(
                df_daily["ATR"].iloc[-1],
                2
            )

            # WEEKLY
            ema10_w = round(
                df_weekly["Close"].ewm(span=10).mean().iloc[-1],
                2
            )

            ema20_w = round(
                df_weekly["Close"].ewm(span=20).mean().iloc[-1],
                2
            )

            ema50_w = round(
                df_weekly["Close"].ewm(span=50).mean().iloc[-1],
                2
            )

            atr_w = round(
                df_weekly["ATR"].iloc[-1],
                2
            )
            
            # ====================================
            # UPPER WICK %
            # ====================================

            # HOURLY

            hourly_high = df_1h["High"].iloc[-1]
            hourly_low = df_1h["Low"].iloc[-1]
            hourly_open = df_1h["Open"].iloc[-1]
            hourly_close = df_1h["Close"].iloc[-1]

            hourly_range = hourly_high - hourly_low

            if hourly_range > 0:

                hourly_wick_pct = (

                    (
                        hourly_high
                        -
                        max(
                            hourly_open,
                            hourly_close
                        )
                    )

                    /

                    hourly_range

                ) * 100

            else:

                hourly_wick_pct = 0


            # DAILY

            daily_high = df_daily["High"].iloc[-1]
            daily_low = df_daily["Low"].iloc[-1]
            daily_open = df_daily["Open"].iloc[-1]
            daily_close = df_daily["Close"].iloc[-1]

            daily_range = daily_high - daily_low

            if daily_range > 0:

                daily_wick_pct = (

                    (
                        daily_high
                        -
                        max(
                            daily_open,
                            daily_close
                        )
                    )

                    /

                    daily_range

                ) * 100

            else:

                daily_wick_pct = 0


            # WEEKLY

            weekly_high = df_weekly["High"].iloc[-1]
            weekly_low = df_weekly["Low"].iloc[-1]
            weekly_open = df_weekly["Open"].iloc[-1]
            weekly_close = df_weekly["Close"].iloc[-1]

            weekly_range = weekly_high - weekly_low

            if weekly_range > 0:

                weekly_wick_pct = (

                    (
                        weekly_high
                        -
                        max(
                            weekly_open,
                            weekly_close
                        )
                    )

                    /

                    weekly_range

                ) * 100

            else:

                weekly_wick_pct = 0
            
            # ====================================
            # COMMON ANALYSIS VALUES
            # ====================================

            daily_close = float(latest_daily["Close"])

            rsi = float(latest_daily["RSI"])

            adx = float(latest_daily["ADX"])

            rs_daily = float(latest_rs_daily)

            rs_weekly = float(latest_rs_weekly)

            volume_ratio = float(latest_1h["VOL_RATIO"])

            ema10 = float(latest_daily["EMA10"])
            ema20 = float(latest_daily["EMA20"])
            ema50 = float(latest_daily["EMA50"])            
            
            # ====================================
            # WICK FILTER
            # ====================================           
            hourly_wick_filter = (

                hourly_wick_pct > 30

                or

                (
                    hourly_wick_pct > 25
                    and
                    volume_ratio < 3
                )
            ) 
            daily_wick_filter = (

                daily_wick_pct > 30

                or

                (
                    daily_wick_pct > 25
                    and
                    volume_ratio < 3
                )
            )
            weekly_wick_filter = (

                weekly_wick_pct > 30

                or

                (
                    weekly_wick_pct > 25
                    and
                    volume_ratio < 3
                )
            )                        
            # ======================================
            # MULTI TIMEFRAME CONDITIONS
            # ======================================
            
            # =====================================
            # TRADE STATUS
            # =====================================

            # HOURLY

            (
                hourly_status,
                hourly_entry,
                hourly_signal
            ) = get_trade_status(

                stock,
                "1H"

            )

            # DAILY

            (
                daily_status,
                daily_entry,
                daily_signal
            ) = get_trade_status(

                stock,
                "DAILY"

            )

            # WEEKLY

            (
                weekly_status,
                weekly_entry,
                weekly_signal
            ) = get_trade_status(

                stock,
                "WEEKLY"

            )   
            # ======================================
            # HOURLY CONDITIONS
            # ======================================

            hourly_buy = (

                latest_1h["Close"]

                >

                latest_1h["EMA10"]

                and

                latest_1h["Close"]

                >

                latest_1h["EMA50"]

                and

                latest_1h["EMA10"]

                >

                latest_1h["EMA20"]
                
                >

                latest_1h["EMA50"]

                and

                latest_1h["RSI"]

                >

                75

                and
                
                hourly_breakout
                

                and

                latest_1h["VOL_RATIO"]

                >

                1.5

                and

                adx_1h > 25

                and 
                
                df_1h['Close'].iloc[-1] > df_1h['Open'].iloc[-1]

                and 
                
                df_1h['Close'].iloc[-1] > df_1h['Close'].iloc[-2]

                and

                not hourly_wick_filter

            )

            hourly_add = (

                hourly_status == "ACTIVE"

                and

                dc_breakout_1h

                and

                latest_1h["VOL_RATIO"]

                >

                1.1



            )
          

            hourly_sell = (

                hourly_status == "ACTIVE"

                and

                (

                    latest_1h["Close"]

                    <

                    hourly_sl

                    or

                    latest_1h["Close"]

                    <

                    latest_1h["EMA10"]

                )

            )

            daily_breakout = (

                latest_daily["Close"]

                >

                df_daily["High"].iloc[-2]

            )
            
                # ======================================
                # DAILY CONDITIONS
                # ======================================

            daily_buy = (

                latest_daily["Close"]

                >

                latest_daily["EMA10"]

                and

                latest_daily["Close"]

                >

                latest_daily["EMA50"]

                and

                latest_daily["EMA10"]
                
                >

                latest_daily["EMA50"]

                and

                latest_daily["RSI"]

                >

                60

                and
                
                daily_breakout

                and

                rs_positive_daily
                
                and

                rs_rising_daily

                and

                latest_daily["VOL_RATIO"]

                >

                1.2

                and

                adx_daily > 20

                and 
                
                df_daily['Close'].iloc[-1] > df_daily['Open'].iloc[-1]
                
                and

                df_daily['Close'].iloc[-1] > df_daily['Close'].iloc[-2]
                
                and

                not daily_wick_filter 

            )

            daily_add = (

                daily_status == "ACTIVE"

                and

                dc_breakout_daily

                and

                rs_positive_daily

                and
                
                rs_rising_daily

                and

                latest_daily["VOL_RATIO"]

                >

                1.0

            )

            daily_sell = (

                daily_status == "ACTIVE"

                and

                (

                    latest_daily["Close"]

                    <

                    daily_sl

                    or

                    latest_daily["Close"]

                    <

                    latest_daily["EMA10"]

                )

            )
           # print(
            #    stock,
             #   "W_CLOSE=", latest_weekly["Close"],
              #  "PREV_HIGH=", df_weekly["High"].iloc[-2],
            #    "W_BREAKOUT=", weekly_breakout,
             #   "RSI=", latest_weekly["RSI"],
            #    "EMA10>", latest_weekly["EMA10"] > latest_weekly["EMA50"],
             #   "RS_POS=", rs_positive_weekly,
              #  "RS_RISE=", rs_rising_weekly
            #)
                # ======================================
                # WEEKLY CONDITIONS
                # ======================================

            weekly_buy = (

                latest_weekly["Close"]

                >

                latest_weekly["EMA10"]

                and

                latest_weekly["Close"]

                >

                latest_weekly["EMA50"]

                and

                latest_weekly["EMA10"]
                
                >

                latest_weekly["EMA50"]                

                and

                latest_weekly["RSI"]

                >

                65

                and

                
                weekly_breakout

                and

                rs_positive_weekly

                and

                rs_rising_weekly

                and

                latest_weekly["VOL_RATIO"]

                >

                1.2

                and

                adx_daily > 20

                and 
                
                df_weekly['Close'].iloc[-1] > df_weekly['Open'].iloc[-1]
                
                and 
                
                df_weekly['Close'].iloc[-1] > df_weekly['Close'].iloc[-2]

                and

                not weekly_wick_filter


            )
            
            weekly_add = (

                weekly_status == "ACTIVE"

                and

                dc_breakout_weekly

                and

                rs_positive_weekly

                and

                rs_rising_weekly

                and

                latest_weekly["VOL_RATIO"]

                >

                1.0

                

            )

            weekly_sell = (

                weekly_status == "ACTIVE"

                and

                (

                    latest_weekly["Close"]

                    <

                    weekly_sl

                    or

                    latest_weekly["Close"]

                    <

                    latest_weekly["EMA10"]

                )

            )   
            # ======================================

           # momentum_score = 0

            # ======================================
            # PHASE-4 SMART TECHNOfUNDA SCORE (0-100)
            # ======================================

            trend_score = 0
            momentum_score_part = 0
            adx_score = 0
            breakout_score = 0
            signal_score = 0
            risk_score = 0
            
            # ====================================
            # 1 TREND SCORE (0-20)
            # ====================================

            if ema_alignment_daily:
                trend_score += 10

            if ema_alignment_weekly:
                trend_score += 10

            # ====================================
            # 2 MOMENTUM SCORE (0-20)
            # ====================================

            # DAILY RS
            if rs_positive_daily:
                momentum_score_part += 5

            if rs_rising_daily:
                momentum_score_part += 5

            # WEEKLY RS
            if rs_positive_weekly:
                momentum_score_part += 5

            if rs_rising_weekly:
                momentum_score_part += 5

            # RSI QUALITY
            rsi_daily = float(latest_daily["RSI"])

            if 55 <= rsi_daily <= 75:
                momentum_score_part += 5
            elif rsi_daily > 75:
                momentum_score_part += 2
            elif rsi_daily < 45:
                momentum_score_part -= 5

            momentum_score_part = min(
                20,
                momentum_score_part
            )

            # ====================================
            # 3 ADX SCORE (0-10)
            # ====================================

            if adx_daily > 25:
                adx_score += 5

            if adx_weekly > 25:
                adx_score += 5

            # ====================================
            # 4 BREAKOUT + VOLUME (0-20)
            # ====================================

            if daily_breakout:
                breakout_score += 5

            if weekly_breakout:
                breakout_score += 5

            if dc_breakout_daily:
                breakout_score += 5

            if float(latest_daily["VOL_RATIO"]) > 1.5:
                breakout_score += 5
                

            # ====================================
            # 5 SIGNAL QUALITY (0-20)
            # ====================================

            if hourly_buy:
                signal_score += 4

            if daily_buy:
                signal_score += 8

            if weekly_buy:
                signal_score += 8

            if daily_add:
                signal_score += 4

            if weekly_add:
                signal_score += 4

            signal_score = min(
                20,
                signal_score
            )

            # ====================================
            # 6 RISK SCORE (0-10)
            # ====================================

            risk_pct = (
                float(atr_d)
                /
                float(latest_daily["Close"])
            ) * 100

            if risk_pct < 2:
                risk_score = 10
            elif risk_pct < 4:
                risk_score = 6
            else:
                risk_score = 2

            # ====================================
            # FINAL SCORE
            # ====================================

            momentum_score = (

                trend_score

                +

                momentum_score_part

                +

                adx_score

                +

                breakout_score

                +

                signal_score

                +

                risk_score

            )

            # ====================================
            # SECTOR FILTER
            # ====================================

            sector_avg = sector_avg_lookup.get(
                sector,
                50
            )

            # STRONG SECTOR BONUS

            if sector_avg >= 75:

                momentum_score += 10

            elif sector_avg >= 60:

                momentum_score += 5

            # WEAK SECTOR PENALTY

            elif sector_avg < 45:

                momentum_score -= 10

            # NEGATIVE CONDITIONS

            if rs_falling_daily:
                momentum_score -= 5

            if rs_falling_weekly:
                momentum_score -= 5

            if (
                hourly_sell
                or
                daily_sell
                or
                weekly_sell
            ):
                momentum_score -= 15

            momentum_score = max(
                0,
                min(
                    100,
                    momentum_score
                )
            ) 

            # ==========================
            # LOAD FUNDAMENTAL SCORE
            # ==========================

            fund_score = load_fundamental_scores(
                symbol_clean
            )

            #print(
            #    f"{symbol_clean} Fund Score={fund_score}"
            #)

            #=================================

            technical_score = momentum_score

            technofunda_rank = (
                calculate_technofunda_rank(
                    technical_score,
                    fund_score
                )
            )

            
            # ==========================
            # LOAD FUNDAMENTAL DATA
            # ==========================

            fund_data = fetch_fundamentals(
                symbol_clean
            ) or {}

            if fund_data:

                four_cylinder_score = (
                    calculate_four_cylinder_score(
                        fund_data
                    )
                )

                canslim_score = (
                    calculate_canslim_score(
                        fund_data,
                        rs_daily,
                        volume_ratio
                    )
                )

            else:

                four_cylinder_score = 0
                canslim_score = 0

            
            # ==========================
            # DISPLAY SCORES
            # ==========================

            fund_display = round(
                (fund_score / 100) * 7,
                2
            )

            tech_display = round(
                (technical_score / 100) * 5,
                2
            )
            earnings_score = calculate_earnings_score(
                fund_data
            )            

            valuation_score = calculate_valuation_score(
                fund_data
            )
            print(
                f"{stock} | "
                f"PE={fund_data.get('pe_ratio')} | "
                f"PB={fund_data.get('pb_ratio')} | "
                f"VAL={valuation_score}"
            )
            print(
                f"{stock} Valuation Score={valuation_score}"
            )
            sector_avg = 0
            
            for s in sector_data:

                if s["sector"] == sector:

                    sector_avg = s["avg_score"]

                    sector_rs = round(
                        (sector_avg / 100) * 10,
                        2
                    )

                    break

            machine_score = calculate_machine_score(

                fund_data,

                locals().get("rs_daily", 0),

                locals().get("volume_ratio", 0),

                sector_avg

            )

            print(
                f"{stock} Machine Score={machine_score}"
            )
            
            print(
                f"{stock} Earnings Score={earnings_score}"
            )
            
            # ==========================
            # DEMAND SCORE (/12)
            # ==========================

            demand_score = 0

            # Volume

            if volume_ratio >= 2:
                demand_score += 4

            elif volume_ratio >= 1.5:
                demand_score += 3

            elif volume_ratio >= 1.2:
                demand_score += 2

            elif volume_ratio >= 1:
                demand_score += 1

            # Relative Strength

            if rs_daily >= 0.05:
                demand_score += 4

            elif rs_daily >= 0.03:
                demand_score += 3

            elif rs_daily >= 0.01:
                demand_score += 2

            elif rs_daily > 0:
                demand_score += 1

            # Breakout

            if daily_breakout:
                demand_score += 2

            # EMA Structure

            if ema_alignment_daily:
                demand_score += 2

            demand_score = min(
                demand_score,
                12
            )
            print(
                f"{stock} RS={rs_daily:.4f} VOL={volume_ratio:.2f} "
                f"BREAKOUT={daily_breakout} EMA={ema_alignment_daily}"
            )
            print(f"{stock} Demand Score={demand_score}")
           
            print(f"DEBUG {stock}")
            print(f"sector={sector}")
            print(f"sector_rs={locals().get('sector_rs', 'MISSING')}")
            # ==========================
            # DISPLAY TOTAL
            # ==========================          
            
            sector_rs = locals().get("sector_rs", 0)
            demand_score = locals().get("demand_score", 0)
            earnings_score = locals().get("earnings_score", 0)
            four_cylinder_score = locals().get("four_cylinder_score", 0)
            machine_score = locals().get("machine_score", 0)
            canslim_score = locals().get("canslim_score", 0)
            orders_score = locals().get("orders_score", 0)
            fund_display = locals().get("fund_display", 0)
            valuation_score = locals().get("valuation_score", 0)
            tech_display = locals().get("tech_display", 0)
            news_score = locals().get("news_score", 0)
            sentiment_score = locals().get("sentiment_score", 0)
            
            display_total = round(

                sector_rs +

                demand_score +

                earnings_score +

                four_cylinder_score +

                machine_score +

                canslim_score +

                orders_score +

                fund_display +

                valuation_score +

                tech_display +

                news_score +

                sentiment_score,

                2
            )

            final_score = round(

                (sector_rs / 10) * 10 +

                (demand_score / 12) * 10 +

                (earnings_score / 12) * 15 +

                (four_cylinder_score / 12) * 15 +

                (machine_score / 10) * 10 +

                (canslim_score / 10) * 10 +

                (orders_score / 8) * 8 +

                (fund_display / 7) * 8 +

                (valuation_score / 5) * 5 +

                (tech_display / 5) * 5 +

                (news_score / 3) * 2 +

                (sentiment_score / 2) * 2,

                2
            )
            print(
                f"{stock} | FINAL={final_score} | "
                f"TECH={tech_display} | "
                f"FUND={fund_display}"
            )
            
            # ======================
            # SAVE RANKING
            # ======================

            rating = get_rating(
                final_score
            )
            try:
                                                
                rank_conn = sqlite3.connect(
                    "signals.db"
                )

                rank_cursor = rank_conn.cursor()
                print(
                    f"SAVING {symbol_clean}: |"
                    f"earn={earnings_score} |"
                    f"4cyl={four_cylinder_score} | "
                    f"canslim={canslim_score} |"
                    f"machine={machine_score} | "
                    f"earn={earnings_score}"
                )
               
                rank_cursor.execute(
                    """
                    INSERT OR REPLACE INTO company_ranking
                    (
                        stock,
                        sector_rs,
                        demand_score,
                        earnings_score,
                        four_cylinder_score,
                        machine_score,
                        canslim_score,
                        orders_score,
                        fund_score,
                        fund_display,
                        valuation_score,
                        technical_score,
                        tech_display,
                        news_score,
                        sentiment_score,
                        total_score,
                        final_score,
                        rating,
                        updated_at
                    )
                    VALUES
                    (
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )
                    """,
                    (
                        symbol_clean,    #                            
                        sector_rs,
                        demand_score,
                        earnings_score,
                        four_cylinder_score,
                        machine_score,
                        canslim_score,
                        orders_score,
                        fund_score,  #
                        fund_display,
                        valuation_score,
                        technical_score,
                        tech_display,
                        news_score,
                        sentiment_score,
                        total_score,
                        final_score,
                        rating,
                        datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    )
                )

                rank_conn.commit()

            finally:

                rank_conn.close()

            # ====================================
            # GRADE SYSTEM
            # ====================================

            if momentum_score >= 90:
                grade = "A+"

            elif momentum_score >= 80:
                grade = "A"

            elif momentum_score >= 70:
                grade = "B+"

            elif momentum_score >= 60:
                grade = "B"

            elif momentum_score >= 50:
                grade = "C"

            else:
                grade = "AVOID" 

            # ====================================
            # WATCHLIST CATEGORY
            # ====================================

            if momentum_score >= 85:

                watch_category = "🚀 ELITE"

            elif momentum_score >= 70:

                watch_category = "📈 SWING"

            elif momentum_score >= 55:

                watch_category = "👀 WATCH"

            else:

                watch_category = "❌ AVOID"       

            # ====================================
            # MOMENTUM STATUS
            # ====================================

            if momentum_score >= 80:

                momentum_status = (
                    "🚀 Strong Trend"
                )

            elif momentum_score >= 65:

                momentum_status = (
                    "📈 Strong Swing Candidate"
                )

            elif momentum_score >= 50:

                momentum_status = (
                    "👀 Watchlist"
                )

            elif momentum_score >= 35:

                momentum_status = (
                    "⚠️ Weak"
                )

            else:

                momentum_status = (
                    "❌ Avoid"
                )

            print(f"Scanning {stock} 🚀")

            # ===================================
            # SAFE DEFAULT VALUES
            # ===================================

            category = watch_category
           

            if "fund_score" not in locals():
                fund_score = 0

            if "technofunda_rank" not in locals():
                technofunda_rank = 0

            if "grade" not in locals():
                grade = "C"

            if "category" not in locals():
                category = "WATCH"

            if "sector" not in locals():
                sector = "Unknown"

            if "signal_category" not in locals():
                signal_category = "NONE"        
        
            # ====================================
            # SAVE ALL STOCK ANALYSIS
            # ====================================

            save_stock_analysis(

                stock=stock,
                sector=sector,

                daily_close=float(latest_daily["Close"]),
                rsi=float(latest_daily["RSI"]),
                adx=float(adx_daily),

                rs_daily=float(latest_rs_daily),
                rs_weekly=float(latest_rs_weekly),

                volume_ratio=float(latest_daily["VOL_RATIO"]),

                ema10=float(latest_daily["EMA10"]),
                ema20=float(latest_daily["EMA20"]),
                ema50=float(latest_daily["EMA50"]),

                score=momentum_score,

                fund_score=fund_score,  

                technofunda_rank=float(technofunda_rank),
                final_score=final_score,
                rating=rating,

                earnings_score=earnings_score,
                four_cylinder_score=four_cylinder_score,
                machine_score=machine_score,
                canslim_score=canslim_score,
                valuation_score=valuation_score,
                demand_score=demand_score,

                sales_growth=fund_data.get("sales_growth", 0),
                profit_growth=fund_data.get("profit_growth", 0),
                eps_growth=fund_data.get("eps_growth", 0),

                roe=fund_data.get("roe", 0),
                roce=fund_data.get("roce", 0),
                debt_equity=fund_data.get("debt_equity", 0),

                pe_ratio=fund_data.get("pe_ratio", 0),
                pb_ratio=fund_data.get("pb_ratio", 0),

                status=momentum_status,
                signal="NONE",

                ema10_h=ema10_h,
                ema20_h=ema20_h,
                ema50_h=ema50_h,
                atr_h=hourly_sl,

                ema10_d=ema10_d,
                ema20_d=ema20_d,
                ema50_d=ema50_d,
                atr_d=daily_sl,

                ema10_w=ema10_w,
                ema20_w=ema20_w,
                ema50_w=ema50_w,
                atr_w=weekly_sl
            )
            # =========================
            # TF SIGNAL (Technofunda)
            # =========================

            if technofunda_rank < 10:
                tf_signal = "AVOID"

            elif technofunda_rank <= 20:
                tf_signal = "WATCH"

            else:
                tf_signal = "BUY"
            # ============================================
            # MOMENTUM DATA SAVE
            # ============================================

            momentum_data.append({

                "stock": stock,
                "sector": sector,
                "sector_score": 0,

                "price": round(daily_close, 2),

                "score": momentum_score,

                "rating": rating,

                "final_score": round(
                    final_score,
                    2
                ),

                "fund_score": fund_score,

                "technofunda_rank": round(
                    technofunda_rank, 2
                ),

                "grade": grade,
                "category": category,

                "tf_signal": tf_signal,
                "signal": signal_category,
                "status": str(status),

                # =================
                # RS
                # =================

                "rs_daily": round(rs_daily,2),
                "rs_weekly": round(rs_weekly,2),

                "rs":
                    f"D:{round(rs_daily,2)}\n"
                    f"W:{round(rs_weekly,2)}",

                "rs_status":
                    "RISING 📈"
                    if rs_daily > 0 and rs_weekly > 0
                    else "FALLING 📉",

                # =================
                # RSI
                # =================

                "hourly_rsi": round(
                    latest_1h["RSI"],2
                ),

                "daily_rsi": round(
                    latest_daily["RSI"],2
                ),

                "weekly_rsi": round(
                    latest_weekly["RSI"],2
                ),

                # =================
                # EMA
                # =================

                "ema10": round(ema10_d,2),
                "ema20": round(ema20_d,2),
                "ema50": round(ema50_d,2),

                # =================
                # ATR / SL
                # =================

                "hourly_sl": hourly_sl,
                "daily_sl": daily_sl,
                "weekly_sl": weekly_sl
            })
            
                # ======================================
                # HOURLY BUY
                # ======================================

            if hourly_buy and hourly_status is None:

                #print(f"🟢 HOURLY BUY: {stock}")

                save_signal(

                    stock=stock,
                    signal_type="HOURLY BUY",
                    price=float(latest_1h["Close"]),
                    rsi=float(latest_1h["RSI"]),
                    volume_ratio=float(latest_1h["VOL_RATIO"]),
                    timeframe="1H",

                    daily_close=daily_close,
                    adx=adx,
                    rs_daily=rs_daily,
                    rs_weekly=rs_weekly,

                    ema10=ema10,
                    ema20=ema20,
                    ema50=ema50,

                    score=momentum_score,

                    fund_score=fund_score,
                    technofunda_rank=technofunda_rank,
                    sector=sector,

                    status=str(status),
                    signal=signal_category,

                    ema10_h=ema10_h,
                    ema20_h=ema20_h,
                    ema50_h=ema50_h,
                    atr_h=hourly_sl,

                    ema10_d=ema10_d,
                    ema20_d=ema20_d,
                    ema50_d=ema50_d,
                    atr_d=daily_sl,

                    ema10_w=ema10_w,
                    ema20_w=ema20_w,
                    ema50_w=ema50_w,
                    atr_w=weekly_sl
                )

                update_trade_status(

                    stock=stock,
                    timeframe="1H",
                    status="ACTIVE",
                    entry_price=float(latest_1h["Close"]),
                    last_signal="HOURLY BUY"

                )

                message = (

                    f"🟢 HOURLY BUY\n\n"
                    f"STOCK: {stock}\n"
                    f"PRICE: {float(latest_1h['Close']):.2f}\n"
                    f"RSI: {float(latest_1h['RSI']):.2f}"

                )

                print(message)

                send_telegram(message)

                # ======================================
                # DAILY BUY
                # ======================================                   

            elif daily_buy and daily_status is None:

                #print(f"🔵 DAILY BUY: {stock}")

                save_signal(

                    stock=stock,
                    signal_type="DAILY BUY",
                    price=float(latest_daily["Close"]),
                    rsi=float(latest_daily["RSI"]),
                    volume_ratio=float(latest_daily["VOL_RATIO"]),
                    timeframe="DAILY",

                    daily_close=daily_close,
                    adx=adx,
                    rs_daily=rs_daily,
                    rs_weekly=rs_weekly,

                    ema10=ema10,
                    ema20=ema20,
                    ema50=ema50,

                    score=momentum_score,

                    fund_score=fund_score,
                    technofunda_rank=technofunda_rank,
                    sector=sector,

                    status=str(status),
                    signal=signal_category,

                    ema10_h=ema10_h,
                    ema20_h=ema20_h,
                    ema50_h=ema50_h,
                    atr_h=atr_h,

                    ema10_d=ema10_d,
                    ema20_d=ema20_d,
                    ema50_d=ema50_d,
                    atr_d=atr_d,

                    ema10_w=ema10_w,
                    ema20_w=ema20_w,
                    ema50_w=ema50_w,
                    atr_w=atr_w
                )

                update_trade_status(

                    stock=stock,
                    timeframe="DAILY",
                    status="ACTIVE",
                    entry_price=float(latest_daily["Close"]),
                    last_signal="DAILY BUY"

                )

                message = (

                    f"🔵 DAILY BUY\n\n"
                    f"STOCK: {stock}\n"
                    f"PRICE: {float(latest_daily['Close']):.2f}\n"
                    f"RSI: {float(latest_daily['RSI']):.2f}"

                )

                print(message)

                send_telegram(message)

                # ======================================
                # WEEKLY BUY
                # ======================================

            elif weekly_buy and weekly_status is None:

                #print(f"🟣 WEEKLY BUY: {stock}")

                save_signal(

                    stock=stock,
                    signal_type="WEEKLY BUY",
                    price=float(latest_weekly["Close"]),
                    rsi=float(latest_weekly["RSI"]),
                    volume_ratio=float(latest_weekly["VOL_RATIO"]),
                    timeframe="WEEKLY",

                    daily_close=daily_close,
                    adx=adx,
                    rs_daily=rs_daily,
                    rs_weekly=rs_weekly,

                    ema10=ema10,
                    ema20=ema20,
                    ema50=ema50,

                    score=momentum_score,

                    fund_score=fund_score,
                    technofunda_rank=technofunda_rank,
                    sector=sector,

                    status=str(status),
                    signal=signal_category,

                    ema10_h=ema10_h,
                    ema20_h=ema20_h,
                    ema50_h=ema50_h,
                    atr_h=atr_h,

                    ema10_d=ema10_d,
                    ema20_d=ema20_d,
                    ema50_d=ema50_d,
                    atr_d=atr_d,

                    ema10_w=ema10_w,
                    ema20_w=ema20_w,
                    ema50_w=ema50_w,
                    atr_w=atr_w

                )

                update_trade_status(

                    stock=stock,
                    timeframe="WEEKLY",
                    status="ACTIVE",
                    entry_price=float(latest_weekly["Close"]),
                    last_signal="WEEKLY BUY"

                )

                message = (

                    f"🟣 WEEKLY BUY\n\n"
                    f"STOCK: {stock}\n"
                    f"PRICE: {float(latest_weekly['Close']):.2f}\n"
                    f"RSI: {float(latest_weekly['RSI']):.2f}"

                )

                print(message)

                send_telegram(message)

            # ======================================
            # DAILY ADD
            # ======================================

            elif daily_add and daily_status == "ACTIVE":

                print(f"🟢 DAILY ADD: {stock}")

                save_signal(

                    stock=stock,
                    signal_type="DAILY ADD",
                    price=float(latest_daily["Close"]),
                    rsi=float(latest_daily["RSI"]),
                    volume_ratio=1,
                    timeframe="DAILY",

                    daily_close=daily_close,
                    adx=adx,
                    rs_daily=rs_daily,
                    rs_weekly=rs_weekly,

                    ema10=ema10,
                    ema20=ema20,
                    ema50=ema50,

                    score=momentum_score,
                    technofunda_rank=technofunda_rank,
                    status=str(status),

                    ema10_h=ema10_h,
                    ema20_h=ema20_h,
                    ema50_h=ema50_h,
                    atr_h=atr_h,

                    ema10_d=ema10_d,
                    ema20_d=ema20_d,
                    ema50_d=ema50_d,
                    atr_d=atr_d,

                    ema10_w=ema10_w,
                    ema20_w=ema20_w,
                    ema50_w=ema50_w,
                    atr_w=atr_w
                )

                update_trade_status(

                    stock=stock,
                    timeframe="DAILY",
                    status="ACTIVE",
                    entry_price=float(latest_daily["Close"]),
                    last_signal="DAILY ADD"

                )

                message = (

                    f"🟢 DAILY ADD\n\n"
                    f"STOCK: {stock}\n"
                    f"PRICE: {float(latest_daily['Close']):.2f}\n"
                    f"RSI: {float(latest_daily['RSI']):.2f}"

                )

                print(message)

                send_telegram(message)

            # ======================================
            # WEEKLY ADD
            # ======================================

            elif weekly_add and weekly_status == "ACTIVE":

                #print(f"🟣 WEEKLY ADD: {stock}")

                save_signal(

                    stock=stock,
                    signal_type="WEEKLY ADD",
                    price=float(latest_weekly["Close"]),
                    rsi=float(latest_weekly["RSI"]),
                    volume_ratio=1,
                    timeframe="WEEKLY",

                    daily_close=daily_close,
                    adx=adx,
                    rs_daily=rs_daily,
                    rs_weekly=rs_weekly,

                    ema10=ema10,
                    ema20=ema20,
                    ema50=ema50,

                    score=momentum_score,
                    technofunda_rank=technofunda_rank,
                    status=str(status),

                    ema10_h=ema10_h,
                    ema20_h=ema20_h,
                    ema50_h=ema50_h,
                    atr_h=atr_h,

                    ema10_d=ema10_d,
                    ema20_d=ema20_d,
                    ema50_d=ema50_d,
                    atr_d=atr_d,

                    ema10_w=ema10_w,
                    ema20_w=ema20_w,
                    ema50_w=ema50_w,
                    atr_w=atr_w
                )

                update_trade_status(

                    stock=stock,
                    timeframe="WEEKLY",
                    status="ACTIVE",
                    entry_price=float(latest_weekly["Close"]),
                    last_signal="WEEKLY ADD"

                )

                message = (

                    f"🟣 WEEKLY ADD\n\n"
                    f"STOCK: {stock}\n"
                    f"PRICE: {float(latest_weekly['Close']):.2f}\n"
                    f"RSI: {float(latest_weekly['RSI']):.2f}"

                )

                print(message)

                send_telegram(message)        

                # ======================================
                # HOURLY SELL
                # ======================================

            elif (

                hourly_sell

                and

                hourly_status == "ACTIVE"

                and

                hourly_signal in [

                    "HOURLY BUY",
                    "HOURLY ADD"

                ]

            ):

                #print(f"🔴 HOURLY SELL: {stock}")

                save_signal(

                    stock=stock,
                    signal_type="HOURLY SELL",
                    price=float(latest_1h["Close"]),
                    rsi=float(latest_1h["RSI"]),
                    volume_ratio=float(latest_1h["VOL_RATIO"]),
                    timeframe="1H",

                    daily_close=daily_close,
                    adx=adx,
                    rs_daily=rs_daily,
                    rs_weekly=rs_weekly,

                    ema10=ema10,
                    ema20=ema20,
                    ema50=ema50,

                    score=momentum_score,
                    technofunda_rank=technofunda_rank,
                    status=str(status),

                    ema10_h=ema10_h,
                    ema20_h=ema20_h,
                    ema50_h=ema50_h,
                    atr_h=atr_h,

                    ema10_d=ema10_d,
                    ema20_d=ema20_d,
                    ema50_d=ema50_d,
                    atr_d=atr_d,

                    ema10_w=ema10_w,
                    ema20_w=ema20_w,
                    ema50_w=ema50_w,
                    atr_w=atr_w
                )

                message = (

                    f"🔴 HOURLY SELL\n\n"
                    f"STOCK: {stock}"
                    f"PRICE: {float(latest_1h['Close']):.2f}\n"

                )

                print(message)

                send_telegram(message)

                close_trade(stock, "1H")

                # ======================================
                # DAILY SELL
                # ======================================

            elif (

                daily_sell

                and

                daily_status == "ACTIVE"

                and

                daily_signal in [

                    "DAILY BUY",
                    "DAILY ADD"

                ]

            ):

                #print(f"🔴 DAILY SELL: {stock}")

                save_signal(

                    stock=stock,
                    signal_type="DAILY SELL",
                    price=float(latest_daily["Close"]),
                    rsi=float(latest_daily["RSI"]),
                    volume_ratio=1,
                    timeframe="DAILY",

                    daily_close=daily_close,
                    adx=adx,
                    rs_daily=rs_daily,
                    rs_weekly=rs_weekly,

                    ema10=ema10,
                    ema20=ema20,
                    ema50=ema50,

                    score=momentum_score,
                    technofunda_rank=technofunda_rank,
                    status=str(status),

                    ema10_h=ema10_h,
                    ema20_h=ema20_h,
                    ema50_h=ema50_h,
                    atr_h=atr_h,

                    ema10_d=ema10_d,
                    ema20_d=ema20_d,
                    ema50_d=ema50_d,
                    atr_d=atr_d,

                    ema10_w=ema10_w,
                    ema20_w=ema20_w,
                    ema50_w=ema50_w,
                    atr_w=atr_w
                )

                message = (

                    f"🔴 DAILY SELL\n\n"
                    f"STOCK: {stock}"
                    f"PRICE: {float(latest_daily['Close']):.2f}\n"

                )

                print(message)

                send_telegram(message)

                close_trade(stock, "DAILY")

                # ======================================
                # WEEKLY SELL
                # ======================================

            elif (

                weekly_sell

                and

                weekly_status == "ACTIVE"

                and

                weekly_signal in [

                    "WEEKLY BUY",
                    "WEEKLY ADD"

                ]

            ):

                #print(f"🔴 WEEKLY SELL: {stock}")

                save_signal(

                    stock=stock,
                    signal_type="WEEKLY SELL",
                    price=float(latest_weekly["Close"]),
                    rsi=float(latest_weekly["RSI"]),
                    volume_ratio=1,
                    timeframe="WEEKLY",

                    daily_close=daily_close,
                    adx=adx,
                    rs_daily=rs_daily,
                    rs_weekly=rs_weekly,

                    ema10=ema10,
                    ema20=ema20,
                    ema50=ema50,

                    score=momentum_score,
                    technofunda_rank=technofunda_rank,
                    status=str(status),

                    ema10_h=ema10_h,
                    ema20_h=ema20_h,
                    ema50_h=ema50_h,
                    atr_h=atr_h,

                    ema10_d=ema10_d,
                    ema20_d=ema20_d,
                    ema50_d=ema50_d,
                    atr_d=atr_d,

                    ema10_w=ema10_w,
                    ema20_w=ema20_w,
                    ema50_w=ema50_w,
                    atr_w=atr_w
                )

                message = (

                    f"🔴 WEEKLY SELL\n\n"
                    f"STOCK: {stock}"
                    f"PRICE: {float(latest_weekly['Close']):.2f}\n"
                )

                print(message)

                send_telegram(message)

                close_trade(stock, "WEEKLY")

            else:

                last_signal = get_last_signal(stock)

                if last_signal != "NONE":

                    save_signal(
                        stock=stock,
                        signal_type="NONE",
                        price=float(latest_daily["Close"]),
                        rsi=rsi,
                        volume_ratio=volume_ratio,
                        timeframe="NONE",

                        daily_close=daily_close,
                        adx=adx,
                        rs_daily=rs_daily,
                        rs_weekly=rs_weekly,

                        ema10=ema10,
                        ema20=ema20,
                        ema50=ema50,

                        score=momentum_score,
                        fund_score=fund_score,
                        technofunda_rank=technofunda_rank,
                        sector=sector,
                        status=str(status),
                        signal="NONE",

                        ema10_h=ema10_h,
                        ema20_h=ema20_h,
                        ema50_h=ema50_h,
                        atr_h=hourly_sl,

                        ema10_d=ema10_d,
                        ema20_d=ema20_d,
                        ema50_d=ema50_d,
                        atr_d=daily_sl,

                        ema10_w=ema10_w,
                        ema20_w=ema20_w,
                        ema50_w=ema50_w,
                        atr_w=weekly_sl
                    )
                    print(

                        f"{stock}"

                        " → No Signal"

                    )

                    
           
             
        
            # ======================================
            # SIGNAL TYPE
            # ======================================

            signal_category = "NONE"

            if weekly_buy:

                signal_category = "Wk-Buy"

            elif daily_buy:

                signal_category = "D-Buy"

            elif hourly_buy:

                signal_category = "H-Buy"

            if weekly_add:

                signal_category = "Wk-Add"

            elif daily_add:

                signal_category = "D-Add"

            elif hourly_add:

                signal_category = "H-Add"

            if weekly_sell:

                signal_category = "Wk-Sell"

            elif daily_sell:

                signal_category = "D-Sell"

            elif hourly_sell:

                signal_category = "H-Sell"        

            # =====================================
            # TECHNOfunda COMBINED SIGNAL
            # =====================================

            if momentum_score >= 70 and technofunda_rank >= 20:

                tf_signal = "⭐ HIGH CONVICTION"

            elif momentum_score >= 60 and technofunda_rank >= 10:

                tf_signal = "✅ SWING CANDIDATE"

            elif momentum_score >= 50:

                tf_signal = "👀 WATCH"

            else:

                tf_signal = "❌ AVOID"
            #========================
            # LOAD SAVED FUNDAMENTALS
            #========================
            if "fund_score" not in locals() or fund_score is None:
                fund_score = 0

            if "technofunda_rank" not in locals() or technofunda_rank is None:
                technofunda_rank = 0
            # ======================================
            # SAVE RANKING
            # ======================================

            momentum_rankings.append({

                "stock": stock,

                "sector": sector,

                "sector_score": round(
                    sector_avg_lookup.get(
                        sector,
                        0
                    ),
                    2
                ),

                "price": round(
                    float(latest_daily["Close"]),
                    2
                ),

                "score": momentum_score,

                "final_score": final_score,

                "rating": rating,

                "fund_score": fund_score,

                "technofunda_rank": round(
                    technofunda_rank,
                    2
                ),

                "grade": grade,
                
                "category": watch_category,

                "tf_signal": tf_signal,

                "signal": signal_category,

                # RSI

                "hourly_rsi": round(float(latest_1h["RSI"]), 2),

                "daily_rsi": round(float(latest_daily["RSI"]), 2),

                "weekly_rsi": round(float(latest_weekly["RSI"]), 2),

                # EMA VALUES

                "ema10": round(float(latest_daily["EMA10"]), 2),

                "ema20": round(float(latest_daily["EMA20"]), 2),

                "ema50": round(float(latest_daily["EMA50"]), 2),

                # ATR STOP LOSS

                "hourly_sl": round(hourly_sl, 2),

                "daily_sl": round(daily_sl, 2),

                "weekly_sl": round(weekly_sl, 2),

                "atr_stop": (

                    f"H:{round(hourly_sl,2)}\n"

                    f"D:{round(daily_sl,2)}\n"

                    f"W:{round(weekly_sl,2)}"

                ),

                "trade_status": (

                    weekly_status
                    if weekly_status

                    else daily_status
                    if daily_status

                    else hourly_status
                    if hourly_status

                    else "NO SIGNAL"

                ),

                "status": momentum_status,

                # RS            
                "rs_daily": round(
                    float(latest_rs_daily),
                    3
                ),

                "rs_weekly": round(
                    float(latest_rs_weekly),
                    3
                ),

                # COMBINED RS FOR HTML

                "rs": (

                    f"D:{round(float(latest_rs_daily),2)}\n"

                    f"W:{round(float(latest_rs_weekly),2)}"

                ),

                "rs_status": (

                    "RISING 📈"

                    if (
                        rs_rising_daily
                        and
                        rs_rising_weekly
                    )

                    else "FALLING 📉"

                ),

                "rs_slope": (

                    "UPWARD ↗️"

                    if (
                        rs_slope_up_daily
                        and
                        rs_slope_up_weekly
                    )

                    else "DOWNWARD ↘️"

                ),

            })

            stock_analysis_data.append({

                "sector": sector,
                "stock": stock,

                "daily_close": round(
                    float(latest_daily["Close"]),
                    2
                ),

                "rsi": round(
                    float(latest_daily["RSI"]),
                    2
                ),

                "adx": round(
                    float(adx_daily),
                    2
                ),

                "rs_daily": round(
                    float(latest_rs_daily),
                    3
                ),

                "rs_weekly": round(
                    float(latest_rs_weekly),
                    3
                ),

                "volume_ratio": round(
                    float(latest_daily["VOL_RATIO"]),
                    2
                ),

                "ema10": round(
                    float(latest_daily["EMA10"]),
                    2
                ),

                "ema20": round(
                    float(latest_daily["EMA20"]),
                    2
                ),

                "ema50": round(
                    float(latest_daily["EMA50"]),
                    2
                ),

                "fund_score": fund_score,

                "technofunda_rank": round(
                    technofunda_rank,
                    2
                ),

                "status": momentum_status,

                "signal": signal_category,

                "signal_time":
                    datetime.now().strftime(
                        "%d-%m-%Y %H:%M"
                    )

            })
            #=============================
            if sector not in sector_scores:

                sector_scores[sector] = {

                    "total_score": 0,
                    "count": 0,
                    "stock_count": 0,
                    "strong_count": 0

                }              
            # =================================
            # UPDATE SECTOR DATA
            # =================================
            
            sector_scores[sector]["total_score"] += momentum_score
            sector_scores[sector]["count"] += 1
            sector_scores[sector]["stock_count"] += 1

            if momentum_score >= 60:
                sector_scores[sector]["strong_count"] += 1

            # =====================================
            # CALCULATE SECTOR DATA
            # =====================================

            #global sector_data

            if not isinstance(sector_data, list):
                sector_data = []

            sector_data.clear()

            for sector_name, data in sector_scores.items():

                if data["count"] > 0:

                    avg_score = round(
                        data["total_score"] / data["count"],
                        2
                    )

                else:

                    avg_score = 0

                sector_data.append({

                    "sector": sector_name,

                    "avg_score": avg_score,

                    "stock_count": data["stock_count"],

                    "strong_count": data["strong_count"],

                    "trend": (

                        "🔥 Strong"

                        if avg_score >= 60

                        else "👀 Watch"

                        if avg_score >= 45

                        else "⚠ Weak"

                    )

                })

            sector_data.sort(

                key=lambda x: x["avg_score"],

                reverse=True

            )
            #print("\nSECTOR SCORES")

            for s in sector_data:
                #print(s["sector"], s["avg_score"], s["stock_count"])
        
            # ====================================
            # FILTER STRONG MOMENTUM STOCKS
            # ====================================

                strong_stocks = [

                    stock for stock in momentum_rankings

                    if stock["score"] >= 35

                ]    
            # ====================================
            # CREATE MESSAGE
            # ====================================

            ranking_message = (
                "🔥 TOP TECHNOFUNDA STOCKS 🔥\n\n"
            )
            
            # ====================================
            # TOP MOMENTUM RANKING
            # ====================================

            top_stocks = sorted(

                strong_stocks,

                key=lambda x: x.get(
                    "final_score",
                    0
                ),

                reverse=True

            )[:100]

        except Exception as e:
    
            import traceback

            print(f"{stock} failed ❌")

            traceback.print_exc()

            continue
            

    # ====================================
    # CHECK STOCKS FOUND
    # ====================================

    if len(top_stocks) == 0:

        ranking_message += (
            "No strong momentum stocks found."
        )

    else:

        for i, stock_data in enumerate(

            top_stocks,

            start=1

        ):

            ranking_message += (

                f"{i}. "

                f"{stock_data['stock']} "

                f"| Score: {stock_data['score']} "

                f"| Signal: {stock_data['signal']} "

                f"| 1H RSI: {stock_data['hourly_rsi']} "

                f"| D RSI: {stock_data['daily_rsi']} "

                f"| W RSI: {stock_data['weekly_rsi']}\n"

            )         
    # ===================================
    # MY TRADES LIVE ALERTS
    # ===================================

        conn = sqlite3.connect(    
        "signals.db"
        )

        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM my_trades
            WHERE status='OPEN'
            """
        )

        open_trades = cursor.fetchall()

        print(
            "OPEN TRADES:",
            len(open_trades)
        )

        for tr in open_trades:
            
            stock = tr["stock"]

            cursor.execute(
                """
                SELECT
                daily_close,
                signal,
                daily_ema10,
                weekly_ema10,
                monthly_ema10
            FROM stock_analysis
                WHERE stock=?
                """,
                (stock,)
            )

            row = cursor.fetchone()

            if not row:
                continue

            cmp_price = row["daily_close"]

            signal = (
                row["signal"]
                if row["signal"]
                else ""
            )
           
            # TARGET
           
            if (
                tr["status"] == "OPEN"
                and
                float(cmp_price)
                >=
                float(tr["target"])
            ):

                msg = (
                    f"🎯 Target Achieved\n"
                    f"{tr['stock']}\n"
                    f"CMP: {cmp_price}\n"
                    f"Target: {tr['target']}"
                )

                if not alert_sent(
                    cursor,
                    tr["stock"],
                    "TARGET"
                ):

                    print(
                        "SAVING TARGET ALERT:",
                        tr["stock"]
                    )

                    send_telegram(
                        msg
                    )

                    save_alert(
                        conn,
                        cursor,
                        tr["stock"],
                        "TARGET"
                    )

        conn.close()

        # =========================================
        # PRINT + TELEGRAM
        # =========================================

        if len(top_stocks) > 0:

            #print(
            #    "\n" +
            #    ranking_message
            #)

            send_telegram(
                ranking_message
            )

        else:

            print(
                "No strong momentum stocks found."
            )
        # ====================================
        # FINAL SECTOR RANKING
        # ====================================    

        sector_data.clear()

        for sector_name, data in sector_scores.items():

            avg_score = round(

                data["total_score"]

                /

                max(data["count"], 1),

                2
            )
            sector_avg_lookup[sector_name] = avg_score

            if avg_score >= 75:

                trend = "🚀 Strong"

            elif avg_score >= 60:

                trend = "📈 Positive"

            elif avg_score >= 45:

                trend = "⚠️ Weak"

            else:

                trend = "❌ Avoid"

            sector_data.append({

                "sector": sector_name,

                "avg_score": avg_score,

                "stocks": data["stock_count"],

                "strong": data["strong_count"],

                "trend": trend
            })

        sector_data = sorted(

            sector_data,

            key=lambda x: x["avg_score"],

            reverse=True
        )
        # =========================
        # SECTOR RS SCORE
        # =========================

        sector_rs_lookup = {}

        for rank, sector in enumerate(
            sector_data,
            start=1
        ):

            if rank <= 5:
                score = 20

            elif rank <= 10:
                score = 18

            elif rank <= 15:
                score = 15

            elif rank <= 20:
                score = 10

            else:
                score = 5

            sector_rs_lookup[
                sector["sector"]
            ] = score
        
        # ====================================
        # GLOBAL MOMENTUM DATA
        # ====================================
        
        momentum_data.clear()

        momentum_data.extend(top_stocks)

        #print("MOMENTUM DATA UPDATED ✅")

        #print(momentum_data)  
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

        print("Next Scan After 1 Hour ⏳")

        time.sleep(3600)
#================================

#===============================
def close_trade(

    stock,
    timeframe

):

    conn = sqlite3.connect(
        "signals.db"
    )

    cursor = conn.cursor()

    cursor.execute("""

        DELETE FROM active_trades

        WHERE stock=?
        AND timeframe=?

    """,

    (

        stock,
        timeframe

    )

    )

    conn.commit()
    conn.close()   
#=================================    
def get_trade_status(

    stock,
    timeframe

):

    conn = sqlite3.connect(
        "signals.db"
    )

    cursor = conn.cursor()

    cursor.execute("""

        SELECT

            status,
            entry_price,
            last_signal

        FROM active_trades

        WHERE stock=?
        AND timeframe=?

    """,

    (

        stock,
        timeframe

    )

    )

    row = cursor.fetchone()

    conn.close()

    if row:

        return row

    return (

        None,
        None,
        None

    )
#==============================
def update_trade_status(

    stock,
    timeframe,
    status,
    entry_price,
    last_signal

):

    conn = sqlite3.connect(
        "signals.db"
    )

    cursor = conn.cursor()

    cursor.execute("""

        INSERT OR REPLACE INTO active_trades (

            stock,
            timeframe,
            status,
            entry_price,
            last_signal,
            updated_time

        )

        VALUES (

            ?,
            ?,
            ?,
            ?,
            ?,
            datetime('now')

        )

    """,

    (

        stock,
        timeframe,
        status,
        entry_price,
        last_signal

    )

    )

    conn.commit()
    conn.close()
# ===========================
# RESET SIGNALS
# ===========================

def clear_old_signals():

    conn = sqlite3.connect(
        "signals.db"
    )

    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM signals"
    )

    cursor.execute(
        "DELETE FROM active_trades"
    )

    cursor.execute(
        "DELETE FROM sqlite_sequence WHERE name='signals'"
    )

    conn.commit()

    # CHECK COUNT AFTER DELETE
    cursor.execute(
        "SELECT COUNT(*) FROM signals"
    )

    print(
        "Signals After Reset:",
        cursor.fetchone()[0]
    )

    conn.close()

    print(
        "Signals Reset ✅"
    )


# ====================================
# START BACKGROUND SCANNER
# ====================================

def start_background_scanner():

    scanner_thread = threading.Thread(

        target=run_scanner,

        daemon=True

    )

    scanner_thread.start()

    #print("SCANNER THREAD STARTED 🚀")
#====================================
@app.route(
    "/download-trades-csv"
)
def download_trades_csv():

    from flask import Response

    conn = sqlite3.connect(
        "signals.db"
    )

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT

            tt.created_at,
            mt.portfolio,
            mt.stock,
            tt.action,
            tt.qty,
            tt.price

        FROM trade_transactions tt

        LEFT JOIN my_trades mt
        ON tt.trade_id = mt.id

        ORDER BY tt.created_at DESC
        """
    )

    rows = cursor.fetchall()

    conn.close()

    def generate():

        output = []

        if rows:

            headers = rows[0].keys()

            output.append(
                ",".join(headers)
            )

            for row in rows:

                output.append(

                    ",".join(

                        str(
                            row[h]
                        )
                        for h in headers
                    )
                )

        return "\n".join(output)

    return Response(

        generate(),

        mimetype="text/csv",

        headers={

            "Content-Disposition":
            "attachment; filename=trade_ledger.csv"

        }
    )
# ====================================
# MAIN
# ====================================

if __name__ == "__main__":

    import os

    create_fundamental_table()

    create_signal_table()

    create_active_trades_table()

    # clear_old_signals()   # RUN ONCE

    start_background_scanner()

    socket_thread = threading.Thread(
        target=background_signal_updater,
        daemon=True
    )

    socket_thread.start()

    print("FLASK SERVER STARTED 🚀")

    port = int(os.environ.get("PORT", 10000))

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=False
    )
