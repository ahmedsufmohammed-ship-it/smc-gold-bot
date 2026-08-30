import requests
import time
import json
import os
from datetime import datetime
from xml.etree import ElementTree as ET
import pytz

# ==================== الإعدادات ====================
TELEGRAM_TOKEN = "8800189995:AAEAluegBqFTM_fXko38IS92efpEsOKDYqA"
ADMIN_IDS      = ["6360489611", "8315710670", "1266693223"]
MEMBERS_FILE   = "members.json"

SWING_LEN      = 10
OB_LOOKBACK    = 60
OB_MAX_TOUCH   = 3
MAX_OB_KEEP    = 5
SL_BUFFER_PCT  = 0.15
MIN_RR         = 2.0
USE_WICK_TOUCH = True
REQUIRE_IDM    = False

GAZA_TZ = pytz.timezone("Asia/Gaza")

# ==================== إدارة الأعضاء ====================
def load_members():
    if os.path.exists(MEMBERS_FILE):
        with open(MEMBERS_FILE, "r") as f:
            return json.load(f)
    # الأدمن دايماً موجودين
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

# ==================== إرسال رسائل ====================
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

# ==================== معالجة رسائل الأدمن ====================
def handle_admin_message(chat_id, text, first_name):
    chat_id = str(chat_id)

    # أوامر الأدمن
    if text == "/members":
        members = load_members()
        send_telegram(
            f"👥 <b>قائمة الأعضاء</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"العدد الكلي: <b>{len(members)}</b> عضو\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🤖 SMC Gold Bot",
            chat_id
        )
        return

    if text == "/help":
        send_telegram(
            "⚙️ <b>أوامر الأدمن:</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "/members — عدد الأعضاء\n"
            "/help — قائمة الأوامر\n\n"
            "📢 <b>للبث:</b>\n"
            "ابعث أي رسالة عادية وتوصل لكل الأعضاء تلقائياً\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🤖 SMC Gold Bot",
            chat_id
        )
        return

    # أي رسالة ثانية من الأدمن = بث للكل
    members = load_members()
    count = len(members)
    broadcast(
        f"📢 <b>رسالة من الإدارة:</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{text}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🤖 SMC Gold Bot"
    )
    send_telegram(f"✅ تم إرسال رسالتك لـ <b>{count}</b> عضو", chat_id)

# ==================== معالجة رسائل الأعضاء ====================
def handle_member_message(chat_id, text, first_name):
    chat_id = str(chat_id)

    if text == "/start":
        added = add_member(chat_id)
        if added:
            members = load_members()
            send_telegram(
                f"🎉 <b>أهلاً {first_name}!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"تم اشتراكك في <b>SMC Gold Bot</b> ✅\n\n"
                f"📊 الزوج: XAU/USD | فريم M5\n"
                f"📈 ستصلك إشارات شراء/بيع تلقائياً\n"
                f"📰 وتنبيهات أخبار USD\n"
                f"🌅 ورسالة صباحية يومياً\n\n"
                f"للإلغاء: /stop\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🤖 SMC Gold Bot",
                chat_id
            )
            # إشعار الأدمن
            members_count = len(members)
            for admin in ADMIN_IDS:
                send_telegram(
                    f"👤 عضو جديد انضم!\n"
                    f"الاسم: {first_name}\n"
                    f"ID: {chat_id}\n"
                    f"المجموع: {members_count} عضو",
                    admin
                )
        else:
            send_telegram(
                f"✅ {first_name} أنت مشترك أصلاً!\n"
                f"للإلغاء: /stop",
                chat_id
            )
        return

    if text == "/stop":
        removed = remove_member(chat_id)
        if removed:
            send_telegram(
                f"😔 تم إلغاء اشتراكك {first_name}\n"
                f"للاشتراك مجدداً: /start",
                chat_id
            )
        else:
            send_telegram("أنت غير مشترك أو لا يمكن إلغاء اشتراكك.", chat_id)
        return

    # رسالة عادية من عضو
    send_telegram(
        f"مرحباً {first_name} 👋\n"
        f"هذا البوت للإشارات فقط.\n\n"
        f"/start — اشتراك\n"
        f"/stop — إلغاء الاشتراك",
        chat_id
    )

# ==================== استقبال رسائل التيليغرام ====================
def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 30, "offset": offset}
    try:
        r = requests.get(url, params=params, timeout=35)
        return r.json().get("result", [])
    except:
        return []

def process_updates(offset):
    updates = get_updates(offset)
    for update in updates:
        offset = update["update_id"] + 1
        try:
            msg      = update.get("message", {})
            chat_id  = msg.get("chat", {}).get("id")
            text     = msg.get("text", "").strip()
            first    = msg.get("from", {}).get("first_name", "")
            if not chat_id or not text:
                continue
            if str(chat_id) in ADMIN_IDS:
                handle_admin_message(chat_id, text, first)
            else:
                handle_member_message(chat_id, text, first)
        except:
            pass
    return offset

