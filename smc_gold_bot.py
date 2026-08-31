import requests
import time
import json
import os
from datetime import datetime
from xml.etree import ElementTree as ET
import pytz

TELEGRAM_TOKEN = "8800189995:AAEAluegBqFTM_fXko38IS92efpEsOKDYqA"
ADMIN_IDS      = ["6360489611", "8315710670", "1266693223"]
BROADCASTER_ID = "6360489611"
MEMBERS_FILE   = "members.json"

SWING_LEN      = 10
OB_LOOKBACK    = 60
OB_MAX_TOUCH   = 3
MAX_OB_KEEP    = 5
SL_BUFFER_PCT  = 0.15
MIN_RR         = 2.0
USE_WICK_TOUCH = True
REQUIRE_IDM    = False
GAZA_TZ        = pytz.timezone("Asia/Gaza")

# ==================== الأعضاء ====================
def load_members():
    if os.path.exists(MEMBERS_FILE):
        with open(MEMBERS_FILE, "r") as f:
            return json.load(f)
    save_members(ADMIN_IDS.copy())
    return ADMIN_IDS.copy()

def save_members(members):
    with open(MEMBERS_FILE, "w") as f:
        json.dump(members, f)

def add_member(chat_id):
    members = load_members()
    chat_id = str(chat_id)
    if chat_id not in members:
        members.append(chat_id)
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
        except:
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
                f"تم تفعيل اشتراكك ✅\n"
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
    except:
        return []

def process_updates(offset):
    for update in get_updates(offset):
        offset = update["update_id"] + 1
        try:
            msg     = update.get("message", {})
            chat_id = msg.get("chat", {}).get("id")
            text    = msg.get("text", "").strip()
            first   = msg.get("from", {}).get("first_name", "")
            if not chat_id or not text: continue
            if str(chat_id) in ADMIN_IDS:
                handle_admin_message(chat_id, text, first)
            else:
                handle_member_message(chat_id, text, first)
        except:
            pass
    return offset

# ==================== بيانات الذهب ====================
# رموز محتملة لسعر الذهب سبوت (نفس نوع السعر يلي عالميتاتريدر) - بيجرب كل واحد
# لحد ما يلقى وحد شغال عند ياهو، وآخر خيار GC=F (عقود مستقبلية) كحل احتياطي
# بس ضامن إنه دايماً في بيانات حتى لو الرموز التانية توقفت
GOLD_TICKERS = ["XAUUSD=X", "XAU=X", "GC=F"]

def get_candles():
    headers = {"User-Agent": "Mozilla/5.0"}
    for symbol in GOLD_TICKERS:
        try:
            r = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={"interval": "5m", "range": "5d"},
                headers=headers, timeout=20)
            data = r.json()
            result = data.get("chart", {}).get("result", [])
            if not result:
                print(f"⚠️ {symbol}: لا بيانات، بجرب رمز تاني")
                continue
            ts    = result[0]["timestamp"]
            ohlcv = result[0]["indicators"]["quote"][0]
            opens  = ohlcv.get("open", [])
            highs  = ohlcv.get("high", [])
            lows   = ohlcv.get("low", [])
            closes = ohlcv.get("close", [])
            candles = []
            for i in range(len(ts)):
                if opens[i] is None or closes[i] is None: continue
                dt = datetime.fromtimestamp(ts[i], tz=GAZA_TZ).strftime("%Y-%m-%d %H:%M")
                candles.append({
                    "time": dt,
                    "open":  float(opens[i]),
                    "high":  float(highs[i]),
                    "low":   float(lows[i]),
                    "close": float(closes[i]),
                })
            if len(candles) < 50:
                print(f"⚠️ {symbol}: بيانات ناقصة، بجرب رمز تاني")
                continue
            print(f"✅ {symbol}: {len(candles)} شمعة | {candles[-1]['close']:.2f}")
            return candles
        except Exception as e:
            print(f"❌ {symbol}: {e}")
    print("❌ فشل جلب السعر من كل الرموز")
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
                if event.findtext("country","").upper() != "USD": continue
                title  = event.findtext("title","")
                impact = event.findtext("impact","").lower()
                d_str  = event.findtext("date","")
                t_str  = event.findtext("time","")
                if not d_str or not t_str: continue
                try:
                    dt_utc = datetime.strptime(f"{d_str} {t_str}", "%m-%d-%Y %I:%M%p")
                except:
                    dt_utc = datetime.strptime(f"{d_str} {t_str}", "%m-%d-%Y %I:%M %p")
                dt_gaza = pytz.utc.localize(dt_utc).astimezone(GAZA_TZ)
                if dt_gaza.date() != today: continue
                if impact in ["high","medium","low"]:
                    news_list.append({"title": title, "impact": impact,
                                      "time": dt_gaza, "time_str": dt_gaza.strftime("%I:%M %p")})
            except: continue
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
    if not news_list: return
    high   = [n for n in news_list if n["impact"] == "high"]
    medium = [n for n in news_list if n["impact"] == "medium"]
    low    = [n for n in news_list if n["impact"] == "low"]
    msg = "📰 <b>أخبار USD اليوم</b>\n━━━━━━━━━━━━━━━━━━\n🕐 <i>بتوقيت غزة</i>\n\n"
    if high:
        msg += "🔴 <b>قوية — ابتعد:</b>\n"
        for n in high: msg += f"   ⏰ {n['time_str']} | {n['title']}\n"
        msg += "\n"
    if medium:
        msg += "🟡 <b>متوسطة — انتبه:</b>\n"
        for n in medium: msg += f"   ⏰ {n['time_str']} | {n['title']}\n"
        msg += "\n"
    if low:
        msg += "🟢 <b>ضعيفة:</b>\n"
        for n in low: msg += f"   ⏰ {n['time_str']} | {n['title']}\n"
        msg += "\n"
    msg += "━━━━━━━━━━━━━━━━━━\n⚠️ لا تتداول 15د قبل وبعد القوية"
    broadcast(msg)

