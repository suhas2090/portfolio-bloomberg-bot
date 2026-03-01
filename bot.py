"""
╔══════════════════════════════════════════════════════════╗
║       🏦 PERSONAL BLOOMBERG — TELEGRAM AI AGENT          ║
║   Stocks: Genus Power | ACE | IREDA | Jio Fin |          ║
║           Websol Energy | Bajel Projects                 ║
╚══════════════════════════════════════════════════════════╝

Commands available:
  /start       - Welcome + command list
  /prices      - Live portfolio prices + P&L
  /filings     - Latest NSE/BSE corporate announcements
  /news        - Supply chain & sector news digest
  /analysis    - AI buy/hold/sell for each stock
  /macro       - Political & macro event impact
  /weekly      - Full weekly industry report
  /broker      - Brokerage targets & concall highlights
  /ask <text>  - Ask AI anything about your portfolio
  /portfolio   - Portfolio summary with allocation
  /alert       - Run full scan + push all alerts
"""

import os
import re
import json
import time
import logging
import datetime
import requests
import feedparser
import yfinance as yf
import httpx
from telegram import Update, ParseMode
from telegram.ext import (
    Updater, CommandHandler, MessageHandler,
    Filters, CallbackContext
)
from flask import Flask
from threading import Thread

# ── Logging ────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════

TELEGRAM_TOKEN     = os.environ.get("TELEGRAM_TOKEN", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
ALLOWED_CHAT_ID    = os.environ.get("ALLOWED_CHAT_ID", "")
RENDER_URL         = os.environ.get("RENDER_URL", "")

# ── Portfolio ───────────────────────────────────────────────
PORTFOLIO = {
    "GENUSPOWER": {
        "name": "Genus Power Infrastructure",
        "exchange": "NSE", "bse_code": "514992",
        "qty": 100, "avg_price": 350.0,
        "industry": "Smart Metering / Electrical Equipment",
        "peers": ["HPL Electric", "Honeywell Automation"],
        "key_suppliers": ["STMicroelectronics", "Renesas", "PCB manufacturers"],
        "key_clients": ["DISCOMS", "AEML", "TPDDL", "UP Electricity Dept"],
    },
    "ACE": {
        "name": "Action Construction Equipment",
        "exchange": "NSE", "bse_code": "532762",
        "qty": 50, "avg_price": 900.0,
        "industry": "Construction & Material Handling Equipment",
        "peers": ["BEML", "Escorts Kubota", "Jupiter Wagons"],
        "key_suppliers": ["Cummins India", "TAFE Perkins", "Steel suppliers"],
        "key_clients": ["L&T", "NCC Limited", "Government contractors"],
    },
    "IREDA": {
        "name": "IREDA",
        "exchange": "NSE", "bse_code": "544097",
        "qty": 200, "avg_price": 180.0,
        "industry": "Renewable Energy NBFC",
        "peers": ["PFC", "RECLTD", "HUDCO"],
        "key_suppliers": ["N/A - Financial Institution"],
        "key_clients": ["Adani Green", "Greenko", "ReNew Power", "Solar IPPs"],
    },
    "JIOFIN": {
        "name": "Jio Financial Services",
        "exchange": "NSE", "bse_code": "543865",
        "qty": 75, "avg_price": 250.0,
        "industry": "NBFC / Financial Services",
        "peers": ["Bajaj Finance", "Shriram Finance", "Muthoot Finance"],
        "key_suppliers": ["Reliance / Jio tech stack"],
        "key_clients": ["Retail borrowers", "Jio subscribers", "BlackRock JV"],
    },
    "WEBELSOLAR": {
        "name": "Websol Energy System",
        "exchange": "NSE", "bse_code": "517498",
        "qty": 150, "avg_price": 700.0,
        "industry": "Solar PV Manufacturing",
        "peers": ["Waaree Energies", "Premier Energies", "Borosil Renewables"],
        "key_suppliers": ["LONGi Solar", "Daqo (polysilicon)", "Silver paste suppliers"],
        "key_clients": ["SECI", "NTPC", "EPC companies", "European export buyers"],
    },
    "BAJEL": {
        "name": "Bajel Projects",
        "exchange": "NSE", "bse_code": "544076",
        "qty": 100, "avg_price": 400.0,
        "industry": "Power T&D EPC",
        "peers": ["KEC International", "Kalpataru Projects", "Techno Electric"],
        "key_suppliers": ["Steel suppliers", "Copper wire", "Transformer manufacturers"],
        "key_clients": ["Power Grid Corp", "State Transmission Utilities", "Industrial clients"],
    },
}

SUPPLY_CHAIN_WATCHLIST = [
    "NTPC India", "Power Grid Corporation India", "SECI solar",
    "Adani Green Energy", "LONGi solar production", "polysilicon supply India",
    "Cummins India", "Reliance Industries", "REC Limited India",
    "L&T construction India", "NCC Limited India"
]

# ══════════════════════════════════════════════════════════
# AI — OpenRouter (Free, no quota issues)
# ══════════════════════════════════════════════════════════

_chat_sessions = {}

def ask_ai(prompt: str, retries=3) -> str:
    """Send prompt to OpenRouter AI and return response."""
    for i in range(retries):
        try:
            response = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/portfolio-bot",
                    "X-Title": "Portfolio Bloomberg Bot"
                },
                json={
                    "model": "meta-llama/llama-3.1-8b-instruct:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1024
                },
                timeout=30
            )
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            if i < retries - 1:
                time.sleep(2)
            else:
                return f"⚠️ AI unavailable: {str(e)[:80]}"

