#!/usr/bin/env python3
"""
sync_terminal.py - Automated 6-Hour Market Data & News Synchronizer for WHY://TERMINAL
Fetches live data from Yahoo Finance, Binance API, and financial RSS feeds,
recalculates technical indicators (RSI 14, 24h %, momentum signals),
and safely updates index.html.
"""

import urllib.request
import urllib.parse
import json
import re
import math
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

INDEX_PATH = "index.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_json(url, timeout=12):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"[WARN] fetch_json failed for {url}: {e}")
        return None

def fetch_rss(url, timeout=12):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return ET.fromstring(resp.read())
    except Exception as e:
        print(f"[WARN] fetch_rss failed for {url}: {e}")
        return None

def calc_rsi(prices, period=14):
    if not prices or len(prices) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    
    if len(gains) < period:
        return 50.0

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)

def format_vol(num):
    if not num or math.isnan(num):
        return "100K"
    if num >= 1_000_000_000_000:
        return f"{num / 1_000_000_000_000:.1f}T"
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}B"
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(int(num))

def fetch_binance_asset(symbol, quote_name, asset_name, cat, dp=2):
    t_url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
    k_url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit=25"
    
    t_data = fetch_json(t_url)
    k_data = fetch_json(k_url)

    if not t_data or 'lastPrice' not in t_data:
        return None

    last = float(t_data.get('lastPrice', 0))
    chg = float(t_data.get('priceChange', 0))
    chg_pct = float(t_data.get('priceChangePercent', 0))
    high = float(t_data.get('highPrice', 0))
    low = float(t_data.get('lowPrice', 0))
    vol_raw = float(t_data.get('volume', 0))

    closes = []
    if k_data and isinstance(k_data, list):
        closes = [float(bar[4]) for bar in k_data]

    rsi = calc_rsi(closes) if closes else 60.0

    if rsi <= 40:
        signal = "OVERSOLD"
    elif rsi >= 65:
        signal = "OVERBOUGHT"
    elif rsi >= 55 and chg_pct > 0:
        signal = "GOLDEN_CROSS"
    elif abs(chg_pct) >= 2.0:
        signal = "VOL_BREAKOUT"
    elif chg_pct > 0:
        signal = "BULLISH"
    else:
        signal = "BEARISH"

    return {
        "sym": quote_name,
        "name": asset_name,
        "cat": cat,
        "last": round(last, dp) if dp > 0 else int(round(last)),
        "chg": round(chg, dp) if dp > 0 else int(round(chg)),
        "chgPct": round(chg_pct, 2),
        "high": round(high, dp) if dp > 0 else int(round(high)),
        "low": round(low, dp) if dp > 0 else int(round(low)),
        "vol": format_vol(vol_raw),
        "rsi": rsi,
        "signal": signal,
        "dp": dp
    }

def fetch_yahoo_asset(yahoo_sym, terminal_sym, name, cat, dp=2):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yahoo_sym)}?range=1mo&interval=1d"
    data = fetch_json(url)

    if not data or 'chart' not in data or not data['chart']['result']:
        print(f"[WARN] No data from Yahoo for {yahoo_sym}")
        return None

    res = data['chart']['result'][0]
    meta = res.get('meta', {})
    indicators = res.get('indicators', {})
    quotes = indicators.get('quote', [{}])[0]

    last = meta.get('regularMarketPrice')
    prev_close = meta.get('chartPreviousClose') or meta.get('previousClose')
    high = meta.get('regularMarketDayHigh')
    low = meta.get('regularMarketDayLow')
    vol = meta.get('regularMarketVolume')

    closes = quotes.get('close', [])
    valid_closes = [c for c in closes if c is not None]

    if last is None and valid_closes:
        last = valid_closes[-1]

    if prev_close is None and len(valid_closes) >= 2:
        prev_close = valid_closes[-2]

    if last is None:
        return None

    if prev_close and prev_close > 0:
        chg = last - prev_close
        chg_pct = (chg / prev_close) * 100
    else:
        chg = 0.0
        chg_pct = 0.0

    if high is None and valid_closes:
        high = max(valid_closes[-5:])
    if low is None and valid_closes:
        low = min(valid_closes[-5:])

    rsi = calc_rsi(valid_closes) if len(valid_closes) >= 15 else 50.0

    if rsi <= 40:
        signal = "OVERSOLD"
    elif rsi >= 65:
        signal = "OVERBOUGHT"
    elif rsi >= 55 and chg_pct > 0:
        signal = "GOLDEN_CROSS"
    elif abs(chg_pct) >= 2.0:
        signal = "VOL_BREAKOUT"
    elif chg_pct > 0:
        signal = "BULLISH"
    elif chg_pct < 0:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    if rsi <= 42:
        signal = "OVERSOLD"

    return {
        "sym": terminal_sym,
        "name": name,
        "cat": cat,
        "last": round(last, dp) if dp > 0 else int(round(last)),
        "chg": round(chg, dp) if dp > 0 else int(round(chg)),
        "chgPct": round(chg_pct, 2),
        "high": round(high, dp) if (high is not None and dp > 0) else (int(round(high)) if high is not None else last),
        "low": round(low, dp) if (low is not None and dp > 0) else (int(round(low)) if low is not None else last),
        "vol": format_vol(vol) if vol else ("Forex" if cat == "FOREX" else "Metal"),
        "rsi": rsi,
        "signal": signal,
        "dp": dp
    }

