import requests
import time
from datetime import datetime, timedelta
import pytz
from xml.etree import ElementTree as ET

# ==================== الإعدادات ====================
TELEGRAM_TOKEN = "8800189995:AAEAluegBqFTM_fXko38IS92efpEsOKDYqA"
CHAT_IDS       = ["6360489611", "8315710670", "1266693223"]

SWING_LEN      = 10
OB_LOOKBACK    = 60
OB_MAX_TOUCH   = 3
MAX_OB_KEEP    = 5
SL_BUFFER_PCT  = 0.15
MIN_RR         = 2.0
USE_WICK_TOUCH = True
REQUIRE_IDM    = False

GAZA_TZ = pytz.timezone("Asia/Gaza")

# ==================== إرسال رسالة ====================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for chat_id in CHAT_IDS:
        try:
            requests.post(url, data={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=10)
        except:
            pass

# ==================== جلب أخبار USD ====================
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
                currency = event.findtext("country", "")
                if currency.upper() != "USD":
                    continue

                title    = event.findtext("title", "")
                impact   = event.findtext("impact", "").lower()
                date_str = event.findtext("date", "")
                time_str = event.findtext("time", "")

                if not date_str or not time_str:
                    continue

                # تحويل الوقت
                dt_str = f"{date_str} {time_str}"
                try:
                    dt_utc = datetime.strptime(dt_str, "%m-%d-%Y %I:%M%p")
                except:
                    try:
                        dt_utc = datetime.strptime(dt_str, "%m-%d-%Y %I:%M %p")
                    except:
                        continue

                dt_utc = pytz.utc.localize(dt_utc)
                dt_gaza = dt_utc.astimezone(GAZA_TZ)

                if dt_gaza.date() != today:
                    continue

                if impact in ["high", "medium", "low"]:
                    news_list.append({
                        "title" : title,
                        "impact": impact,
                        "time"  : dt_gaza,
                        "time_str": dt_gaza.strftime("%H:%M")
                    })
            except:
                continue

        news_list.sort(key=lambda x: x["time"])
        return news_list
    except Exception as e:
        print(f"خطأ في جلب الأخبار: {e}")
        return []

# ==================== هل نحن في وقت خبر قوي؟ ====================
def is_high_impact_news_time(news_list):
    now = datetime.now(GAZA_TZ)
    for news in news_list:
        if news["impact"] == "high":
            diff = (news["time"] - now).total_seconds() / 60
            if -15 <= diff <= 15:
                return True, news
    return False, None

# ==================== رسالة أخبار الصباح ====================
def send_news_message(news_list):
    if not news_list:
        return

    high   = [n for n in news_list if n["impact"] == "high"]
    medium = [n for n in news_list if n["impact"] == "medium"]
    low    = [n for n in news_list if n["impact"] == "low"]

    msg = (
        "📰 <b>أخبار USD اليوم</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
    )

    msg += "🕐 <i>الأوقات بتوقيت غزة (Asia/Gaza)</i>\n\n"

    if high:
        msg += "🔴 <b>أخبار قوية — ابتعد عن التداول:</b>\n"
        for n in high:
            msg += f"   ⏰ {n['time_str']} غزة | {n['title']}\n"
        msg += "\n"

    if medium:
        msg += "🟡 <b>أخبار متوسطة — انتبه:</b>\n"
        for n in medium:
            msg += f"   ⏰ {n['time_str']} غزة | {n['title']}\n"
        msg += "\n"

    if low:
        msg += "🟢 <b>أخبار ضعيفة — لا تأثير كبير:</b>\n"
        for n in low:
            msg += f"   ⏰ {n['time_str']} غزة | {n['title']}\n"
        msg += "\n"

    msg += (
        "━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <b>تنبيه:</b> لا تتداول 15 دقيقة قبل وبعد الأخبار القوية 🔴\n"
        "🤖 SMC Gold Bot"
    )

    send_telegram(msg)
    print("✅ رسالة الأخبار أُرسلت")

# ==================== رسالة الصباح ====================
def send_morning_message(news_list):
    now = datetime.now(GAZA_TZ)
    day_ar = ["الاثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"][now.weekday()]
    date_str = now.strftime(f"{day_ar} %d/%m/%Y")

    high_news = [n for n in news_list if n["impact"] == "high"]
    news_warn = ""
    if high_news:
        news_warn = "\n⚠️ <b>تحذير:</b> يوم فيه أخبار قوية!\n"
        for n in high_news:
            news_warn += f"   🔴 {n['time_str']} | {n['title']}\n"

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
    send_telegram(msg)
    print(f"✅ رسالة الصباح - {date_str}")

# ==================== جلب بيانات الذهب ====================
def get_candles():
    try:
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol"    : "XAU/USD",
            "interval"  : "5min",
            "outputsize": 200,
            "apikey"    : "0cef5bb56a314b6289f3db0b648f84b5"
        }
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if "values" not in data:
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
        return candles
    except:
        return None