# ══════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════

def get_news(query: str, n=5) -> list:
    try:
        url = (
            f"https://news.google.com/rss/search"
            f"?q={requests.utils.quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"
        )
        feed = feedparser.parse(url)
        return [
            {"title": e.get("title",""), "link": e.get("link",""),
             "published": e.get("published",""), "summary": e.get("summary","")}
            for e in feed.entries[:n]
        ]
    except:
        return []

def get_price(symbol: str) -> dict:
    try:
        t = yf.Ticker(f"{symbol}.NS")
        h = t.history(period="5d")
        if h.empty:
            t = yf.Ticker(f"{symbol}.BO")
            h = t.history(period="5d")
        if h.empty:
            return {}
        cur  = round(h["Close"].iloc[-1], 2)
        prev = round(h["Close"].iloc[-2], 2) if len(h) > 1 else cur
        d_chg = round(cur - prev, 2)
        d_pct = round((d_chg / prev) * 100, 2) if prev else 0
        h1y  = t.history(period="1y")
        hi52 = round(h1y["High"].max(), 2) if not h1y.empty else cur
        lo52 = round(h1y["Low"].min(), 2)  if not h1y.empty else cur
        return {"price": cur, "prev": prev, "day_chg": d_chg,
                "day_pct": d_pct, "hi52": hi52, "lo52": lo52}
    except Exception as e:
        log.warning(f"Price fetch failed for {symbol}: {e}")
        return {}

def safe_send(context: CallbackContext, chat_id, text: str, parse_mode=ParseMode.HTML):
    for i in range(0, len(text), 4000):
        context.bot.send_message(
            chat_id=chat_id, text=text[i:i+4000],
            parse_mode=parse_mode, disable_web_page_preview=True,
        )
        time.sleep(0.3)

def is_authorised(update: Update) -> bool:
    if not ALLOWED_CHAT_ID:
        return True
    return str(update.effective_chat.id) == str(ALLOWED_CHAT_ID)

def auth_fail(update: Update):
    update.message.reply_text("🔒 Unauthorised. This is a private bot.")

def e_chg(pct):  return "🟢" if pct >= 0 else "🔴"
def e_pri(p):    return {"HIGH":"🚨","MEDIUM":"🟡","LOW":"ℹ️"}.get(p,"⚪")
def e_imp(i):    return {"POSITIVE":"🟢","NEGATIVE":"🔴","NEUTRAL":"⚪","MIXED":"🟡"}.get(i,"⚪")

def portfolio_context_str() -> str:
    return "\n".join(
        f"  {s}: {d['name']} | {d['industry']} | Avg ₹{d['avg_price']} × {d['qty']} shares"
        for s, d in PORTFOLIO.items()
    )

# ══════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ══════════════════════════════════════════════════════════