# Fallback default universe definition if fresh network pull fails
DEFAULT_FALLBACK = [
    {"sym": "GC1!", "name": "Gold Futures / XAUUSD", "cat": "METALS", "last": 4405.90, "chg": 2.70, "chgPct": 0.06, "high": 4422.10, "low": 4377.50, "vol": "245K", "rsi": 52.4, "signal": "NEUTRAL", "dp": 2},
    {"sym": "NQ1!", "name": "E-Mini Nasdaq 100", "cat": "US", "last": 30264.50, "chg": 347.25, "chgPct": 1.15, "high": 30275.00, "low": 29904.00, "vol": "1.45M", "rsi": 68.4, "signal": "GOLDEN_CROSS", "dp": 2},
    {"sym": "BTC/USD", "name": "Bitcoin / US Dollar", "cat": "CRYPTO", "last": 85365.63, "chg": 4945.00, "chgPct": 6.15, "high": 85473.68, "low": 80327.64, "vol": "21.7K", "rsi": 74.2, "signal": "OVERBOUGHT", "dp": 2},
    {"sym": "ETH/USD", "name": "Ethereum", "cat": "CRYPTO", "last": 2732.69, "chg": 155.30, "chgPct": 6.03, "high": 2749.98, "low": 2571.96, "vol": "420K", "rsi": 68.1, "signal": "VOL_BREAKOUT", "dp": 2},
    {"sym": "SOL/USD", "name": "Solana", "cat": "CRYPTO", "last": 117.02, "chg": 8.65, "chgPct": 8.00, "high": 117.18, "low": 107.94, "vol": "3.6M", "rsi": 76.5, "signal": "OVERBOUGHT", "dp": 2},
    {"sym": "IHSG", "name": "IDX Composite", "cat": "IDX", "last": 6384.73, "chg": -56.70, "chgPct": -0.88, "high": 6451.33, "low": 6381.57, "vol": "16.8T", "rsi": 34.2, "signal": "OVERSOLD", "dp": 2},
    {"sym": "BBCA.JK", "name": "Bank Central Asia", "cat": "IDX", "last": 6225, "chg": -75, "chgPct": -1.19, "high": 6300, "low": 6225, "vol": "131M", "rsi": 38.6, "signal": "OVERSOLD", "dp": 0},
    {"sym": "BBRI.JK", "name": "Bank Rakyat Indonesia", "cat": "IDX", "last": 3300, "chg": 10, "chgPct": 0.30, "high": 3310, "low": 3270, "vol": "185M", "rsi": 33.1, "signal": "OVERSOLD", "dp": 0},
    {"sym": "BMRI.JK", "name": "Bank Mandiri", "cat": "IDX", "last": 4200, "chg": -70, "chgPct": -1.64, "high": 4270, "low": 4200, "vol": "140M", "rsi": 36.4, "signal": "OVERSOLD", "dp": 0},
    {"sym": "TLKM.JK", "name": "Telkom Indonesia", "cat": "IDX", "last": 2500, "chg": -20, "chgPct": -0.79, "high": 2550, "low": 2500, "vol": "95M", "rsi": 41.5, "signal": "OVERSOLD", "dp": 0},
    {"sym": "ASII.JK", "name": "Astra International", "cat": "IDX", "last": 4820, "chg": 10, "chgPct": 0.21, "high": 4870, "low": 4810, "vol": "74M", "rsi": 46.2, "signal": "NEUTRAL", "dp": 0},
    {"sym": "AMMN.JK", "name": "Amman Mineral", "cat": "IDX", "last": 4660, "chg": -190, "chgPct": -3.92, "high": 4850, "low": 4640, "vol": "115M", "rsi": 42.0, "signal": "VOL_BREAKOUT", "dp": 0},
    {"sym": "NVDA", "name": "NVIDIA Corp", "cat": "US", "last": 222.27, "chg": 4.15, "chgPct": 1.90, "high": 222.73, "low": 218.04, "vol": "38.2B", "rsi": 67.2, "signal": "GOLDEN_CROSS", "dp": 2},
    {"sym": "AAPL", "name": "Apple Inc", "cat": "US", "last": 336.13, "chg": 2.85, "chgPct": 0.85, "high": 338.49, "low": 332.53, "vol": "19.4B", "rsi": 55.4, "signal": "NEUTRAL", "dp": 2},
    {"sym": "TSLA", "name": "Tesla Inc", "cat": "US", "last": 364.27, "chg": 7.40, "chgPct": 2.07, "high": 370.90, "low": 360.75, "vol": "24.1B", "rsi": 69.8, "signal": "VOL_BREAKOUT", "dp": 2},
    {"sym": "MSFT", "name": "Microsoft Corp", "cat": "US", "last": 493.78, "chg": 3.20, "chgPct": 0.65, "high": 498.65, "low": 491.10, "vol": "16.2B", "rsi": 58.0, "signal": "NEUTRAL", "dp": 2},
    {"sym": "USD/IDR", "name": "US Dollar / Rupiah", "cat": "FOREX", "last": 17847, "chg": 95, "chgPct": 0.54, "high": 17855, "low": 17735, "vol": "Forex", "rsi": 78.4, "signal": "OVERBOUGHT", "dp": 0},
    {"sym": "EUR/USD", "name": "Euro / US Dollar", "cat": "FOREX", "last": 1.1493, "chg": 0.0012, "chgPct": 0.10, "high": 1.1498, "low": 1.1474, "vol": "Forex", "rsi": 52.1, "signal": "NEUTRAL", "dp": 4},
    {"sym": "GBP/USD", "name": "British Pound / USD", "cat": "FOREX", "last": 1.3415, "chg": 0.0022, "chgPct": 0.16, "high": 1.3440, "low": 1.3385, "vol": "Forex", "rsi": 58.3, "signal": "NEUTRAL", "dp": 4},
    {"sym": "XAU/USD", "name": "Gold Spot (London)", "cat": "METALS", "last": 4359.14, "chg": -2.40, "chgPct": -0.06, "high": 4375.00, "low": 4338.00, "vol": "Metal", "rsi": 51.5, "signal": "NEUTRAL", "dp": 2},
    {"sym": "SI=F", "name": "Silver Futures", "cat": "METALS", "last": 67.09, "chg": 0.85, "chgPct": 1.28, "high": 67.55, "low": 66.20, "vol": "Metal", "rsi": 64.2, "signal": "BULLISH", "dp": 2},
    {"sym": "BRENT", "name": "WTI/Brent Crude Oil", "cat": "METALS", "last": 93.36, "chg": -1.45, "chgPct": -1.53, "high": 97.22, "low": 92.70, "vol": "Energy", "rsi": 44.0, "signal": "BEARISH", "dp": 2}
]

