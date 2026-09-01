import requests
import time
import json
import os
import sys
from datetime import datetime
from xml.etree import ElementTree as ET
import pytz

TELEGRAM_TOKEN = "8800189995:AAEWA3PQ1JuaRmTjeQb9V4IL-QU4nnlH2Bs"
ADMIN_IDS      = ["6360489611", "8315710670", "1266693223"]
BROADCASTER_ID = "6360489611"
MEMBERS_FILE   = "members.json"
OFFSET_FILE    = "offset.json"
STATE_FILE     = "bot_state.json"

SWING_LEN      = 10
OB_LOOKBACK    = 60
OB_MAX_TOUCH   = 3
MAX_OB_KEEP    = 5
SL_BUFFER_PCT  = 0.15
MIN_RR         = 2.0
USE_WICK_TOUCH = True
REQUIRE_IDM    = False
GAZA_TZ        = pytz.timezone("Asia/Gaza")

# حجم اللوت المستخدم لحساب الربح/الخسارة بالدولار (1 لوت = 100 أونصة ذهب)
LOT_SIZE       = 0.01
CONTRACT_SIZE  = 100  # أونصة لكل لوت قياسي

# ==================== قفل النسخة الواحدة ====================
LOCK_FILE = "/tmp/smc_bot.lock"