def cmd_start(update: Update, context: CallbackContext):
    if not is_authorised(update): return auth_fail(update)
    msg = (
        "🏦 <b>Personal Bloomberg — Portfolio AI Agent</b>\n\n"
        "Your 6 stocks are loaded. Here's what I can do:\n\n"
        "📊 <b>/prices</b> — Live prices + P&amp;L\n"
        "📋 <b>/filings</b> — Latest corporate announcements\n"
        "📰 <b>/news</b> — Supply chain &amp; sector news\n"
        "💡 <b>/analysis</b> — AI buy/hold/sell signals\n"
        "🏛️ <b>/macro</b> — Political &amp; RBI/Budget impact\n"
        "📈 <b>/weekly</b> — Weekly industry report\n"
        "🎯 <b>/broker</b> — Analyst targets &amp; concall highlights\n"
        "💼 <b>/portfolio</b> — Holdings summary\n"
        "🔔 <b>/alert</b> — Run full scan now\n\n"
        "🤖 <b>/ask</b> <i>your question</i> — Ask me anything\n"
        "   <i>Example: /ask Should I average down on Websol?</i>\n\n"
        "Or just <b>type naturally</b> — I'll understand!\n\n"
        "⚠️ <i>AI analysis only — not SEBI-registered advice</i>"
    )
    update.message.reply_text(msg, parse_mode=ParseMode.HTML)


def cmd_prices(update: Update, context: CallbackContext):
    if not is_authorised(update): return auth_fail(update)
    update.message.reply_text("⏳ Fetching live prices...")

    msg  = f"💰 <b>PORTFOLIO PRICES</b>\n"
    msg += f"🕐 {datetime.datetime.now().strftime('%d %b %Y, %I:%M %p IST')}\n"
    msg += "─" * 30 + "\n\n"
    total_invested = total_current = 0

    for sym, info in PORTFOLIO.items():
        p = get_price(sym)
        if not p:
            msg += f"⚠️ {sym}: Price unavailable\n\n"
            continue
        cur     = p["price"]
        avg     = info["avg_price"]
        qty     = info["qty"]
        invested= avg * qty
        current = cur * qty
        pnl     = current - invested
        pnl_pct = ((cur - avg) / avg) * 100
        total_invested += invested
        total_current  += current
        arrow = "▲" if p["day_pct"] >= 0 else "▼"
        msg += (
            f"{e_chg(p['day_pct'])} <b>{sym}</b> — ₹{cur}\n"
            f"   {arrow} Day: {p['day_pct']:+.2f}%  |  52W: ₹{p['lo52']}–{p['hi52']}\n"
            f"   P&amp;L: {e_chg(pnl)} ₹{pnl:+,.0f} ({pnl_pct:+.1f}%)\n\n"
        )

    total_pnl = total_current - total_invested
    total_pct = (total_pnl / total_invested * 100) if total_invested else 0
    msg += "─" * 30 + "\n"
    msg += f"💼 <b>TOTAL INVESTED:</b>  ₹{total_invested:,.0f}\n"
    msg += f"📈 <b>CURRENT VALUE:</b>   ₹{total_current:,.0f}\n"
    msg += f"{e_chg(total_pnl)} <b>TOTAL P&amp;L:</b>       ₹{total_pnl:+,.0f} ({total_pct:+.1f}%)\n"
    msg += "\n<i>Prices ~15 min delayed (Yahoo Finance)</i>"
    safe_send(context, update.effective_chat.id, msg)


def cmd_filings(update: Update, context: CallbackContext):
    if not is_authorised(update): return auth_fail(update)
    update.message.reply_text("🔍 Fetching latest announcements & running AI analysis...")

    msg  = "📋 <b>CORPORATE FILINGS — AI ANALYSIS</b>\n"
    msg += f"📅 Last 7 days | {datetime.datetime.now().strftime('%d %b %Y')}\n"
    msg += "─" * 30 + "\n\n"

    for sym, info in PORTFOLIO.items():
        news = get_news(f"{info['name']} NSE BSE announcement India", n=3)
        if not news:
            msg += f"📭 <b>{sym}</b>: No recent filings found\n\n"
            continue
        for item in news[:2]:
            title = item["title"]
            prompt = f"""Classify this Indian stock filing for a retail investor.
Company: {info['name']} ({sym}), Industry: {info['industry']}
Filing: "{title}"
Reply ONLY as valid JSON (no markdown):
{{"priority":"HIGH/MEDIUM/LOW","impact":"POSITIVE/NEGATIVE/NEUTRAL","explanation":"2 sentences plain English","action":"1 sentence what to watch"}}
HIGH = Results, major orders, M&A, fundraise, regulatory action
MEDIUM = AGM, pledge change, investor meet
LOW = Routine compliance, board meeting date"""
            raw = ask_ai(prompt)
            try:
                m = re.search(r'\{.*?\}', raw, re.DOTALL)
                data = json.loads(m.group()) if m else {}
            except:
                data = {}
            pri = data.get("priority","MEDIUM")
            imp = data.get("impact","NEUTRAL")
            msg += (
                f"{e_pri(pri)} <b>{sym}</b> [{pri}] {e_imp(imp)}\n"
                f"📄 {title[:90]}\n"
                f"💬 {data.get('explanation', title)}\n"
                f"👉 {data.get('action','')}\n\n"
            )
            time.sleep(0.5)
    safe_send(context, update.effective_chat.id, msg)