def fetch_all_universe():
    fb_map = {u['sym']: u for u in DEFAULT_FALLBACK}
    updated = []

    print("[1/4] Fetching Primary & Crypto Assets...")
    # 1. GC1!
    gc = fetch_yahoo_asset("GC=F", "GC1!", "Gold Futures / XAUUSD", "METALS", 2)
    if not gc:
        gc = fetch_binance_asset("PAXGUSDT", "GC1!", "Gold Futures / XAUUSD", "METALS", 2) or fb_map.get("GC1!")
    if gc: updated.append(gc)

    # 2. NQ1!
    nq = fetch_yahoo_asset("NQ=F", "NQ1!", "E-Mini Nasdaq 100", "US", 2) or fb_map.get("NQ1!")
    if nq: updated.append(nq)

    # 3. BTC/USD
    btc = fetch_binance_asset("BTCUSDT", "BTC/USD", "Bitcoin / US Dollar", "CRYPTO", 2) or fb_map.get("BTC/USD")
    if btc: updated.append(btc)

    # 4. ETH/USD
    eth = fetch_binance_asset("ETHUSDT", "ETH/USD", "Ethereum", "CRYPTO", 2) or fb_map.get("ETH/USD")
    if eth: updated.append(eth)

    # 5. SOL/USD
    sol = fetch_binance_asset("SOLUSDT", "SOL/USD", "Solana", "CRYPTO", 2) or fb_map.get("SOL/USD")
    if sol: updated.append(sol)

    print("[2/4] Fetching IDX Indonesian Equities...")
    idx_list = [
        ("^JKSE", "IHSG", "IDX Composite", "IDX", 2),
        ("BBCA.JK", "BBCA.JK", "Bank Central Asia", "IDX", 0),
        ("BBRI.JK", "BBRI.JK", "Bank Rakyat Indonesia", "IDX", 0),
        ("BMRI.JK", "BMRI.JK", "Bank Mandiri", "IDX", 0),
        ("TLKM.JK", "TLKM.JK", "Telkom Indonesia", "IDX", 0),
        ("ASII.JK", "ASII.JK", "Astra International", "IDX", 0),
        ("AMMN.JK", "AMMN.JK", "Amman Mineral", "IDX", 0),
    ]
    for y_sym, t_sym, name, cat, dp in idx_list:
        item = fetch_yahoo_asset(y_sym, t_sym, name, cat, dp) or fb_map.get(t_sym)
        if item: updated.append(item)

    print("[3/4] Fetching US Equities, Forex & Commodities...")
    us_list = [
        ("NVDA", "NVDA", "NVIDIA Corp", "US", 2),
        ("AAPL", "AAPL", "Apple Inc", "US", 2),
        ("TSLA", "TSLA", "Tesla Inc", "US", 2),
        ("MSFT", "MSFT", "Microsoft Corp", "US", 2),
    ]
    for y_sym, t_sym, name, cat, dp in us_list:
        item = fetch_yahoo_asset(y_sym, t_sym, name, cat, dp) or fb_map.get(t_sym)
        if item: updated.append(item)

    fx_list = [
        ("USDIDR=X", "USD/IDR", "US Dollar / Rupiah", "FOREX", 0),
        ("EURUSD=X", "EUR/USD", "Euro / US Dollar", "FOREX", 4),
        ("GBPUSD=X", "GBP/USD", "British Pound / USD", "FOREX", 4),
    ]
    for y_sym, t_sym, name, cat, dp in fx_list:
        item = fetch_yahoo_asset(y_sym, t_sym, name, cat, dp) or fb_map.get(t_sym)
        if item: updated.append(item)

    comm_list = [
        ("GC=F", "XAU/USD", "Gold Spot (London)", "METALS", 2),
        ("SI=F", "SI=F", "Silver Futures", "METALS", 2),
        ("BZ=F", "BRENT", "WTI/Brent Crude Oil", "METALS", 2),
    ]
    for y_sym, t_sym, name, cat, dp in comm_list:
        item = fetch_yahoo_asset(y_sym, t_sym, name, cat, dp) or fb_map.get(t_sym)
        if item: updated.append(item)

    return updated