def send_morning_message(news_list):
    now = datetime.now(GAZA_TZ)
    day_ar = ["الاثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"][now.weekday()]
    high_news = [n for n in news_list if n["impact"] == "high"]
    news_warn = ""
    if high_news:
        news_warn = "\n⚠️ <b>يوم فيه أخبار قوية!</b>\n"
        for n in high_news: news_warn += f"   🔴 {n['time_str']} | {n['title']}\n"
    broadcast(
        f"🌅 <b>Good Morning Traders!</b> ☀️\n━━━━━━━━━━━━━━━━━━\n"
        f"📅 {now.strftime(f'{day_ar} %d/%m/%Y')}\n━━━━━━━━━━━━━━━━━━\n"
        f"📊 XAU/USD | M5\n{news_warn}\n"
        f"🔍 <b>خطة اليوم:</b>\n• راقب الأوردر بلوك\n"
        f"• انتظر BOS أو CHOCH\n• لا تدخل بدون إشارة\n\n"
        f"💡 الصبر أهم من الصفقات!\n━━━━━━━━━━━━━━━━━━\n"
        f"بالتوفيق للجميع 🌟")

# ==================== Pivot ====================
def pivot_high(highs, i, length):
    if i < length or i + length >= len(highs): return None
    val = highs[i]
    for j in range(1, length+1):
        if highs[i-j] >= val or highs[i+j] >= val: return None
    return val

def pivot_low(lows, i, length):
    if i < length or i + length >= len(lows): return None
    val = lows[i]
    for j in range(1, length+1):
        if lows[i-j] <= val or lows[i+j] <= val: return None
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

        bull_break = pending_ph is not None and i > 0 and closes[i-1] <= pending_ph and closes[i] > pending_ph
        bear_break = pending_pl is not None and i > 0 and closes[i-1] >= pending_pl and closes[i] < pending_pl

        if bull_break:
            if pending_pl is not None: idm_level = pending_pl; idm_is_high = False; idm_swept = False
            trend = 1
            start = pending_pl_bar if pending_pl_bar != -1 else 0
            for k in range(1, min(OB_LOOKBACK, i-start)+1):
                idx = i-k
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
            for k in range(1, min(OB_LOOKBACK, i-start)+1):
                idx = i-k
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

        if i == n-2 and (not REQUIRE_IDM or idm_swept):
            for ob in ob_list:
                if not ob["valid"] or ob["signaled"]: continue
                touch = (lows[i] <= ob["top"] and highs[i] >= ob["bottom"]) if USE_WICK_TOUCH else (ob["bottom"] <= closes[i] <= ob["top"])
                if not touch: continue
                if trend == 1 and ob["bullish"] and not buy_signal and not sell_signal:
                    entry = ob["top"]; sl = ob["bottom"]*(1-SL_BUFFER_PCT/100); risk = entry-sl
                    if risk > 0:
                        ob["signaled"] = True; buy_signal = True
                        sig_entry = entry; sig_sl = sl; sig_tp = entry+risk*MIN_RR; sig_rr = MIN_RR
                elif trend == -1 and not ob["bullish"] and not buy_signal and not sell_signal:
                    entry = ob["bottom"]; sl = ob["top"]*(1+SL_BUFFER_PCT/100); risk = sl-entry
                    if risk > 0:
                        ob["signaled"] = True; sell_signal = True
                        sig_entry = entry; sig_sl = sl; sig_tp = entry-risk*MIN_RR; sig_rr = MIN_RR

    return {"buy": buy_signal, "sell": sell_signal, "entry": sig_entry,
            "sl": sig_sl, "tp": sig_tp, "rr": sig_rr, "trend": trend,
            "time": candles[-1]["time"] if candles else ""}

# ==================== رسالة إشارة جديدة ====================
def send_signal_message(trade):
    direction = "Buy" if trade["type"] == "BUY" else "Sell"
    msg = (
        f"🥇 #XAUUSD | {direction} {trade['entry']:.2f}\n\n"
        f"✅ Target : {trade['tp']:.2f}\n\n"
        f"❕Stoploss : {trade['sl']:.2f}"
    )
    broadcast(msg)