def cmd_news(update: Update, context: CallbackContext):
    if not is_authorised(update): return auth_fail(update)
    update.message.reply_text("📰 Scanning supply chain & sector news...")

    DISRUPTION_KW = ["disruption","delay","halt","crisis","shortage","problem",
                     "issue","loss","penalty","default","bankruptcy","strike",
                     "cancel","stalled","ban","investigation","fire","accident"]

    msg  = "📰 <b>SUPPLY CHAIN & SECTOR NEWS</b>\n"
    msg += f"📅 {datetime.datetime.now().strftime('%d %b %Y, %I:%M %p')}\n"
    msg += "─" * 30 + "\n\n"
    msg += "🔗 <b>SUPPLY CHAIN WATCH</b>\n\n"
    alerts_found = False

    for entity in SUPPLY_CHAIN_WATCHLIST[:6]:
        items = get_news(f"{entity} disruption problem 2025", n=2)
        for item in items:
            if any(kw in item["title"].lower() for kw in DISRUPTION_KW):
                prompt = f"""Indian stock analyst. Does this news affect any of these stocks?
Stocks: {', '.join(PORTFOLIO.keys())} (industries: Smart Metering, Construction Equipment, Renewable NBFC, NBFC, Solar PV, Power T&D)
News about {entity}: "{item['title']}"
Reply ONLY as valid JSON: {{"relevant":true/false,"stocks":["SYM1"],"severity":"HIGH/MEDIUM/LOW","explanation":"2 sentences"}}"""
                raw = ask_ai(prompt)
                try:
                    m = re.search(r'\{.*?\}', raw, re.DOTALL)
                    d = json.loads(m.group()) if m else {}
                except:
                    d = {}
                if d.get("relevant"):
                    sev = d.get("severity","MEDIUM")
                    msg += (
                        f"{e_pri(sev)} <b>{entity}</b> [{sev}]\n"
                        f"📌 {item['title'][:90]}\n"
                        f"🎯 Affects: {', '.join(d.get('stocks',[]))}\n"
                        f"💬 {d.get('explanation','')[:150]}\n\n"
                    )
                    alerts_found = True
                time.sleep(0.5)

    if not alerts_found:
        msg += "✅ No significant supply chain disruptions detected.\n\n"

    msg += "─" * 30 + "\n🏭 <b>SECTOR HEADLINES</b>\n\n"
    for sym, info in list(PORTFOLIO.items())[:3]:
        items = get_news(f"{info['industry']} India 2025", n=2)
        if items:
            msg += f"<b>{sym} — {info['industry']}</b>\n"
            for it in items[:2]:
                msg += f"  • {it['title'][:80]}\n"
            msg += "\n"
    safe_send(context, update.effective_chat.id, msg)


