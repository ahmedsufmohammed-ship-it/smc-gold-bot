import requests
import time
import json
from datetime import datetime

# ==================== الإعدادات ====================
TELEGRAM_TOKEN = "8800189995:AAEAluegBqFTM_fXko38IS92efpEsOKDYqA"
CHAT_ID        = "6360489611"
SYMBOL         = "XAU/USD"

# إعدادات الاستراتيجية
SWING_LEN      = 10
OB_LOOKBACK    = 60
OB_MAX_TOUCH   = 3
MAX_OB_KEEP    = 5
SL_BUFFER_PCT  = 0.15
MIN_RR         = 2.0
USE_WICK_TOUCH = True
REQUIRE_IDM    = False

# ==================== إرسال رسالة تيليغرام ====================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=10)
    except:
        pass

# ==================== جلب بيانات الذهب من API مجانية ====================
def get_candles():
    """
    جلب بيانات XAUUSD M5 من Twelve Data (مجاني - 800 طلب/يوم)
    """
    try:
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol"    : "XAU/USD",
            "interval"  : "5min",
            "outputsize": 200,
            "apikey"    : "0cef5bb56a314b6289f3db0b648f84b5"   # <-- ضع مفتاحك المجاني هون
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

# ==================== كشف Pivot High / Low ====================
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

# ==================== المنطق الرئيسي للاستراتيجية ====================
def analyze(candles):
    opens  = [c["open"]  for c in candles]
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]
    closes = [c["close"] for c in candles]
    n      = len(candles)

    # --- متغيرات الهيكل ---
    trend         = 0
    pending_ph    = None; pending_ph_bar = -1
    pending_pl    = None; pending_pl_bar = -1
    prev_ph       = None; prev_ph_bar    = -1
    prev_pl       = None; prev_pl_bar    = -1
    raw_last_ph   = None; raw_last_ph_bar = -1
    raw_last_pl   = None; raw_last_pl_bar = -1

    idm_level  = None
    idm_bar    = -1
    idm_swept  = False
    idm_is_high = False

    ob_list = []  # قائمة الأوردر بلوك

    buy_signal  = False
    sell_signal = False
    sig_entry = sig_sl = sig_tp = sig_rr = None

    for i in range(n):
        # كشف القمم والقيعان
        ph = pivot_high(highs, i, SWING_LEN)
        pl = pivot_low(lows, i, SWING_LEN)

        if ph is not None:
            prev_ph = pending_ph;     prev_ph_bar = pending_ph_bar
            pending_ph = ph;          pending_ph_bar = i - SWING_LEN
            raw_last_ph = ph;         raw_last_ph_bar = i - SWING_LEN

        if pl is not None:
            prev_pl = pending_pl;     prev_pl_bar = pending_pl_bar
            pending_pl = pl;          pending_pl_bar = i - SWING_LEN
            raw_last_pl = pl;         raw_last_pl_bar = i - SWING_LEN

        # كشف الكسر الصاعد
        bull_break = (pending_ph is not None and i > 0 and
                      closes[i-1] <= pending_ph and closes[i] > pending_ph)

        # كشف الكسر الهابط
        bear_break = (pending_pl is not None and i > 0 and
                      closes[i-1] >= pending_pl and closes[i] < pending_pl)

        # معالجة الكسر الصاعد
        if bull_break:
            if pending_pl is not None:
                idm_level   = pending_pl
                idm_bar     = pending_pl_bar
                idm_is_high = False
                idm_swept   = False

            trend = 1

            # إضافة أوردر بلوك صاعد
            start_bar = pending_pl_bar if pending_pl_bar != -1 else pending_ph_bar
            ob_top = ob_bot = ob_idx = None
            for k in range(1, min(OB_LOOKBACK, i - (start_bar or 0)) + 1):
                idx = i - k
                if start_bar and idx < start_bar:
                    break
                if closes[idx] < opens[idx]:  # شمعة هابطة
                    ob_top = highs[idx]
                    ob_bot = lows[idx]
                    ob_idx = idx
                    break

            if ob_idx is not None:
                ob_list.append({
                    "top": ob_top, "bottom": ob_bot,
                    "bullish": True, "touches": 0,
                    "valid": True, "signaled": False,
                    "start_bar": ob_idx
                })
                if len(ob_list) > MAX_OB_KEEP:
                    ob_list.pop(0)

            pending_ph = None; prev_ph = None

        # معالجة الكسر الهابط
        if bear_break:
            if pending_ph is not None:
                idm_level   = pending_ph
                idm_bar     = pending_ph_bar
                idm_is_high = True
                idm_swept   = False

            trend = -1

            # إضافة أوردر بلوك هابط
            start_bar = pending_ph_bar if pending_ph_bar != -1 else pending_pl_bar
            ob_top = ob_bot = ob_idx = None
            for k in range(1, min(OB_LOOKBACK, i - (start_bar or 0)) + 1):
                idx = i - k
                if start_bar and idx < start_bar:
                    break
                if closes[idx] > opens[idx]:  # شمعة صاعدة
                    ob_top = highs[idx]
                    ob_bot = lows[idx]
                    ob_idx = idx
                    break

            if ob_idx is not None:
                ob_list.append({
                    "top": ob_top, "bottom": ob_bot,
                    "bullish": False, "touches": 0,
                    "valid": True, "signaled": False,
                    "start_bar": ob_idx
                })
                if len(ob_list) > MAX_OB_KEEP:
                    ob_list.pop(0)

            pending_pl = None; prev_pl = None

        # متابعة سحب IDM
        if not idm_swept and idm_level is not None:
            if idm_is_high and highs[i] >= idm_level:
                idm_swept = True
            if not idm_is_high and lows[i] <= idm_level:
                idm_swept = True

        # تحديث لمسات OB وإلغاؤها
        for ob in ob_list:
            if not ob["valid"]:
                continue
            if ob["bullish"]:
                if lows[i] <= ob["top"] and lows[i] >= ob["bottom"]:
                    ob["touches"] += 1
                if closes[i] < ob["bottom"]:
                    ob["valid"] = False
            else:
                if highs[i] >= ob["bottom"] and highs[i] <= ob["top"]:
                    ob["touches"] += 1
                if closes[i] > ob["top"]:
                    ob["valid"] = False
            if ob["touches"] >= OB_MAX_TOUCH:
                ob["valid"] = False

        # كشف إشارات الدخول على آخر شمعة مكتملة
        if i == n - 2:  # آخر شمعة مكتملة
            idm_ok = (not REQUIRE_IDM) or idm_swept

            if idm_ok:
                for ob in ob_list:
                    if not ob["valid"] or ob["signaled"]:
                        continue

                    if USE_WICK_TOUCH:
                        touch = lows[i] <= ob["top"] and highs[i] >= ob["bottom"]
                    else:
                        touch = ob["bottom"] <= closes[i] <= ob["top"]

                    if not touch:
                        continue

                    # إشارة شراء
                    if trend == 1 and ob["bullish"] and not buy_signal and not sell_signal:
                        entry = ob["top"]
                        sl    = ob["bottom"] * (1 - SL_BUFFER_PCT / 100)
                        risk  = entry - sl
                        if risk > 0:
                            tp = entry + risk * MIN_RR
                            ob["signaled"] = True
                            buy_signal = True
                            sig_entry = entry
                            sig_sl    = sl
                            sig_tp    = tp
                            sig_rr    = MIN_RR

                    # إشارة بيع
                    elif trend == -1 and not ob["bullish"] and not buy_signal and not sell_signal:
                        entry = ob["bottom"]
                        sl    = ob["top"] * (1 + SL_BUFFER_PCT / 100)
                        risk  = sl - entry
                        if risk > 0:
                            tp = entry - risk * MIN_RR
                            ob["signaled"] = True
                            sell_signal = True
                            sig_entry = entry
                            sig_sl    = sl
                            sig_tp    = tp
                            sig_rr    = MIN_RR

    return {
        "buy"  : buy_signal,
        "sell" : sell_signal,
        "entry": sig_entry,
        "sl"   : sig_sl,
        "tp"   : sig_tp,
        "rr"   : sig_rr,
        "trend": trend,
        "time" : candles[-1]["time"] if candles else ""
    }