# ==================== أخبار USD ====================
def get_usd_news():
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
        r = requests.get(url, timeout=15)
        root = ET.fromstring(r.content)
        news_list = []
        now_gaza = datetime.now(GAZA_TZ)
        today = now_gaza.date()
        for event in root.findall("event"):
            try:
                if event.findtext("country","").upper() != "USD": continue
                title    = event.findtext("title","")
                impact   = event.findtext("impact","").lower()
                date_str = event.findtext("date","")
                time_str = event.findtext("time","")
                if not date_str or not time_str: continue
                dt_str = f"{date_str} {time_str}"
                try:
                    dt_utc = datetime.strptime(dt_str, "%m-%d-%Y %I:%M%p")
                except:
                    dt_utc = datetime.strptime(dt_str, "%m-%d-%Y %I:%M %p")
                dt_utc  = pytz.utc.localize(dt_utc)
                dt_gaza = dt_utc.astimezone(GAZA_TZ)
                if dt_gaza.date() != today: continue
                if impact in ["high","medium","low"]:
                    news_list.append({
                        "title"   : title,
                        "impact"  : impact,
                        "time"    : dt_gaza,
                        "time_str": dt_gaza.strftime("%I:%M %p")
                    })
            except: continue
        news_list.sort(key=lambda x: x["time"])
        return news_list
    except Exception as e:
        print(f"خطأ في الأخبار: {e}")
        return []

def is_high_impact_news_time(news_list):
    now = datetime.now(GAZA_TZ)
    for news in news_list:
        if news["impact"] == "high":
            diff = (news["time"] - now).total_seconds() / 60
            if -15 <= diff <= 15:
                return True, news
    return False, None

def send_news_message(news_list):
    if not news_list: return
    high   = [n for n in news_list if n["impact"] == "high"]
    medium = [n for n in news_list if n["impact"] == "medium"]
    low    = [n for n in news_list if n["impact"] == "low"]
    msg = (
        "📰 <b>أخبار USD اليوم</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🕐 <i>الأوقات بتوقيت غزة</i>\n\n"
    )
    if high:
        msg += "🔴 <b>أخبار قوية — ابتعد عن التداول:</b>\n"
        for n in high: msg += f"   ⏰ {n['time_str']} | {n['title']}\n"
        msg += "\n"
    if medium:
        msg += "🟡 <b>أخبار متوسطة — انتبه:</b>\n"
        for n in medium: msg += f"   ⏰ {n['time_str']} | {n['title']}\n"
        msg += "\n"
    if low:
        msg += "🟢 <b>أخبار ضعيفة — لا تأثير كبير:</b>\n"
        for n in low: msg += f"   ⏰ {n['time_str']} | {n['title']}\n"
        msg += "\n"
    msg += (
        "━━━━━━━━━━━━━━━━━━\n"
        "⚠️ لا تتداول 15 دقيقة قبل وبعد الأخبار القوية 🔴\n"
        "🤖 SMC Gold Bot"
    )
    broadcast(msg)

def send_morning_message(news_list):
    now = datetime.now(GAZA_TZ)
    day_ar = ["الاثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"][now.weekday()]
    date_str = now.strftime(f"{day_ar} %d/%m/%Y")
    high_news = [n for n in news_list if n["impact"] == "high"]
    news_warn = ""
    if high_news:
        news_warn = "\n⚠️ <b>تحذير:</b> يوم فيه أخبار قوية!\n"
        for n in high_news: news_warn += f"   🔴 {n['time_str']} | {n['title']}\n"
    msg = (
        "🌅 <b>Good Morning Traders!</b> ☀️\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📅 {date_str}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📊 <b>SMC Gold Bot</b> | XAU/USD M5\n"
        f"{news_warn}\n"
        "🔍 <b>خطة اليوم:</b>\n"
        "• راقب مناطق الأوردر بلوك\n"
        "• انتظر تأكيد BOS أو CHOCH\n"
        "• لا تدخل بدون إشارة واضحة\n\n"
        "💡 <b>تذكّر:</b> الصبر أهم من الصفقات!\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🤖 البوت شغّال ويراقب السوق 24/5 ✅"
    )
    broadcast(msg)
    print(f"✅ رسالة الصباح - {date_str}")

# ==================== جلب بيانات الذهب ====================
def get_candles():
    try:
        r = requests.get("https://api.twelvedata.com/time_series", params={
            "symbol": "XAU/USD", "interval": "5min",
            "outputsize": 200, "apikey": "0cef5bb56a314b6289f3db0b648f84b5"
        }, timeout=15)
        data = r.json()
        if "values" not in data: return None
        return [{"time": v["datetime"], "open": float(v["open"]),
                 "high": float(v["high"]), "low": float(v["low"]),
                 "close": float(v["close"])} for v in reversed(data["values"])]
    except: return None

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
                    ob_list.append({"top": highs[idx], "bottom": lows[idx], "bullish": True, "touches": 0, "valid": True, "signaled": False})
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
                    ob_list.append({"top": highs[idx], "bottom": lows[idx], "bullish": False, "touches": 0, "valid": True, "signaled": False})
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