def cmd_analysis(update: Update, context: CallbackContext):
    if not is_authorised(update): return auth_fail(update)
    update.message.reply_text("💡 Running AI buy/hold/sell analysis for all 6 stocks...")

    msg  = "💡 <b>BUY / HOLD / AVERAGE / SELL ANALYSIS</b>\n"
    msg += f"📅 {datetime.datetime.now().strftime('%d %b %Y')}\n"
    msg += "⚠️ <i>AI analysis only — not SEBI financial advice</i>\n"
    msg += "─" * 30 + "\n\n"
    ACTION_EMOJI = {"BUY MORE":"🟢","AVERAGE DOWN":"🔵","HOLD":"🟡","PARTIAL SELL":"🟠","SELL":"🔴"}

    for sym, info in PORTFOLIO.items():
        p = get_price(sym)
        if not p:
            msg += f"⚠️ {sym}: Could not fetch price data\n\n"
            continue
        cur     = p["price"]
        avg     = info["avg_price"]
        pnl_pct = ((cur - avg) / avg) * 100
        frm_52hi= ((cur - p["hi52"]) / p["hi52"]) * 100
        news    = get_news(f"{info['name']} India results outlook 2025", n=4)
        headlines = "\n".join(f"- {n['title']}" for n in news)

        prompt = f"""Senior Indian equity analyst. Give buy/hold/sell recommendation:
Stock: {info['name']} ({sym}) | Industry: {info['industry']}
Current Price: ₹{cur} | My Avg Buy: ₹{avg}
My P&L: {pnl_pct:+.1f}% | From 52W High: {frm_52hi:.1f}%
52W Range: ₹{p['lo52']} – ₹{p['hi52']}
Peers: {', '.join(info['peers'])}
Recent news:
{headlines[:800]}
Reply ONLY as valid JSON:
{{"action":"BUY MORE/AVERAGE DOWN/HOLD/PARTIAL SELL/SELL","confidence":"HIGH/MEDIUM/LOW","reasoning":"3 sentences why","risk":"biggest risk in 1 sentence","catalyst":"best upcoming catalyst in 1 sentence","target":"rough ₹ range e.g. ₹400-450"}}"""

        raw = ask_ai(prompt)
        try:
            m = re.search(r'\{.*?\}', raw, re.DOTALL)
            d = json.loads(m.group()) if m else {}
        except:
            d = {}
        action = d.get("action","HOLD")
        msg += (
            f"{ACTION_EMOJI.get(action,'⚪')} <b>{sym}</b> — {action} [{d.get('confidence','MEDIUM')}]\n"
            f"   {e_chg(pnl_pct)} Price: ₹{cur}  |  P&amp;L: {pnl_pct:+.1f}%\n"
            f"   🎯 Target: {d.get('target','N/A')}\n"
            f"   💬 {d.get('reasoning','')[:180]}\n"
            f"   ⚠️ Risk: {d.get('risk','')[:100]}\n"
            f"   🚀 Catalyst: {d.get('catalyst','')[:100]}\n\n"
        )
        time.sleep(1)
    safe_send(context, update.effective_chat.id, msg)


def cmd_macro(update: Update, context: CallbackContext):
    if not is_authorised(update): return auth_fail(update)
    update.message.reply_text("🏛️ Analysing political & macro events...")

    macro_queries = [
        "India RBI monetary policy interest rate 2025",
        "India Union Budget announcement 2025",
        "India PLI scheme solar energy infrastructure",
        "India China trade policy 2025",
        "India US tariff trade relations 2025",
        "India election BJP policy infrastructure renewable energy",
    ]
    all_news = []
    for q in macro_queries:
        all_news.extend(get_news(q, n=2))
    seen  = set()
    unique= [n for n in all_news if not (n["title"] in seen or seen.add(n["title"]))]
    headlines = "\n".join(f"- {n['title']}" for n in unique[:14])
    portfolio_str = "\n".join(f"  {s}: {i['name']} ({i['industry']})" for s,i in PORTFOLIO.items())

    prompt = f"""Senior Indian equity analyst. Analyse macro/political events for a retail investor's portfolio.
RECENT EVENTS:
{headlines}
PORTFOLIO:
{portfolio_str}
Identify up to 5 relevant events. Reply ONLY as a JSON array:
[{{"event":"short description","severity":"HIGH/MEDIUM/LOW","impact":"POSITIVE/NEGATIVE/MIXED/NEUTRAL","stocks":["SYM"],"explanation":"2 sentences plain English","action":"1 sentence what investor should do"}}]
Skip irrelevant events. Be direct and specific to these exact stocks."""

    raw = ask_ai(prompt)
    try:
        m = re.search(r'\[.*?\]', raw, re.DOTALL)
        events = json.loads(m.group()) if m else []
    except:
        events = []

    msg  = "🏛️ <b>POLITICAL &amp; MACRO EVENT IMPACT</b>\n"
    msg += f"📅 {datetime.datetime.now().strftime('%d %b %Y')}\n"
    msg += "─" * 30 + "\n\n"
    if not events:
        msg += "✅ No major macro events with significant portfolio impact detected today.\n"
    else:
        for ev in events:
            sev = ev.get("severity","MEDIUM")
            imp = ev.get("impact","NEUTRAL")
            msg += (
                f"{e_pri(sev)} <b>[{sev}]</b> {e_imp(imp)} {imp}\n"
                f"📌 {ev.get('event','')[:100]}\n"
                f"🎯 Affects: {', '.join(ev.get('stocks',[]))}\n"
                f"💬 {ev.get('explanation','')[:200]}\n"
                f"👉 {ev.get('action','')[:120]}\n\n"
            )
    safe_send(context, update.effective_chat.id, msg)