def fetch_live_news():
    print("[4/4] Fetching Multi-Portal Financial News Wire...")
    new_items = []
    now_wib = datetime.now(timezone(timedelta(hours=7)))
    time_str = now_wib.strftime("%H:%M")

    # 1. CoinDesk RSS
    cd_root = fetch_rss("https://www.coindesk.com/arc/outboundfeeds/rss/")
    if cd_root:
        cd_items = cd_root.findall('./channel/item')[:2]
        for it in cd_items:
            title = it.find('title').text if it.find('title') is not None else ""
            if title:
                title = re.sub(r'<[^>]+>', '', title).strip()
                new_items.append({
                    "id": f"n_cd_{len(new_items)+1}",
                    "portal": "COINDESK",
                    "time": time_str,
                    "tag": "CRYPTO",
                    "sentiment": "BULLISH" if any(w in title.lower() for w in ['surge', 'jump', 'rally', 'high', 'gain', 'inflow', 'record']) else "NEUTRAL",
                    "title": title,
                    "impact": "Sentimen likuiditas aset kripto global dan perputaran volume harian.",
                    "tickers": ["BTC/USD", "ETH/USD"]
                })

    # 2. Google News Indonesia (IDX / Rupiah)
    g_id_root = fetch_rss("https://news.google.com/rss/search?q=IHSG+OR+saham+OR+Rupiah&hl=id&gl=ID&ceid=ID:id")
    if g_id_root:
        id_items = g_id_root.findall('./channel/item')[:3]
        for it in id_items:
            title = it.find('title').text if it.find('title') is not None else ""
            if title:
                source = "KONTAN"
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    title = parts[0]
                    src_tag = parts[1].upper()
                    if "BISNIS" in src_tag: source = "BISNIS"
                    elif "DETIK" in src_tag or "CNBC" in src_tag: source = "CNBC"
                    elif "KONTAN" in src_tag: source = "KONTAN"
                sent = "BEARISH" if any(w in title.lower() for w in ['turun', 'melemah', 'anjlok', 'jual', 'koreksi']) else ("BULLISH" if any(w in title.lower() for w in ['naik', 'menguat', 'rebound', 'lonjak']) else "NEUTRAL")
                new_items.append({
                    "id": f"n_id_{len(new_items)+1}",
                    "portal": source,
                    "time": time_str,
                    "tag": "IDX",
                    "sentiment": sent,
                    "title": title,
                    "impact": "Dinamika pasar domestik, pergerakan dana asing, dan stabilitas kurs nilai tukar.",
                    "tickers": ["IHSG", "BBCA.JK", "BBRI.JK", "USD/IDR"]
                })

    # 3. Google News US / Global Markets
    g_us_root = fetch_rss("https://news.google.com/rss/search?q=Nasdaq+OR+Nvidia+OR+Gold+price&hl=en&gl=US&ceid=US:en")
    if g_us_root:
        us_items = g_us_root.findall('./channel/item')[:2]
        for it in us_items:
            title = it.find('title').text if it.find('title') is not None else ""
            if title:
                source = "BLOOMBERG"
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    title = parts[0]
                    src_tag = parts[1].upper()
                    if "REUTERS" in src_tag: source = "REUTERS"
                    elif "CNBC" in src_tag: source = "CNBC"
                    elif "INVESTING" in src_tag: source = "INVESTING"
                sent = "BULLISH" if any(w in title.lower() for w in ['rally', 'gains', 'high', 'surge', 'rise']) else ("BEARISH" if any(w in title.lower() for w in ['drop', 'fall', 'sink', 'slide', 'slump']) else "NEUTRAL")
                new_items.append({
                    "id": f"n_us_{len(new_items)+1}",
                    "portal": source,
                    "time": time_str,
                    "tag": "US TECH",
                    "sentiment": sent,
                    "title": title,
                    "impact": "Arah pergerakan Wall Street dan sentimen risiko makro ekonomi.",
                    "tickers": ["NQ1!", "NVDA", "GC1!"]
                })

    # Curated backup headlines
    curated_backup = [
        { "id": "n1", "portal": "COINDESK", "time": "19:15", "tag": "CRYPTO", "sentiment": "BULLISH", "title": "Bitcoin melonjak menembus $85.365 didorong arus modal masuk masif Spot ETF; analis pantau resisten kunci $85.500.", "impact": "Risk-on appetite kembali menguasai pasar kripto, likuiditas berputar cepat ke Ethereum dan Solana.", "tickers": ["BTC/USD", "ETH/USD", "SOL/USD"] },
        { "id": "n2", "portal": "BLOOMBERG", "time": "18:50", "tag": "US TECH", "sentiment": "BULLISH", "title": "Wall Street reli dipimpin saham kecerdasan buatan (Nvidia, Tesla, Microsoft); pelonggaran harga minyak dinginkan yield obligasi.", "impact": "E-Mini Nasdaq 100 melaju ke level 30.264, indeks S&P 500 cetak rekor performa kuartalan.", "tickers": ["NQ1!", "NVDA", "TSLA", "MSFT"] },
        { "id": "n3", "portal": "KONTAN", "time": "18:30", "tag": "IDX", "sentiment: ": "BEARISH", "title": "IHSG ditutup melemah 0,88% ke 6.384 di tengah aksi jual bersih asing Rp 510 Miliar dan pelemahan Rupiah ke Rp 17.847 per Dolar AS.", "impact": "Saham perbankan (BBCA, BMRI) masuk zona oversold teknikal jelang rilis pengumuman RDG Bank Indonesia.", "tickers": ["IHSG", "BBCA.JK", "BMRI.JK", "USD/IDR"] },
        { "id": "n4", "portal": "REUTERS", "time": "18:05", "tag": "METALS", "sentiment": "NEUTRAL", "title": "Harga emas dunia stabil di level $4.359 - $4.405 per troy ounce; pelaku pasar cermati pidato 8 pejabat Federal Reserve pekan ini.", "impact": "Aset safe-haven terkonsolidasi sehat setelah mencatatkan kenaikan lebih dari 16% Year-on-Year.", "tickers": ["GC1!", "XAU/USD", "SI=F"] },
        { "id": "n5", "portal": "CNBC", "time": "17:40", "tag": "MACRO", "sentiment": "NEUTRAL", "title": "Pasar global antisipasi rilis data PMI Manufaktur & Jasa AS (23 Sept) dan KTT Bilateral AS-China Trump-Xi (24 Sept).", "impact": "Volatilitas aset risiko diproyeksikan meningkat menjelang agenda geopolitik dan tarif dagang dunia.", "tickers": ["NQ1!", "IHSG", "BRENT"] },
        { "id": "n6", "portal": "FOREXLIVE", "time": "17:15", "tag": "FOREX", "sentiment": "BEARISH", "title": "Dolar AS perkasa 8 hari berturut-turut menekan mata uang berkembang; Rupiah menyentuh Rp 17.847 per USD, pasar nantikan sinyal BI-Rate.", "impact": "Intervensi Bank Indonesia di pasar spot dan DNDF diharapkan menstabilkan volatilitas nilai tukar.", "tickers": ["USD/IDR", "EUR/USD", "GBP/USD"] },
        { "id": "n7", "portal": "KONTAN", "time": "16:45", "tag": "IDX", "sentiment": "BULLISH", "title": "Bank Rakyat Indonesia (BBRI) konsolidasi di level Rp 3.300; analis nilai insentif KLM BI buka ruang likuiditas ekspansi kredit.", "impact": "RSI indikator harian BBRI berada di level 33.1 (area jenuh jual), terbuka peluang technical rebound.", "tickers": ["BBRI.JK"] },
        { "id": "n8", "portal": "COINDESK", "time": "16:10", "tag": "CRYPTO", "sentiment": "BULLISH", "title": "Solana (+8,0%) dan Ethereum (+6,0%) cetak lonjakan volume breakout harian terdorong ekspansi aktivitas DeFi.", "impact": "Arus likuiditas terdesentralisasi melesat, memicu reli altcoin berkapitalisasi besar.", "tickers": ["SOL/USD", "ETH/USD"] },
        { "id": "n9", "portal": "INVESTING", "time": "15:35", "tag": "COMMODITIES", "sentiment": "BEARISH", "title": "Minyak mentah Brent melandai ke $93,36 per barel di tengah normalisasi pasokan energi; pasar nantikan rilis persediaan minyak EIA.", "impact": "Pelemahan harga minyak mentah mengurangi beban biaya logistik dan inflasi industri global.", "tickers": ["BRENT"] },
        { "id": "n10", "portal": "BISNIS", "time": "14:50", "tag": "IDX", "sentiment": "BEARISH", "title": "Amman Mineral (AMMN) terkoreksi ke level Rp 4.660 (-3,92%) akibat aksi rebalancing portofolio pengelola dana global.", "impact": "Tekanan jual pada saham komoditas mineral membayangi pergerakan indeks sektor bahan baku BEI.", "tickers": ["AMMN.JK"] }
    ]

    seen = {n['title'][:20].lower() for n in new_items}
    for c in curated_backup:
        if c['title'][:20].lower() not in seen:
            new_items.append(c)
        if len(new_items) >= 10:
            break

    return new_items[:10]