# ==================== Pivot ====================
def pivot_high(highs, i, length):
    if i < length or i + length >= len(highs): return None
    val = highs[i]
    for j in range(1, length + 1):
        if highs[i-j] >= val or highs[i+j] >= val: return None
    return val

def pivot_low(lows, i, length):
    if i < length or i + length >= len(lows): return None
    val = lows[i]
    for j in range(1, length + 1):
        if lows[i-j] <= val or lows[i+j] <= val: return None
    return val

# ==================== تحليل SMC ====================
def analyze(candles):
    opens  = [c["open"]  for c in candles]
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]
    closes = [c["close"] for c in candles]
    n      = len(candles)

    trend = 0
    pending_ph = None; pending_ph_bar = -1
    pending_pl = None; pending_pl_bar = -1
    idm_level = None; idm_swept = False; idm_is_high = False
    ob_list = []
    buy_signal = False; sell_signal = False
    sig_entry = sig_sl = sig_tp = sig_rr = None

    for i in range(n):
        ph = pivot_high(highs, i, SWING_LEN)
        pl = pivot_low(lows, i, SWING_LEN)
        if ph is not None: pending_ph = ph; pending_ph_bar = i - SWING_LEN
        if pl is not None: pending_pl = pl; pending_pl_bar = i - SWING_LEN

        bull_break = (pending_ph is not None and i > 0 and closes[i-1] <= pending_ph and closes[i] > pending_ph)
        bear_break = (pending_pl is not None and i > 0 and closes[i-1] >= pending_pl and closes[i] < pending_pl)

        if bull_break:
            if pending_pl is not None:
                idm_level = pending_pl; idm_is_high = False; idm_swept = False
            trend = 1
            start_bar = pending_pl_bar if pending_pl_bar != -1 else 0
            for k in range(1, min(OB_LOOKBACK, i - start_bar) + 1):
                idx = i - k
                if idx < start_bar: break
                if closes[idx] < opens[idx]:
                    ob_list.append({"top": highs[idx], "bottom": lows[idx], "bullish": True, "touches": 0, "valid": True, "signaled": False})
                    if len(ob_list) > MAX_OB_KEEP: ob_list.pop(0)
                    break
            pending_ph = None

        if bear_break:
            if pending_ph is not None:
                idm_level = pending_ph; idm_is_high = True; idm_swept = False
            trend = -1
            start_bar = pending_ph_bar if pending_ph_bar != -1 else 0
            for k in range(1, min(OB_LOOKBACK, i - start_bar) + 1):
                idx = i - k
                if idx < start_bar: break
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

        if i == n - 2 and (not REQUIRE_IDM or idm_swept):
            for ob in ob_list:
                if not ob["valid"] or ob["signaled"]: continue
                touch = (lows[i] <= ob["top"] and highs[i] >= ob["bottom"]) if USE_WICK_TOUCH else (ob["bottom"] <= closes[i] <= ob["top"])
                if not touch: continue
                if trend == 1 and ob["bullish"] and not buy_signal and not sell_signal:
                    entry = ob["top"]; sl = ob["bottom"] * (1 - SL_BUFFER_PCT/100)
                    risk = entry - sl
                    if risk > 0:
                        ob["signaled"] = True; buy_signal = True
                        sig_entry = entry; sig_sl = sl; sig_tp = entry + risk * MIN_RR; sig_rr = MIN_RR
                elif trend == -1 and not ob["bullish"] and not buy_signal and not sell_signal:
                    entry = ob["bottom"]; sl = ob["top"] * (1 + SL_BUFFER_PCT/100)
                    risk = sl - entry
                    if risk > 0:
                        ob["signaled"] = True; sell_signal = True
                        sig_entry = entry; sig_sl = sl; sig_tp = entry - risk * MIN_RR; sig_rr = MIN_RR

    return {"buy": buy_signal, "sell": sell_signal, "entry": sig_entry,
            "sl": sig_sl, "tp": sig_tp, "rr": sig_rr, "trend": trend,
            "time": candles[-1]["time"] if candles else ""}