def cmd_weekly(update: Update, context: CallbackContext):
    if not is_authorised(update): return auth_fail(update)
    update.message.reply_text("📈 Generating weekly industry report (takes ~60 seconds)...")

    msg  = "📈 <b>WEEKLY INDUSTRY REPORT</b>\n"
    msg += f"Week ending {datetime.datetime.now().strftime('%d %b %Y')}\n"
    msg += "─" * 30 + "\n\n"

    for sym, info in PORTFOLIO.items():
        co_news   = get_news(f"{info['name']} India 2025", n=4)
        sec_news  = get_news(f"{info['industry']} India market news 2025", n=3)
        res_news  = get_news(f"{info['name']} quarterly results earnings 2025", n=2)
        peer_news = []
        for peer in info["peers"][:2]:
            peer_news += get_news(f"{peer} India results 2025", n=1)

        headlines = "\n".join(
            [f"COMPANY: {n['title']}" for n in co_news] +
            [f"SECTOR: {n['title']}" for n in sec_news] +
            [f"RESULTS: {n['title']}" for n in res_news] +
            [f"PEER: {n['title']}" for n in peer_news]
        )
        prompt = f"""Write a weekly briefing for Indian retail investor about {info['name']} ({sym}).
Industry: {info['industry']} | Peers: {', '.join(info['peers'])}
News this week:
{headlines[:1500]}
Write 4 short sections (2-3 sentences each):
1. INDUSTRY PULSE — how the sector is doing
2. COMPANY UPDATE — key {sym} news
3. PEERS — what competitors are doing
4. RESULTS & OUTLOOK — any quarterly numbers + near-term view
Plain English. Specific and factual. No fluff."""

        section = ask_ai(prompt)
        msg += f"🏢 <b>{sym} — {info['name']}</b>\n{section}\n"
        msg += "─" * 30 + "\n\n"
        time.sleep(1)
    safe_send(context, update.effective_chat.id, msg)


def cmd_broker(update: Update, context: CallbackContext):
    if not is_authorised(update): return auth_fail(update)
    update.message.reply_text("🎯 Fetching broker targets & concall highlights...")

    msg  = "🎯 <b>BROKER TARGETS &amp; CONCALL TRACKER</b>\n"
    msg += f"📅 {datetime.datetime.now().strftime('%d %b %Y')}\n"
    msg += "─" * 30 + "\n\n"
    CONSENSUS_EMOJI = {"BULLISH":"🟢","NEUTRAL":"🟡","BEARISH":"🔴"}

    for sym, info in PORTFOLIO.items():
        broker_news  = get_news(f"{info['name']} target price analyst rating buy sell 2025", n=4)
        concall_news = get_news(f"{info['name']} concall earnings call guidance management 2025", n=3)
        all_hl = "\n".join(
            [f"BROKER: {n['title']} | {n.get('summary','')[:80]}" for n in broker_news] +
            [f"CONCALL: {n['title']} | {n.get('summary','')[:80]}" for n in concall_news]
        )
        if not all_hl.strip():
            msg += f"📭 <b>{sym}</b>: No broker/concall data found\n\n"
            continue

        prompt = f"""Extract broker recommendations and concall highlights for {info['name']} ({sym}).
Data found:
{all_hl[:2000]}
Reply ONLY as valid JSON:
{{"brokers":[{{"name":"broker","target":"₹XXX","rating":"Buy/Hold/Sell"}}],"concall_points":["point 1","point 2","point 3"],"consensus":"BULLISH/NEUTRAL/BEARISH","guidance":"1 sentence key management forward guidance"}}
If data unavailable use empty array/null. Be honest."""

        raw = ask_ai(prompt)
        try:
            m = re.search(r'\{.*?\}', raw, re.DOTALL)
            d = json.loads(m.group()) if m else {}
        except:
            d = {}

        consensus = d.get("consensus","NEUTRAL")
        msg += f"{CONSENSUS_EMOJI.get(consensus,'⚪')} <b>{sym}</b> — Consensus: {consensus}\n"
        for b in d.get("brokers",[])[:3]:
            msg += f"   📊 {b.get('name','?')}: {b.get('target','?')} ({b.get('rating','?')})\n"
        for pt in d.get("concall_points",[])[:3]:
            msg += f"   🎙️ {pt[:100]}\n"
        if d.get("guidance"):
            msg += f"   👔 {d['guidance'][:150]}\n"
        msg += "\n"
        time.sleep(1)
    safe_send(context, update.effective_chat.id, msg)