# ==================== الحلقة الرئيسية ====================
def main():
    broadcast(
        "🤖 <b>SMC Gold Bot</b> شغّال!\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📊 الزوج: XAU/USD | فريم M5\n"
        "🌅 رسالة صباحية كل يوم 08:00 AM\n"
        "📰 تنبيهات أخبار USD تلقائياً\n"
        "📈 إشارات شراء/بيع SMC\n"
        "👥 ابعث /start لأصحابك يشتركوا\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✅ جاهز للعمل!"
    )
    print("✅ البوت شغّال")

    offset            = None
    last_signal_time  = ""
    morning_sent_date = ""
    news_sent_date    = ""
    news_alert_sent   = set()
    daily_news        = []
    last_candle_check = 0

    while True:
        try:
            # استقبال رسائل
            offset = process_updates(offset)

            now_gaza  = datetime.now(GAZA_TZ)
            today_str = now_gaza.strftime("%Y-%m-%d")

            # جلب الأخبار مرة باليوم
            if news_sent_date != today_str:
                daily_news     = get_usd_news()
                news_sent_date = today_str

            # رسالة الصباح 8:00 AM
            if now_gaza.hour == 8 and now_gaza.minute == 0 and morning_sent_date != today_str:
                send_morning_message(daily_news)
                send_news_message(daily_news)
                morning_sent_date = today_str

            # تنبيه قبل خبر قوي 15 دقيقة
            for news in daily_news:
                if news["impact"] == "high":
                    diff_min = (news["time"] - now_gaza).total_seconds() / 60
                    key = news["time_str"] + "_" + today_str
                    if 14 <= diff_min <= 15 and key+"_pre" not in news_alert_sent:
                        news_alert_sent.add(key+"_pre")
                        broadcast(
                            f"🚨 <b>تحذير خبر قوي!</b>\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"🔴 الخبر: <b>{news['title']}</b>\n"
                            f"⏰ الوقت: <b>{news['time_str']} بتوقيت غزة</b>\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"⛔ <b>لا تفتح صفقات جديدة الآن!</b>\n"
                            f"⏳ انتظر 15 دقيقة بعد الخبر\n"
                            f"🤖 SMC Gold Bot"
                        )
                    if -16 <= diff_min <= -15 and key+"_post" not in news_alert_sent:
                        news_alert_sent.add(key+"_post")
                        broadcast(
                            f"✅ <b>انتهى وقت الخبر</b>\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"📰 {news['title']} | {news['time_str']}\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"🟢 يمكن التداول الآن بحذر\n"
                            f"🤖 SMC Gold Bot"
                        )

            # تحليل السوق كل دقيقة
            now_ts = time.time()
            if now_ts - last_candle_check >= 60:
                last_candle_check = now_ts
                in_news, news_obj = is_high_impact_news_time(daily_news)
                candles = get_candles()
                if candles and len(candles) >= 50:
                    result = analyze(candles)
                    current_time = result["time"]
                    if (result["buy"] or result["sell"]) and current_time != last_signal_time:
                        last_signal_time = current_time
                        direction = "🟢 شراء (BUY)" if result["buy"] else "🔴 بيع (SELL)"
                        emoji = "📈" if result["buy"] else "📉"
                        if in_news:
                            broadcast(
                                f"⚠️ <b>إشارة موجودة لكن لا ندخل!</b>\n"
                                f"━━━━━━━━━━━━━━━━━━\n"
                                f"{emoji} الاتجاه: <b>{direction}</b>\n"
                                f"━━━━━━━━━━━━━━━━━━\n"
                                f"🚨 يوجد خبر قوي: {news_obj['title']}\n"
                                f"⏰ الساعة: {news_obj['time_str']} بتوقيت غزة\n"
                                f"⏳ انتظر انتهاء الخبر\n"
                                f"🤖 SMC Gold Bot"
                            )
                        else:
                            broadcast(
                                f"{emoji} <b>إشارة SMC جديدة!</b>\n"
                                f"━━━━━━━━━━━━━━━━━━\n"
                                f"الزوج:   <b>XAU/USD (ذهب)</b>\n"
                                f"الفريم:  <b>M5</b>\n"
                                f"الاتجاه: <b>{direction}</b>\n"
                                f"━━━━━━━━━━━━━━━━━━\n"
                                f"💰 دخول:  <b>{result['entry']:.2f}</b>\n"
                                f"🛑 ستوب:  <b>{result['sl']:.2f}</b>\n"
                                f"🎯 هدف:   <b>{result['tp']:.2f}</b>\n"
                                f"📊 R:R =  <b>1:{result['rr']:.1f}</b>\n"
                                f"━━━━━━━━━━━━━━━━━━\n"
                                f"🕐 {current_time}\n"
                                f"🤖 SMC Gold Bot"
                            )
                    else:
                        trend_txt = "صاعد 📈" if result["trend"]==1 else ("هابط 📉" if result["trend"]==-1 else "محايد")
                        print(f"[{now_gaza.strftime('%H:%M:%S')}] {trend_txt} | {candles[-1]['close']:.2f}")

        except Exception as e:
            print(f"❌ خطأ: {e}")

        time.sleep(2)

if __name__ == "__main__":
    main()
