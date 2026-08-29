import requests
import time
from datetime import datetime
import pytz

# ==================== الإعدادات ====================
TELEGRAM_TOKEN = "8800189995:AAEAluegBqFTM_fXko38IS92efpEsOKDYqA"
CHAT_IDS       = ["6360489611", "8315710670"]

SWING_LEN      = 10
OB_LOOKBACK    = 60
OB_MAX_TOUCH   = 3
MAX_OB_KEEP    = 5
SL_BUFFER_PCT  = 0.15
MIN_RR         = 2.0
USE_WICK_TOUCH = True
REQUIRE_IDM    = False

GAZA_TZ = pytz.timezone("Asia/Gaza")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for chat_id in CHAT_IDS:
        try:
            requests.post(url, data={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=10)
        except:
            pass

def send_morning_message():
    now = datetime.now(GAZA_TZ)
    day_ar = ["الاثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"][now.weekday()]
    date_str = now.strftime(f"{day_ar} %d/%m/%Y")
    msg = (
        "🌅 <b>Good Morning Traders!</b> ☀️\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📅 {date_str}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📊 <b>SMC Gold Bot</b> | XAU/USD M5\n\n"
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

def pivot_high(highs, i, length):
    if i < length or i + length >= len(highs):
        return None
    val = highs[i]
    for j in range(1, length + 1):
        if highs[i-j] >= val or highs[i+j] >= val:
            return None
    return val

def pivot_low(lows, i, length):
    if i < length or i + length >= len(lows):
        return None
    val = lows[i]
    for j in range(1, length + 1):
        if lows[i-j] <= val or lows[i+j] <= val:
            return None
    return val

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
        if ph is not None:
            pending_ph = ph; pending_ph_bar = i - SWING_LEN
        if pl is not None:
            pending_pl = pl; pending_pl_bar = i - SWING_LEN

        bull_break = (pending_ph is not None and i > 0 and
                      closes[i-1] <= pending_ph and closes[i] > pending_ph)
        bear_break = (pending_pl is not None and i > 0 and
                      closes[i-1] >= pending_pl and closes[i] < pending_pl)

        if bull_break:
            if pending_pl is not None:
                idm_level = pending_pl; idm_is_high = False; idm_swept = False
            trend = 1
            start_bar = pending_pl_bar if pending_pl_bar != -1 else 0
            for k in range(1, min(OB_LOOKBACK, i - start_bar) + 1):
                idx = i - k
                if idx < start_bar: break
                if closes[idx] < opens[idx]:
                    ob_list.append({"top": highs[idx], "bottom": lows[idx], "bullish": True,
                                    "touches": 0, "valid": True, "signaled": False})
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

def main():
    send_telegram(
        "🤖 <b>SMC Gold Bot</b> شغّال!\n"
        "📊 الزوج: XAU/USD | فريم M5\n"
        "⏳ يراقب السوق ويرسل إشارات شراء/بيع تلقائياً\n"
        "🌅 رسالة صباحية كل يوم الساعة 8:00 ✅"
    )
    print("✅ البوت شغّال - يراقب XAUUSD M5")

    last_signal_time = ""
    morning_sent_date = ""

    while True:
        try:
            now_gaza = datetime.now(GAZA_TZ)
            today_str = now_gaza.strftime("%Y-%m-%d")
            if now_gaza.hour == 8 and now_gaza.minute == 0 and morning_sent_date != today_str:
                send_morning_message()
                morning_sent_date = today_str

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
                msg = (
                    f"{emoji} <b>إشارة SMC جديدة!</b>\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"الزوج:  <b>XAU/USD (ذهب)</b>\n"
                    f"الفريم: <b>M5</b>\n"
                    f"الاتجاه: <b>{direction}</b>\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"💰 دخول:  <b>{result['entry']:.2f}</b>\n"
                    f"🛑 ستوب:  <b>{result['sl']:.2f}</b>\n"
                    f"🎯 هدف:   <b>{result['tp']:.2f}</b>\n"
                    f"📊 R:R =  <b>1:{result['rr']:.1f}</b>\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"🕐 {current_time}"
                )
                send_telegram(msg)
                print(f"✅ إشارة: {direction} @ {result['entry']:.2f}")
            else:
                trend_txt = "صاعد 📈" if result["trend"] == 1 else ("هابط 📉" if result["trend"] == -1 else "محايد")
                print(f"[{now_gaza.strftime('%H:%M:%S')}] مراقبة... الترند: {trend_txt} | السعر: {candles[-1]['close']:.2f}")

        except Exception as e:
            print(f"❌ خطأ: {e}")

        time.sleep(60)

if __name__ == "__main__":
    main()