def cmd_portfolio(update: Update, context: CallbackContext):
    if not is_authorised(update): return auth_fail(update)
    msg   = "💼 <b>PORTFOLIO HOLDINGS</b>\n" + "─" * 30 + "\n\n"
    total = sum(i["avg_price"] * i["qty"] for i in PORTFOLIO.values())
    for sym, info in PORTFOLIO.items():
        val   = info["avg_price"] * info["qty"]
        alloc = (val / total * 100) if total else 0
        msg  += (
            f"<b>{sym}</b> — {info['name']}\n"
            f"   📌 {info['industry']}\n"
            f"   🔢 {info['qty']} shares @ ₹{info['avg_price']}\n"
            f"   💰 Invested: ₹{val:,.0f} ({alloc:.1f}% of portfolio)\n"
            f"   👥 Peers: {', '.join(info['peers'][:2])}\n\n"
        )
    msg += "─" * 30 + f"\n💼 <b>Total Invested: ₹{total:,.0f}</b>\n\nUse /prices for live P&amp;L"
    safe_send(context, update.effective_chat.id, msg)


def cmd_alert(update: Update, context: CallbackContext):
    if not is_authorised(update): return auth_fail(update)
    update.message.reply_text("🔔 Running full portfolio scan...\nThis will take 2–3 minutes. I'll send each section as it's ready.")
    cmd_prices(update, context);   time.sleep(1)
    cmd_filings(update, context);  time.sleep(1)
    cmd_news(update, context);     time.sleep(1)
    cmd_macro(update, context);    time.sleep(1)
    cmd_analysis(update, context)
    update.message.reply_text(
        "✅ <b>Full scan complete!</b>\n\nUse /weekly for industry report\nUse /broker for analyst targets\nUse /ask to ask me anything",
        parse_mode=ParseMode.HTML
    )


def cmd_ask(update: Update, context: CallbackContext):
    if not is_authorised(update): return auth_fail(update)
    question = " ".join(context.args) if context.args else ""
    if not question:
        update.message.reply_text(
            "💬 Usage: <code>/ask your question here</code>\n\n"
            "Examples:\n• /ask Should I average down on Websol?\n"
            "• /ask How will RBI rate cuts affect Jio Financial?\n"
            "• /ask Compare IREDA vs PFC vs REC\n"
            "• /ask What's the PLI scheme impact on my stocks?",
            parse_mode=ParseMode.HTML
        )
        return
    _handle_question(update, context, question)


def handle_text(update: Update, context: CallbackContext):
    if not is_authorised(update): return auth_fail(update)
    text = update.message.text.strip()
    if text.startswith("/"): return
    _handle_question(update, context, text)


def _handle_question(update: Update, context: CallbackContext, question: str):
    chat_id = str(update.effective_chat.id)
    update.message.reply_text("🤖 Thinking...")
    if chat_id not in _chat_sessions:
        _chat_sessions[chat_id] = []
    history = _chat_sessions[chat_id]

    system = f"""You are a personal AI stock market analyst for an Indian retail investor.
THEIR PORTFOLIO:
{portfolio_context_str()}
SUPPLY CHAIN MONITORED: {', '.join(SUPPLY_CHAIN_WATCHLIST[:6])}
Rules:
- Answer conversationally like a knowledgeable friend
- Be specific to THEIR exact stocks and situation
- Reference real Indian market context (SEBI, RBI, NSE, PLI schemes, budget etc.)
- Always end with a brief disclaimer that this is educational, not SEBI-registered advice
- Keep answers concise — max 300 words unless asked for detail"""

    conv = system + "\n\nCONVERSATION HISTORY:\n"
    for h in history[-6:]:
        conv += f"{h['role'].upper()}: {h['content']}\n"
    conv += f"\nUSER: {question}\nASSISTANT:"

    answer = ask_ai(conv)
    history.append({"role":"user","content":question})
    history.append({"role":"assistant","content":answer})
    _chat_sessions[chat_id] = history[-10:]
    safe_send(context, update.effective_chat.id, f"🤖 {answer}")


# ══════════════════════════════════════════════════════════
# SCHEDULED JOBS
# ══════════════════════════════════════════════════════════