def acquire_single_instance_lock():
    """يمنع اشتغال أكثر من نسخة من البوت بنفس الوقت (سبب تكرار الرسائل)."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = f.read().strip()
            if old_pid and os.path.exists(f"/proc/{old_pid}"):
                print(f"⚠️ في نسخة شغالة أصلاً (PID {old_pid}). ما رح أشغّل نسخة ثانية.")
                sys.exit(0)
        except Exception:
            pass
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

def release_single_instance_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass

# ==================== الأعضاء ====================
def load_members():
    if os.path.exists(MEMBERS_FILE):
        with open(MEMBERS_FILE, "r") as f:
            members = json.load(f)
        # تنظيف أي تكرار قديم صار بسبب race condition أيام تشغيل نسختين بالغلط
        deduped = list(dict.fromkeys(str(m) for m in members))
        if len(deduped) != len(members):
            print(f"🧹 تم حذف {len(members) - len(deduped)} آيدي مكرر من members.json")
            save_members(deduped)
        return deduped
    save_members(ADMIN_IDS.copy())
    return ADMIN_IDS.copy()

def save_members(members):
    with open(MEMBERS_FILE, "w") as f:
        json.dump(members, f)

def load_offset():
    if os.path.exists(OFFSET_FILE):
        try:
            with open(OFFSET_FILE, "r") as f:
                return json.load(f).get("offset")
        except Exception:
            return None
    return None

def save_offset(offset):
    try:
        with open(OFFSET_FILE, "w") as f:
            json.dump({"offset": offset}, f)
    except Exception:
        pass

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"active_trade": None, "last_signal_time": "", "bot_started_at": ""}

def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass

def add_member(chat_id):
    members = load_members()
    chat_id = str(chat_id)
    if chat_id not in members:
        members.append(chat_id)
        members = list(dict.fromkeys(members))  # حماية إضافية من التكرار
        save_members(members)
        return True
    return False

def remove_member(chat_id):
    members = load_members()
    chat_id = str(chat_id)
    if chat_id in members and chat_id not in ADMIN_IDS:
        members.remove(chat_id)
        save_members(members)
        return True
    return False

# ==================== تيليغرام ====================
def send_telegram(msg, chat_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    targets = [str(chat_id)] if chat_id else load_members()
    for cid in targets:
        try:
            requests.post(url, data={"chat_id": cid, "text": msg, "parse_mode": "HTML"}, timeout=10)
        except Exception:
            pass

def broadcast(msg):
    send_telegram(msg)

# ==================== معالجة رسائل ====================
def handle_admin_message(chat_id, text, first_name):
    chat_id = str(chat_id)
    if text in ["/start", "/stop"]:
        handle_member_message(chat_id, text, first_name)
        return
    if text == "/members":
        members = load_members()
        send_telegram(f"👥 <b>الأعضاء:</b> {len(members)} عضو", chat_id)
        return
    if text == "/help":
        send_telegram("/members — عدد الأعضاء\n/help — المساعدة\nأي رسالة ثانية تتوصل للكل", chat_id)
        return
    if chat_id == BROADCASTER_ID:
        members = load_members()
        broadcast(f"📢 <b>رسالة من الإدارة:</b>\n━━━━━━━━━━━━━━━━━━\n{text}")
        send_telegram(f"✅ تم الإرسال لـ <b>{len(members)}</b> عضو", chat_id)
    else:
        send_telegram("أوامر الأدمن:\n/members\n/help", chat_id)

def handle_member_message(chat_id, text, first_name):
    chat_id = str(chat_id)
    if text == "/start":
        added = add_member(chat_id)
        if added:
            members = load_members()
            send_telegram(
                f"🎉 <b>أهلاً {first_name}!</b>\n━━━━━━━━━━━━━━━━━━\n"
                f"تم اشتراكك في <b>SMC Gold Bot</b> ✅\n"
                f"📊 XAU/USD | M5\n📈 إشارات شراء/بيع\n"
                f"📰 تنبيهات أخبار USD\n🌅 رسالة صباحية\n"
                f"للإلغاء: /stop", chat_id)
            for admin in ADMIN_IDS:
                send_telegram(f"👤 عضو جديد: {first_name}\nID: {chat_id}\nالمجموع: {len(members)}", admin)
        else:
            send_telegram(f"✅ أنت مشترك أصلاً!\nللإلغاء: /stop", chat_id)
        return
    if text == "/stop":
        if remove_member(chat_id):
            send_telegram(f"😔 تم إلغاء اشتراكك\nللاشتراك: /start", chat_id)
        else:
            send_telegram("أنت غير مشترك.", chat_id)
        return
    send_telegram(f"مرحباً {first_name} 👋\n/start — اشتراك\n/stop — إلغاء", chat_id)

def get_updates(offset=None):
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"timeout": 30, "offset": offset}, timeout=35)
        return r.json().get("result", [])
    except Exception:
        return []

def process_updates(offset):
    for update in get_updates(offset):
        offset = update["update_id"] + 1
        save_offset(offset)
        try:
            msg     = update.get("message", {})
            chat_id = msg.get("chat", {}).get("id")
            text    = msg.get("text", "").strip()
            first   = msg.get("from", {}).get("first_name", "")
            if not chat_id or not text:
                continue
            if str(chat_id) in ADMIN_IDS:
                handle_admin_message(chat_id, text, first)
            else:
                handle_member_message(chat_id, text, first)
        except Exception:
            pass
    return offset

# ==================== بيانات الذهب ====================
def get_candles():
    """جيب الشموع من Twelve Data - سعر فوري حقيقي مثل MT5"""
    try:
        r = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol"    : "XAU/USD",
                "interval"  : "5min",
                "outputsize": 200,
                "apikey"    : "0cef5bb56a314b6289f3db0b648f84b5"
            }, timeout=20)
        data = r.json()

        if "values" not in data:
            msg = data.get("message") or data.get("Note") or "لا بيانات"
            print(f"⚠️ Twelve Data: {msg}")
            return None

        candles = []
        for v in reversed(data["values"]):
            candles.append({
                "time" : v["datetime"],
                "open" : float(v["open"]),
                "high" : float(v["high"]),
                "low"  : float(v["low"]),
                "close": float(v["close"])
            })

        print(f"✅ Twelve Data: {len(candles)} شمعة | {candles[-1]['close']:.2f}")
        return candles if len(candles) >= 50 else None
    except Exception as e:
        print(f"❌ Twelve Data: {e}")
        return None

# ==================== أخبار ====================
def get_usd_news():
    try:
        r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.xml", timeout=15)
        root = ET.fromstring(r.content)
        news_list = []
        today = datetime.now(GAZA_TZ).date()
        for event in root.findall("event"):
            try:
                if event.findtext("country", "").upper() != "USD":
                    continue
                title  = event.findtext("title", "")
                impact = event.findtext("impact", "").lower()
                d_str  = event.findtext("date", "")
                t_str  = event.findtext("time", "")
                if not d_str or not t_str:
                    continue
                try:
                    dt_utc = datetime.strptime(f"{d_str} {t_str}", "%m-%d-%Y %I:%M%p")
                except Exception:
                    dt_utc = datetime.strptime(f"{d_str} {t_str}", "%m-%d-%Y %I:%M %p")
                dt_gaza = pytz.utc.localize(dt_utc).astimezone(GAZA_TZ)
                if dt_gaza.date() != today:
                    continue
                if impact in ["high", "medium", "low"]:
                    news_list.append({"title": title, "impact": impact,
                                       "time": dt_gaza, "time_str": dt_gaza.strftime("%I:%M %p")})
            except Exception:
                continue
        return sorted(news_list, key=lambda x: x["time"])
    except Exception as e:
        print(f"خطأ أخبار: {e}")
        return []

def is_high_impact_news_time(news_list):
    now = datetime.now(GAZA_TZ)
    for n in news_list:
        if n["impact"] == "high":
            diff = (n["time"] - now).total_seconds() / 60
            if -15 <= diff <= 15:
                return True, n
    return False, None

def send_news_message(news_list):
    if not news_list:
        return
    high   = [n for n in news_list if n["impact"] == "high"]
    medium = [n for n in news_list if n["impact"] == "medium"]
    msg = "👁️\n\n📰 USD News Today (Gaza Time)\n\n"
    if high:
        msg += "🔴 High Impact — Avoid trading:\n"
        for n in high:
            msg += f"   ⏰ {n['time_str']} | {n['title']}\n"
        msg += "\n"
    if medium:
        msg += "🟡 Medium Impact — Stay cautious:\n"
        for n in medium:
            msg += f"   ⏰ {n['time_str']} | {n['title']}\n"
        msg += "\n"
    msg += "⚠️ Avoid trading 15 minutes before & after high impact news."
    broadcast(msg)

def send_morning_message(news_list):
    now = datetime.now(GAZA_TZ)
    days_en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_en  = days_en[now.weekday()]
    high_news = [n for n in news_list if n["impact"] == "high"]
    news_warn = ""
    if high_news:
        news_warn = "\n\n⚠️ High Impact News Today:\n"
        for n in high_news:
            news_warn += f"🔴 {n['time_str']} | {n['title']}\n"
    broadcast(
        f"👁️\n\n"
        f"🌅 Good Morning Traders!\n"
        f"📅 {day_en} — {now.strftime('%d/%m/%Y')}"
        f"{news_warn}\n\n"
        f"🔍 Focus on clean setups only.\n"
        f"💡 Patience is the key — let the market come to you."
    )

# ==================== Pivot ====================
def pivot_high(highs, i, length):
    if i < length or i + length >= len(highs):
        return None
    val = highs[i]
    for j in range(1, length + 1):
        if highs[i - j] >= val or highs[i + j] >= val:
            return None
    return val

def pivot_low(lows, i, length):
    if i < length or i + length >= len(lows):
        return None
    val = lows[i]
    for j in range(1, length + 1):
        if lows[i - j] <= val or lows[i + j] <= val:
            return None
    return val

# ==================== تحليل SMC ====================
def analyze(candles):
    opens  = [c["open"]  for c in candles]
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]
    closes = [c["close"] for c in candles]
    n = len(candles)
    trend = 0
    pending_ph = None; pending_ph_bar = -1
    pending_pl = None; pending_pl_bar = -1
    idm_level = None; idm_swept = False; idm_is_high = False
    ob_list = []
    buy_signal = sell_signal = False
    sig_entry = sig_sl = sig_tp = sig_rr = None

    for i in range(n):
        ph = pivot_high(highs, i, SWING_LEN)
        pl = pivot_low(lows, i, SWING_LEN)
        if ph is not None: pending_ph = ph; pending_ph_bar = i - SWING_LEN
        if pl is not None: pending_pl = pl; pending_pl_bar = i - SWING_LEN

        bull_break = pending_ph is not None and i > 0 and closes[i - 1] <= pending_ph and closes[i] > pending_ph
        bear_break = pending_pl is not None and i > 0 and closes[i - 1] >= pending_pl and closes[i] < pending_pl

        if bull_break:
            if pending_pl is not None: idm_level = pending_pl; idm_is_high = False; idm_swept = False
            trend = 1
            start = pending_pl_bar if pending_pl_bar != -1 else 0
            for k in range(1, min(OB_LOOKBACK, i - start) + 1):
                idx = i - k
                if idx < start: break
                if closes[idx] < opens[idx]:
                    ob_list.append({"top": highs[idx], "bottom": lows[idx], "bullish": True,
                                    "touches": 0, "valid": True, "signaled": False})
                    if len(ob_list) > MAX_OB_KEEP: ob_list.pop(0)
                    break
            pending_ph = None

        if bear_break:
            if pending_ph is not None: idm_level = pending_ph; idm_is_high = True; idm_swept = False
            trend = -1
            start = pending_ph_bar if pending_ph_bar != -1 else 0
            for k in range(1, min(OB_LOOKBACK, i - start) + 1):
                idx = i - k
                if idx < start: break
                if closes[idx] > opens[idx]:
                    ob_list.append({"top": highs[idx], "bottom": lows[idx], "bullish": False,
                                    "touches": 0, "valid": True, "signaled": False})
                    if len(ob_list) > MAX_OB_KEEP: ob_list.pop(0)
                    break
            pending_pl = None

        if not idm_swept and idm_level is not None:
            if idm_is_high and highs[i] >= idm_level: idm_swept = True
            if not idm_is_high and lows[i] <= idm_level: idm_swept = True

        for ob in ob_list:
            if not ob["valid"]: continue
            if ob["bullish"]:
                if lows[i] <= ob["top"] and lows[i] >= ob["bottom"]: ob["touches"] += 1
                if closes[i] < ob["bottom"]: ob["valid"] = False
            else:
                if highs[i] >= ob["bottom"] and highs[i] <= ob["top"]: ob["touches"] += 1
                if closes[i] > ob["top"]: ob["valid"] = False
            if ob["touches"] >= OB_MAX_TOUCH: ob["valid"] = False

        if i == n - 2 and (not REQUIRE_IDM or idm_swept):
            for ob in ob_list:
                if not ob["valid"] or ob["signaled"]: continue
                touch = (lows[i] <= ob["top"] and highs[i] >= ob["bottom"]) if USE_WICK_TOUCH else (ob["bottom"] <= closes[i] <= ob["top"])
                if not touch: continue
                if trend == 1 and ob["bullish"] and not buy_signal and not sell_signal:
                    entry = ob["top"]; sl = ob["bottom"] * (1 - SL_BUFFER_PCT / 100); risk = entry - sl
                    if risk > 0:
                        ob["signaled"] = True; buy_signal = True
                        sig_entry = entry; sig_sl = sl; sig_tp = entry + risk * MIN_RR; sig_rr = MIN_RR
                elif trend == -1 and not ob["bullish"] and not buy_signal and not sell_signal:
                    entry = ob["bottom"]; sl = ob["top"] * (1 + SL_BUFFER_PCT / 100); risk = sl - entry
                    if risk > 0:
                        ob["signaled"] = True; sell_signal = True
                        sig_entry = entry; sig_sl = sl; sig_tp = entry - risk * MIN_RR; sig_rr = MIN_RR

    return {"buy": buy_signal, "sell": sell_signal, "entry": sig_entry,
            "sl": sig_sl, "tp": sig_tp, "rr": sig_rr, "trend": trend,
            "time": candles[-1]["time"] if candles else ""}

# ==================== حساب الربح/الخسارة ====================
def calc_points_and_money(entry, exit_price, is_buy):
    """يرجع (النقاط، الدولار) للحركة بين entry و exit حسب نوع الصفقة."""
    points = (exit_price - entry) if is_buy else (entry - exit_price)
    money  = points * CONTRACT_SIZE * LOT_SIZE
    return points, money

# ==================== إرسال إشارة جديدة ====================
def send_signal_message(result):
    """يبعث رسالة الإشارة مرة وحدة بس، بثلاث أهداف وستوب."""
    is_buy   = result["buy"]
    entry    = result["entry"]
    sl       = result["sl"]
    risk     = abs(entry - sl)
    order_type = "Buy Limit" if is_buy else "Sell Limit"

    if is_buy:
        t1 = entry + risk * 1.0
        t2 = entry + risk * 1.5
        t3 = entry + risk * 2.0
    else:
        t1 = entry - risk * 1.0
        t2 = entry - risk * 1.5
        t3 = entry - risk * 2.0

    msg = (
        f"👁️\n\n"
        f"🥇 #XAUUSD | {order_type} {entry:.2f}\n\n"
        f"✅ Target 1 : {t1:.2f} | Target 2 : {t2:.2f} | "
        f"Target 3 : {t3:.2f}\n\n"
        f"❗ Stoploss : {sl:.2f}"
    )
    broadcast(msg)

    return {
        "type": "BUY" if is_buy else "SELL",
        "entry": entry,
        "sl": sl,
        "t1": t1, "t2": t2, "t3": t3,
        "hit_t1": False, "hit_t2": False,
        "open_time": result["time"],
    }

# ==================== متابعة الصفقة ====================
def check_trade_result(active_trade, candles):
    """يتابع الصفقة المفتوحة، يعلن كل هدف يتحقق، ويقفل الصفقة عند TP3 أو SL
       مع إعلان الربح/الخسارة بالنقاط والدولار."""
    if not active_trade or not candles:
        return active_trade

    is_buy = active_trade["type"] == "BUY"
    entry  = active_trade["entry"]
    sl     = active_trade["sl"]
    opened = active_trade["open_time"]

    for c in candles:
        if c["time"] <= opened:
            continue

        # ستوب لوس
        hit_sl = (c["low"] <= sl) if is_buy else (c["high"] >= sl)
        if hit_sl:
            points, money = calc_points_and_money(entry, sl, is_buy)
            broadcast(
                f"👁️\n\n"
                f"🛑 Stoploss Hit.\n\n"
                f"🥇 #XAUUSD | {active_trade['type']}\n"
                f"Entry: {entry:.2f} | SL: {sl:.2f}\n"
                f"📉 الخسارة: {abs(points):.2f} نقطة (~{abs(money):.2f}$ للوت {LOT_SIZE})\n\n"
                f"💪 Losses are part of the game.\n"
                f"Stay disciplined — the next setup will be better."
            )
            print(f"❌ ستوب {active_trade['type']} @ {sl:.2f}")
            return None

        # هدف 1
        if not active_trade["hit_t1"]:
            hit_t1 = (c["high"] >= active_trade["t1"]) if is_buy else (c["low"] <= active_trade["t1"])
            if hit_t1:
                active_trade["hit_t1"] = True
                points, money = calc_points_and_money(entry, active_trade["t1"], is_buy)
                broadcast(
                    f"👁️\n\n✅ Target 1 Hit! 🎯\n\n"
                    f"🥇 #XAUUSD | {active_trade['type']}\n"
                    f"📈 الربح: +{points:.2f} نقطة (~{money:.2f}$ للوت {LOT_SIZE})"
                )

        # هدف 2
        if not active_trade["hit_t2"]:
            hit_t2 = (c["high"] >= active_trade["t2"]) if is_buy else (c["low"] <= active_trade["t2"])
            if hit_t2:
                active_trade["hit_t2"] = True
                points, money = calc_points_and_money(entry, active_trade["t2"], is_buy)
                broadcast(
                    f"👁️\n\n✅ Target 2 Hit! 🎯\n\n"
                    f"🥇 #XAUUSD | {active_trade['type']}\n"
                    f"📈 الربح: +{points:.2f} نقطة (~{money:.2f}$ للوت {LOT_SIZE})"
                )

        # هدف 3 - إغلاق الصفقة بالكامل
        hit_t3 = (c["high"] >= active_trade["t3"]) if is_buy else (c["low"] <= active_trade["t3"])
        if hit_t3:
            points, money = calc_points_and_money(entry, active_trade["t3"], is_buy)
            broadcast(
                f"👁️\n\n♥️ Final Target Hit! 🎯\n\n"
                f"🥇 #XAUUSD | {active_trade['type']}\n"
                f"✅ Entry: {entry:.2f} → Target 3: {active_trade['t3']:.2f}\n"
                f"📈 الربح الكلي: +{points:.2f} نقطة (~{money:.2f}$ للوت {LOT_SIZE})\n\n"
                f"🔥 Everyone in profit!\n"
                f"💰 Well done for staying patient."
            )
            print(f"✅ هدف نهائي {active_trade['type']} @ {active_trade['t3']:.2f}")
            return None

    return active_trade  # الصفقة لسا مفتوحة

# ==================== الحلقة الرئيسية ====================
def main():
    acquire_single_instance_lock()

    state             = load_state()
    now_iso           = datetime.now(GAZA_TZ).isoformat()
    last_start_iso    = state.get("bot_started_at", "")
    # لو انعاد التشغيل خلال أقل من 3 دقائق من آخر مرة، هاد مؤشر crash loop
    # منبعت رسالة "البوت اشتغل" بس منسكت عن التكرار
    skip_startup_msg = False
    if last_start_iso:
        try:
            last_dt = datetime.fromisoformat(last_start_iso)
            if (datetime.now(GAZA_TZ) - last_dt).total_seconds() < 180:
                skip_startup_msg = True
                print("⚠️ إعادة تشغيل سريعة مكتشفة (crash loop محتمل) — تجاهل رسالة البدء")
        except Exception:
            pass

    if not skip_startup_msg:
        broadcast("👁️\n\n✅ Bot is now active and monitoring the market!\n📊 #XAUUSD | M5")
    print("✅ البوت شغّال - Twelve Data | XAUUSD M5")

    state["bot_started_at"] = now_iso
    save_state(state)

    offset            = load_offset()
    last_signal_time  = state.get("last_signal_time", "")
    morning_sent_date = ""
    news_sent_date    = ""
    news_alert_sent   = set()
    daily_news        = []
    last_candle_check = 0
    active_trade      = state.get("active_trade")

    try:
        while True:
            try:
                offset    = process_updates(offset)
                now_gaza  = datetime.now(GAZA_TZ)
                today_str = now_gaza.strftime("%Y-%m-%d")

                if news_sent_date != today_str:
                    daily_news     = get_usd_news()
                    news_sent_date = today_str

                if now_gaza.hour == 8 and now_gaza.minute == 0 and morning_sent_date != today_str:
                    send_morning_message(daily_news)
                    send_news_message(daily_news)
                    morning_sent_date = today_str

                for news in daily_news:
                    if news["impact"] == "high":
                        diff = (news["time"] - now_gaza).total_seconds() / 60
                        key  = news["time_str"] + "_" + today_str
                        if 14 <= diff <= 15 and key + "_pre" not in news_alert_sent:
                            news_alert_sent.add(key + "_pre")
                            broadcast(
                                f"👁️\n\n"
                                f"⚠️ High Impact News in 15 minutes!\n\n"
                                f"🔴 {news['title']}\n"
                                f"⏰ {news['time_str']} Gaza Time\n\n"
                                f"🚫 Do NOT open any trades now.\n"
                                f"Wait 15 minutes after the release.")
                        if -16 <= diff <= -15 and key + "_post" not in news_alert_sent:
                            news_alert_sent.add(key + "_post")
                            broadcast(
                                f"👁️\n\n"
                                f"✅ News is over — Market is settling.\n\n"
                                f"📰 {news['title']} | {news['time_str']}\n\n"
                                f"🟢 You may look for setups — but stay cautious.")

                now_ts = time.time()
                if now_ts - last_candle_check >= 300:
                    last_candle_check = now_ts
                    candles = get_candles()

                    if candles:
                        if active_trade:
                            active_trade = check_trade_result(active_trade, candles)
                            state["active_trade"] = active_trade
                            save_state(state)

                        if not active_trade:
                            in_news, news_obj = is_high_impact_news_time(daily_news)
                            result = analyze(candles)
                            current_time = result["time"]

                            if (result["buy"] or result["sell"]) and current_time != last_signal_time:
                                last_signal_time = current_time
                                state["last_signal_time"] = last_signal_time

                                if in_news:
                                    broadcast(
                                        f"👁️\n\n"
                                        f"⚠️ Setup detected but we will NOT enter.\n\n"
                                        f"🔴 High Impact News active: {news_obj['title']}\n"
                                        f"⏰ {news_obj['time_str']} Gaza Time\n\n"
                                        f"🙌 Sometimes avoiding a trade is also a profit.")
                                else:
                                    active_trade = send_signal_message(result)
                                    state["active_trade"] = active_trade

                                save_state(state)

                time.sleep(2)

            except Exception as e:
                print(f"⚠️ خطأ بالحلقة الرئيسية: {e}")
                time.sleep(5)
    finally:
        release_single_instance_lock()

if __name__ == "__main__":
    main()