# ==================== الحلقة الرئيسية ====================
def main():
    send_telegram(
        "🤖 <b>SMC Gold Bot</b> شغّال!\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📊 الزوج: XAU/USD | فريم M5\n"
        "🌅 رسالة صباحية كل يوم 8:00\n"
        "📰 تنبيه أخبار USD تلقائياً\n"
        "📈 إشارات شراء/بيع SMC\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✅ جاهز للعمل!"
    )
    print("✅ البوت شغّال - يراقب XAUUSD M5")

    last_signal_time  = ""
    morning_sent_date = ""
    news_sent_date    = ""
    news_alert_sent   = set()
    daily_news        = []

    while True:
        try:
            now_gaza  = datetime.now(GAZA_TZ)
            today_str = now_gaza.strftime("%Y-%m-%d")

            # جلب أخبار اليوم مرة واحدة
            if news_sent_date != today_str:
                daily_news = get_usd_news()
                news_sent_date = today_str

            # رسالة الصباح 8:00
            if now_gaza.hour == 8 and now_gaza.minute == 0 and morning_sent_date != today_str:
                send_morning_message(daily_news)
                send_news_message(daily_news)
                morning_sent_date = today_str

            # تنبيه قبل خبر قوي بـ 15 دقيقة
            for news in daily_news:
                if news["impact"] == "high":
                    diff_min = (news["time"] - now_gaza).total_seconds() / 60
                    news_key = news["time_str"] + "_" + today_str

                    # تنبيه قبل 15 دقيقة
                    if 14 <= diff_min <= 15 and news_key + "_pre" not in news_alert_sent:
                        news_alert_sent.add(news_key + "_pre")
                        send_telegram(
                            f"🚨 <b>تحذير خبر قوي!</b>\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"🔴 الخبر: <b>{news['title']}</b>\n"
                            f"⏰ الوقت: <b>{news['time_str']} بتوقيت غزة</b>\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"⛔ <b>لا تفتح صفقات جديدة الآن!</b>\n"
                            f"⏳ انتظر 15 دقيقة بعد الخبر\n"
                            f"🤖 SMC Gold Bot"
                        )
                        print(f"⚠️ تنبيه خبر قوي: {news['title']} @ {news['time_str']}")

                    # تنبيه بعد 15 دقيقة من الخبر
                    if -16 <= diff_min <= -15 and news_key + "_post" not in news_alert_sent:
                        news_alert_sent.add(news_key + "_post")
                        send_telegram(
                            f"✅ <b>انتهى وقت الخبر</b>\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"📰 {news['title']} | {news['time_str']}\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"🟢 يمكن التداول الآن بحذر\n"
                            f"🤖 SMC Gold Bot"
                        )

            # تحليل SMC وإشارات
            in_news, news_obj = is_high_impact_news_time(daily_news)

            candles = get_candles()
            if candles is None or len(candles) < 50:
                print("⚠️ ما قدر يجيب البيانات")
                time.sleep(60)
                continue

            result = analyze(candles)
            current_time = result["time"]

            if (result["buy"] or result["sell"]) and current_time != last_signal_time:
                last_signal_time = current_time
                direction = "🟢 شراء (BUY)" if result["buy"] else "🔴 بيع (SELL)"
                emoji = "📈" if result["buy"] else "📉"

                if in_news:
                    # في وقت خبر قوي — نبعث تحذير بدل الإشارة
                    send_telegram(
                        f"⚠️ <b>إشارة موجودة لكن...</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"{emoji} الاتجاه: <b>{direction}</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"🚨 <b>لا ندخل الآن!</b>\n"
                        f"🔴 يوجد خبر قوي: {news_obj['title']}\n"
                        f"⏰ الساعة: {news_obj['time_str']} بتوقيت غزة\n"
                        f"⏳ انتظر انتهاء الخبر\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"🤖 SMC Gold Bot"
                    )
                else:
                    send_telegram(
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
                print(f"✅ إشارة: {direction} @ {result['entry']:.2f}")

            else:
                trend_txt = "صاعد 📈" if result["trend"] == 1 else ("هابط 📉" if result["trend"] == -1 else "محايد")
                print(f"[{now_gaza.strftime('%H:%M:%S')}] مراقبة... الترند: {trend_txt} | السعر: {candles[-1]['close']:.2f}")

        except Exception as e:
            print(f"❌ خطأ: {e}")

        time.sleep(60)

if __name__ == "__main__":
    main()