def scheduled_price_alert(context: CallbackContext):
    if not ALLOWED_CHAT_ID: return
    log.info("Running scheduled price alert...")
    try:
        msg  = f"📊 <b>MARKET CLOSE UPDATE</b>\n"
        msg += f"🕐 {datetime.datetime.now().strftime('%d %b %Y, 3:45 PM IST')}\n"
        msg += "─" * 25 + "\n\n"
        total_invested = total_current = 0
        for sym, info in PORTFOLIO.items():
            p = get_price(sym)
            if not p: continue
            cur     = p["price"]
            pnl_pct = ((cur - info["avg_price"]) / info["avg_price"]) * 100
            total_invested += info["avg_price"] * info["qty"]
            total_current  += cur * info["qty"]
            msg += f"{e_chg(p['day_pct'])} <b>{sym}</b>: ₹{cur} ({p['day_pct']:+.2f}%) | P&amp;L: {pnl_pct:+.1f}%\n"
        total_pnl = total_current - total_invested
        total_pct = (total_pnl / total_invested * 100) if total_invested else 0
        msg += f"\n{e_chg(total_pnl)} <b>Portfolio P&amp;L: ₹{total_pnl:+,.0f} ({total_pct:+.1f}%)</b>"
        context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.error(f"Scheduled price alert error: {e}")


def scheduled_filing_check(context: CallbackContext):
    if not ALLOWED_CHAT_ID: return
    log.info("Running scheduled filing check...")
    high_priority_found = []
    for sym, info in PORTFOLIO.items():
        news = get_news(f"{info['name']} NSE BSE announcement India", n=2)
        for item in news[:1]:
            prompt = f"""Classify this Indian stock filing. Company: {info['name']} ({sym})
Filing: "{item['title']}"
Reply ONLY as valid JSON: {{"priority":"HIGH/MEDIUM/LOW","explanation":"1 sentence"}}
HIGH = Results, major orders, M&A, fundraise, regulatory action"""
            raw = ask_ai(prompt)
            try:
                m = re.search(r'\{.*?\}', raw, re.DOTALL)
                d = json.loads(m.group()) if m else {}
            except:
                d = {}
            if d.get("priority") == "HIGH":
                high_priority_found.append({"sym":sym,"title":item["title"],"explanation":d.get("explanation","")})
        time.sleep(0.5)

    if high_priority_found:
        msg = "🚨 <b>HIGH PRIORITY FILING ALERT</b>\n\n"
        for f in high_priority_found:
            msg += f"🏢 <b>{f['sym']}</b>\n📄 {f['title'][:90]}\n💬 {f['explanation']}\n\n"
        try:
            context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=msg, parse_mode=ParseMode.HTML)
        except Exception as e:
            log.error(f"Filing alert send error: {e}")


# ══════════════════════════════════════════════════════════
# KEEP-ALIVE SERVER
# ══════════════════════════════════════════════════════════

keep_alive_app = Flask(__name__)

@keep_alive_app.route("/")
def home(): return "🏦 Portfolio Bot is running!", 200

@keep_alive_app.route("/ping")
def ping(): return "pong", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    keep_alive_app.run(host="0.0.0.0", port=port)

def start_keep_alive():
    Thread(target=run_flask, daemon=True).start()
    log.info("Keep-alive Flask server started")


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN environment variable not set!")
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY environment variable not set!")

    start_keep_alive()

    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    jq = updater.job_queue

    dp.add_handler(CommandHandler("start",     cmd_start))
    dp.add_handler(CommandHandler("prices",    cmd_prices))
    dp.add_handler(CommandHandler("filings",   cmd_filings))
    dp.add_handler(CommandHandler("news",      cmd_news))
    dp.add_handler(CommandHandler("analysis",  cmd_analysis))
    dp.add_handler(CommandHandler("macro",     cmd_macro))
    dp.add_handler(CommandHandler("weekly",    cmd_weekly))
    dp.add_handler(CommandHandler("broker",    cmd_broker))
    dp.add_handler(CommandHandler("portfolio", cmd_portfolio))
    dp.add_handler(CommandHandler("alert",     cmd_alert))
    dp.add_handler(CommandHandler("ask",       cmd_ask))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

    # 3:45 PM IST = 10:15 UTC, Mon–Fri
    jq.run_daily(scheduled_price_alert, time=datetime.time(hour=10, minute=15), days=(0,1,2,3,4))
    # Filing check every 4 hours
    jq.run_repeating(scheduled_filing_check, interval=14400, first=60)

    log.info("🚀 Portfolio Bot started!")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