# ==================== متابعة الصفقة ====================
def check_trade_result(active_trade, candles):
    """يتابع الصفقة المفتوحة ويرجع النتيجة"""
    if not active_trade or not candles:
        return active_trade

    is_buy  = active_trade["type"] == "BUY"
    entry   = active_trade["entry"]
    sl      = active_trade["sl"]
    tp      = active_trade["tp"]
    opened  = active_trade["open_time"]

    # شوف آخر الشموع بعد وقت الدخول
    for c in candles:
        if c["time"] <= opened:
            continue

        if is_buy:
            if c["low"] <= sl:
                loss = sl - entry
                broadcast(
                    f"🥇 #XAUUSD | BUY ❌\n\n"
                    f"Entry : {entry:.2f}\n"
                    f"Stoploss Hit : {sl:.2f}\n"
                    f"Loss : -{abs(loss):.2f}$"
                )
                print(f"❌ ستوب BUY @ {sl:.2f}")
                return None

            if c["high"] >= tp:
                profit = tp - entry
                broadcast(
                    f"🥇 #XAUUSD | BUY ✅\n\n"
                    f"Entry : {entry:.2f}\n"
                    f"Target Hit : {tp:.2f}\n"
                    f"Profit : +{profit:.2f}$"
                )
                print(f"✅ هدف BUY @ {tp:.2f}")
                return None

        else:  # SELL
            if c["high"] >= sl:
                loss = sl - entry
                broadcast(
                    f"🥇 #XAUUSD | SELL ❌\n\n"
                    f"Entry : {entry:.2f}\n"
                    f"Stoploss Hit : {sl:.2f}\n"
                    f"Loss : -{abs(loss):.2f}$"
                )
                print(f"❌ ستوب SELL @ {sl:.2f}")
                return None

            if c["low"] <= tp:
                profit = entry - tp
                broadcast(
                    f"🥇 #XAUUSD | SELL ✅\n\n"
                    f"Entry : {entry:.2f}\n"
                    f"Target Hit : {tp:.2f}\n"
                    f"Profit : +{profit:.2f}$"
                )
                print(f"✅ هدف SELL @ {tp:.2f}")
                return None

    return active_trade  # الصفقة لسا مفتوحة

# ==================== الحلقة الرئيسية ====================
def main():
    broadcast(
        "📊 <b>XAU/USD</b> | M5\n━━━━━━━━━━━━━━━━━━\n"
        "🌅 رسالة صباحية 08:00 AM\n"
        "📰 تنبيهات أخبار USD\n📈 إشارات تلقائية\n"
        "✅ متابعة نتيجة كل صفقة\n"
        "👥 /start للاشتراك\n━━━━━━━━━━━━━━━━━━\n✅ جاهز!"
    )
    print("✅ البوت شغّال - Yahoo Finance | XAUUSD M5")

    offset            = None
    last_signal_time  = ""
    morning_sent_date = ""
    news_sent_date    = ""
    news_alert_sent   = set()
    daily_news        = []
    last_candle_check = 0
    active_trade      = None  # الصفقة المفتوحة الحالية

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
                    if 14 <= diff <= 15 and key+"_pre" not in news_alert_sent:
                        news_alert_sent.add(key+"_pre")
                        broadcast(
                            f"🚨 <b>تحذير خبر قوي!</b>\n━━━━━━━━━━━━━━━━━━\n"
                            f"🔴 {news['title']}\n⏰ {news['time_str']} بتوقيت غزة\n"
                            f"━━━━━━━━━━━━━━━━━━\n⛔ لا تفتح صفقات!")
                    if -16 <= diff <= -15 and key+"_post" not in news_alert_sent:
                        news_alert_sent.add(key+"_post")
                        broadcast(
                            f"✅ <b>انتهى وقت الخبر</b>\n━━━━━━━━━━━━━━━━━━\n"
                            f"📰 {news['title']} | {news['time_str']}\n"
                            f"━━━━━━━━━━━━━━━━━━\n🟢 يمكن التداول بحذر")

            now_ts = time.time()
            if now_ts - last_candle_check >= 300:
                last_candle_check = now_ts
                candles = get_candles()

                if candles:
                    # تحديث حالة الصفقة المفتوحة إن وجدت (تحقق ستوب/هدف)
                    if active_trade:
                        active_trade = check_trade_result(active_trade, candles)

                    # دور على إشارة جديدة فقط إذا ما في صفقة مفتوحة حالياً
                    if not active_trade:
                        news_block, _ = is_high_impact_news_time(daily_news)
                        if not news_block:
                            result = analyze(candles)
                            if (result["buy"] or result["sell"]) and result["time"] != last_signal_time:
                                trade_type = "BUY" if result["buy"] else "SELL"
                                active_trade = {
                                    "type": trade_type,
                                    "entry": result["entry"],
                                    "sl": result["sl"],
                                    "tp": result["tp"],
                                    "rr": result["rr"],
                                    "open_time": result["time"],
                                }
                                send_signal_message(active_trade)
                                last_signal_time = result["time"]

            time.sleep(5)

        except Exception as e:
            print(f"❌ خطأ رئيسي: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()