def update_index_html():
    print("[INFO] Starting 6-Hour Market Data Sync for WHY://TERMINAL...")
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"[ERROR] Could not read {INDEX_PATH}: {e}")
        return False

    u_match = re.search(r'universe:\s*(\[[\s\S]*?\])\s*,\s*\n\s*news:', content)
    n_match = re.search(r'news:\s*(\[[\s\S]*?\])\s*,\s*\n\s*economicCalendar:', content)

    if not u_match or not n_match:
        print("[ERROR] Could not locate universe or news blocks in index.html")
        return False

    new_universe = fetch_all_universe()
    new_news = fetch_live_news()

    # Format JSON strings with clean indent
    u_lines = ["[\n"]
    for i, u in enumerate(new_universe):
        comma = "," if i < len(new_universe) - 1 else ""
        u_lines.append(f"      {json.dumps(u)}{comma}\n")
    u_lines.append("    ]")
    u_formatted = "".join(u_lines)

    n_lines = ["[\n"]
    for i, n in enumerate(new_news):
        comma = "," if i < len(new_news) - 1 else ""
        n_lines.append(f"      {json.dumps(n)}{comma}\n")
    n_lines.append("    ]")
    n_formatted = "".join(n_lines)

    # Slice replace news first (appears later in file)
    content = content[:n_match.start(1)] + n_formatted + content[n_match.end(1):]

    # Re-search universe after news slice
    u_match = re.search(r'universe:\s*(\[[\s\S]*?\])\s*,\s*\n\s*news:', content)
    content = content[:u_match.start(1)] + u_formatted + content[u_match.end(1):]

    # Update top baseline bars and header widgets for GC, NQ, BTC
    gc_item = next((u for u in new_universe if u['sym'] == 'GC1!'), None)
    nq_item = next((u for u in new_universe if u['sym'] == 'NQ1!'), None)
    btc_item = next((u for u in new_universe if u['sym'] == 'BTC/USD'), None)

    if gc_item:
        content = re.sub(
            r'window\.W_TERMINAL\.barsGC\s*=\s*generateBaselineBars\([0-9\.]+',
            f'window.W_TERMINAL.barsGC = generateBaselineBars({gc_item["last"]:.2f}',
            content
        )
        content = re.sub(
            r'id="gc-price-val">\$[0-9,\.]+<',
            f'id="gc-price-val">${gc_item["last"]:,.2f}<',
            content
        )
        content = re.sub(
            r'id="gc-chg-val">[+\-0-9\.\%]+<',
            f'id="gc-chg-val">{"+" if gc_item["chgPct"]>=0 else ""}{gc_item["chgPct"]:.2f}%<',
            content
        )

    if nq_item:
        content = re.sub(
            r'window\.W_TERMINAL\.barsNQ\s*=\s*generateBaselineBars\([0-9\.]+',
            f'window.W_TERMINAL.barsNQ = generateBaselineBars({nq_item["last"]:.2f}',
            content
        )
        content = re.sub(
            r'id="nq-price-val">\$[0-9,\.]+<',
            f'id="nq-price-val">${nq_item["last"]:,.2f}<',
            content
        )
        content = re.sub(
            r'id="nq-chg-val">[+\-0-9\.\%]+<',
            f'id="nq-chg-val">{"+" if nq_item["chgPct"]>=0 else ""}{nq_item["chgPct"]:.2f}%<',
            content
        )

    if btc_item:
        content = re.sub(
            r'window\.W_TERMINAL\.barsBTC\s*=\s*generateBaselineBars\([0-9\.]+',
            f'window.W_TERMINAL.barsBTC = generateBaselineBars({btc_item["last"]:.2f}',
            content
        )
        content = re.sub(
            r'id="btc-price-val">\$[0-9,\.]+<',
            f'id="btc-price-val">${btc_item["last"]:,.2f}<',
            content
        )
        content = re.sub(
            r'id="btc-chg-val">[+\-0-9\.\%]+<',
            f'id="btc-chg-val">{"+" if btc_item["chgPct"]>=0 else ""}{btc_item["chgPct"]:.2f}%<',
            content
        )
        content = re.sub(
            r'id="hm-spot-val">\$[0-9,\.]+<',
            f'id="hm-spot-val">${btc_item["last"]:,.2f}<',
            content
        )

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[SUCCESS] Successfully updated {INDEX_PATH} with {len(new_universe)} assets and {len(new_news)} news items.")
    return True

if __name__ == "__main__":
    success = update_index_html()
    sys.exit(0 if success else 1)