# ==================== حلقة التشغيل الرئيسية ====================
def main():
    send_telegram(
        "🤖 <b>SMC Gold Bot</b> شغّال الحين!\n"
        "📊 الزوج: XAU/USD | فريم M5\n"
        "⏳ يراقب السوق ويرسل إشارات شراء/بيع تلقائياً..."
    )
    print("✅ البوت شغّال - يراقب XAUUSD M5")

    last_signal_time = ""

    while True:
        try:
            candles = get_candles()

            if candles is None or len(candles) < 50:
                print("⚠️ ما قدر يجيب البيانات، ينتظر...")
                time.sleep(60)
                continue

            result = analyze(candles)
            current_time = result["time"]

            # إرسال التنبيه مرة واحدة لكل شمعة
            if (result["buy"] or result["sell"]) and current_time != last_signal_time:
                last_signal_time = current_time

                direction = "🟢 شراء (BUY)" if result["buy"] else "🔴 بيع (SELL)"
                emoji     = "📈" if result["buy"] else "📉"

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
                print(f"✅ إشارة أُرسلت: {direction} @ {result['entry']:.2f}")
            else:
                trend_txt = "صاعد 📈" if result["trend"] == 1 else ("هابط 📉" if result["trend"] == -1 else "محايد")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] مراقبة... الترند: {trend_txt} | السعر: {candles[-1]['close']:.2f}")

        except Exception as e:
            print(f"❌ خطأ: {e}")

        # انتظر 5 دقايق (نفس الفريم)
        time.sleep(300)

if __name__ == "__main__":
    main()
