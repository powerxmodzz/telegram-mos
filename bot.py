#!/usr/bin/env python3
# ============================================================
#   POWER OTP BOT - Pure Requests
#   No library needed - works on Python 3.8+
#   t.me/power_method
# ============================================================

import requests
import time
import sys
import signal

def handle_signal(sig, frame):
    print("Bot band ho raha hai...")
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

BOT_TOKEN   = "8727882995:AAHfPN4mNKhI6fhjZcSIg5zzH-Z50Vjzdzc"
GROUP_ID    = -1003886766454
NUMBERS_URL = "https://t.me/dp_numbers"
BACKUP_URL  = "https://t.me/power_method"
API         = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ─── FIXED COUNTRY LIST ──────────────────────────────────────
# [code, flag, dial, name, display_name]
COUNTRIES = [
    ["CH",  "🇨🇭", "41",  "Switzerland",   "🇨🇭 Switzerland"],
    ["VN",  "🇻🇳", "84",  "Vietnam",       "🇻🇳 Vietnam"],
    ["AF",  "🇦🇫", "93",  "Afghanistan",   "🇦🇫 Afghanistan"],
    ["IL",  "🇮🇱", "972", "Israel",        "🇮🇱 Israel 💩"],
    ["PK",  "🇵🇰", "92",  "Pakistan",      "🇵🇰 Pakistan"],
    ["CI",  "🇨🇮", "225", "Ivory Coast",   "🇨🇮 Ivory Coast"],
    ["NP",  "🇳🇵", "977", "Nepal",         "🇳🇵 Nepal"],
    ["KZ",  "🇰🇿", "7",   "Kazakhstan",    "🇰🇿 Kazakhstan"],
    ["RU",  "🇷🇺", "7",   "Russia",        "🇷🇺 Russia"],
    ["ZW",  "🇿🇼", "263", "Zimbabwe",      "🇿🇼 Zimbabwe"],
    ["VE",  "🇻🇪", "58",  "Venezuela",     "🇻🇪 Venezuela"],
    ["XX",  "🌐",  "",    "Unknown",       "🌐 Unknown Country"],
]

COUNTRY_MAP = {c[0]: c for c in COUNTRIES}

# User sessions
# {chat_id: {"state": ..., "country": [...], "last_country": [...]}}
SESSIONS = {}

# States
IDLE          = "idle"
PICK_COUNTRY  = "pick_country"
ENTER_NUMBER  = "enter_number"
ENTER_OTP     = "enter_otp"
NOTIF_TYPE    = "notif_type"
NOTIF_TITLE   = "notif_title"
NOTIF_MSG     = "notif_msg"
NOTIF_LINK    = "notif_link"

NOTIF_TYPES = [
    "Alert", "Warning", "Success",
    "Error", "Announcement", "Urgent", "Message"
]
NOTIF_EMOJI = {
    "Alert": "🔔", "Warning": "⚠️", "Success": "✅",
    "Error": "❌", "Announcement": "📢", "Urgent": "🔴", "Message": "💬"
}

# ─── HELPERS ─────────────────────────────────────────────────

def mask_number(n: str) -> str:
    n = n.strip().replace("+", "")
    if len(n) <= 6:
        return n
    return n[:3] + "XXXXX" + n[-3:]

def format_otp(raw: str) -> str:
    clean = "".join(c for c in raw if c.isdigit())
    if len(clean) == 6:
        return clean[:3] + "-" + clean[3:]
    return raw.strip()

def sess(chat_id):
    if chat_id not in SESSIONS:
        SESSIONS[chat_id] = {"state": IDLE, "country": None, "data": {}}
    return SESSIONS[chat_id]

# ─── TELEGRAM API ─────────────────────────────────────────────

def tg(method, **kw):
    try:
        r = requests.post(f"{API}/{method}", json=kw, timeout=15)
        return r.json()
    except Exception as e:
        print(f"API Error [{method}]: {e}", flush=True)
        return {}

def send(chat_id, text, kb=None, parse="Markdown"):
    p = {"chat_id": chat_id, "text": text,
         "parse_mode": parse, "disable_web_page_preview": True}
    if kb:
        p["reply_markup"] = {"inline_keyboard": kb}
    return tg("sendMessage", **p)

def edit(chat_id, mid, text, kb=None):
    p = {"chat_id": chat_id, "message_id": mid,
         "text": text, "parse_mode": "Markdown",
         "disable_web_page_preview": True}
    if kb:
        p["reply_markup"] = {"inline_keyboard": kb}
    return tg("editMessageText", **p)

def answer(cbid):
    tg("answerCallbackQuery", callback_query_id=cbid)

def group_send(text, kb):
    tg("sendMessage",
       chat_id=GROUP_ID, text=text,
       disable_web_page_preview=True,
       reply_markup={"inline_keyboard": kb})

# ─── KEYBOARDS ───────────────────────────────────────────────

def country_kb():
    """3 columns of country buttons"""
    rows = []
    row  = []
    for c in COUNTRIES:
        row.append({"text": c[4], "callback_data": f"c_{c[0]}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows

def otp_kb(fmt_otp=None):
    rows = []
    if fmt_otp:
        rows.append([{"text": f"  {fmt_otp}  ", "callback_data": "noop"}])
    rows.append([
        {"text": "NUMBERS", "url": NUMBERS_URL},
        {"text": "BACKUP",  "url": BACKUP_URL},
    ])
    return rows

def notif_kb():
    return [[
        {"text": "NUMBERS", "url": NUMBERS_URL},
        {"text": "BACKUP",  "url": BACKUP_URL},
    ]]

def after_send_kb(country_code):
    """After sending OTP - show quick options"""
    return [
        [{"text": "Send Another OTP (Same Country)", "callback_data": f"again_{country_code}"}],
        [{"text": "Change Country", "callback_data": "change_country"}],
        [{"text": "Main Menu", "callback_data": "menu"}],
    ]

def notif_type_kb():
    rows = []
    row  = []
    for i, t in enumerate(NOTIF_TYPES):
        e = NOTIF_EMOJI.get(t, "")
        row.append({"text": f"{e} {t}", "callback_data": f"nt_{i}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows

# ─── COMMAND HANDLERS ────────────────────────────────────────

def cmd_start(chat_id):
    s = sess(chat_id)
    s["state"] = IDLE
    send(chat_id,
        "*POWER OTP BOT*\n\n"
        "/otp - Number + OTP bhejo\n"
        "/notif - Notification bhejo\n"
        "/cancel - Band karo",
        [[
            {"text": "Send OTP", "callback_data": "go_otp"},
            {"text": "Notification", "callback_data": "go_notif"},
        ]]
    )

def cmd_otp(chat_id):
    s = sess(chat_id)
    # If country already selected, ask if want same
    if s.get("country"):
        c = s["country"]
        send(chat_id,
            f"*Country:* {c[4]} (+{c[2]})\n\nIs country se continue karein?",
            [
                [{"text": f"Haan - {c[4]}", "callback_data": f"again_{c[0]}"}],
                [{"text": "Nahi - Change Country", "callback_data": "change_country"}],
            ]
        )
    else:
        s["state"] = PICK_COUNTRY
        send(chat_id, "*Country select karo:*", country_kb())

def cmd_cancel(chat_id):
    s = sess(chat_id)
    s["state"] = IDLE
    send(chat_id, "Cancel ho gaya. /otp ya /notif se shuru karo.")

def cmd_notif(chat_id):
    s = sess(chat_id)
    s["state"] = NOTIF_TYPE
    s["data"]  = {}
    send(chat_id, "*Notification type select karo:*", notif_type_kb())

# ─── TEXT HANDLERS ───────────────────────────────────────────

def handle_text(chat_id, text):
    s     = sess(chat_id)
    state = s["state"]
    data  = s.get("data", {})
    text  = text.strip()

    # ── OTP number input ──
    if state == ENTER_NUMBER:
        phone = text.replace("+", "")
        if not phone.isdigit() or len(phone) < 6:
            send(chat_id, "Galat number! Sirf digits daalo (e.g. 41783380461)")
            return
        c      = s["country"]
        masked = mask_number(phone)
        data["phone"]  = phone
        data["masked"] = masked
        s["state"] = ENTER_OTP
        send(chat_id,
            f"Number: `{masked}`\n\n"
            f"OTP daalo (6 digits)\n"
            f"Skip: *skip* likho\n\n/cancel"
        )

    # ── OTP code input ──
    elif state == ENTER_OTP:
        c      = s["country"]
        masked = data.get("masked", "")
        fmt_otp = None
        if text.lower() != "skip":
            fmt_otp = format_otp(text)

        # Build group message
        # Format: 📱 | 🇵🇰 #PK 923XXXXX928
        code = c[0] if c[0] != "XX" else "??"
        flag = c[1]
        msg  = f"📱 | {flag} #{code} {masked}"

        group_send(msg, otp_kb(fmt_otp))

        # Confirm to user
        reply = f"*Sent!*\n\n`{msg}`"
        if fmt_otp:
            reply += f"\nOTP: `{fmt_otp}`"
        send(chat_id, reply, after_send_kb(c[0]))
        s["state"] = IDLE

    # ── Notification flows ──
    elif state == NOTIF_TITLE:
        data["ntitle"] = "" if text.lower() == "skip" else text
        s["state"] = NOTIF_MSG
        send(chat_id, "*Message daalo:*\n\n/cancel")

    elif state == NOTIF_MSG:
        data["nmsg"] = text
        s["state"]   = NOTIF_LINK
        send(chat_id, "*Link daalo* (skip = skip likhna)\n\n/cancel")

    elif state == NOTIF_LINK:
        link  = "" if text.lower() == "skip" else text
        ntype = data.get("ntype", "Alert")
        emoji = NOTIF_EMOJI.get(ntype, "")
        title = data.get("ntitle", "")
        msg   = data.get("nmsg", "")

        full  = f"{emoji} {ntype}\n"
        if title:
            full += f"\n{title}\n"
        full += f"\n{msg}\n"
        if link:
            full += f"\n{link}\n"
        full += "\n__________\n@power_method"

        group_send(full, notif_kb())
        send(chat_id, "*Notification bhej di!*")
        s["state"] = IDLE
        s["data"]  = {}

    else:
        send(chat_id,
            "/otp - OTP bhejo\n"
            "/notif - Notification\n"
            "/cancel - Cancel"
        )

# ─── CALLBACK HANDLER ────────────────────────────────────────

def handle_cb(cbid, chat_id, mid, data):
    answer(cbid)
    s = sess(chat_id)

    # Menu buttons
    if data == "go_otp":
        cmd_otp(chat_id)
        return
    if data == "go_notif":
        cmd_notif(chat_id)
        return
    if data == "menu":
        cmd_start(chat_id)
        return
    if data == "noop":
        return

    # Change country
    if data == "change_country":
        s["state"] = PICK_COUNTRY
        send(chat_id, "*Country select karo:*", country_kb())
        return

    # Same country - send again
    if data.startswith("again_"):
        code = data[6:]
        c    = COUNTRY_MAP.get(code)
        if not c:
            return
        s["country"] = c
        s["state"]   = ENTER_NUMBER
        s["data"]    = {}

        # Unknown country - ask for code too
        if code == "XX":
            send(chat_id,
                f"*{c[4]}*\n\n"
                f"Number daalo (country code samait, e.g. 1234567890)\n\n/cancel"
            )
        else:
            send(chat_id,
                f"*{c[4]}* (+{c[2]})\n\n"
                f"Number daalo (country code samait)\n"
                f"Example: `{c[2]}XXXXXXXXX`\n\n/cancel"
            )
        return

    # Country selected
    if data.startswith("c_"):
        code = data[2:]
        c    = COUNTRY_MAP.get(code)
        if not c:
            return
        s["country"] = c
        s["state"]   = ENTER_NUMBER
        s["data"]    = {}

        if code == "XX":
            edit(chat_id, mid,
                f"*{c[4]}*\n\n"
                f"Number daalo (country code samait, e.g. 1234567890)\n\n/cancel"
            )
        else:
            edit(chat_id, mid,
                f"*{c[4]}* selected! (+{c[2]})\n\n"
                f"Number daalo (country code samait)\n"
                f"Example: `{c[2]}XXXXXXXXX`\n\n/cancel"
            )
        return

    # Notification type
    if data.startswith("nt_"):
        idx = int(data[3:])
        ntype = NOTIF_TYPES[idx]
        emoji = NOTIF_EMOJI.get(ntype, "")
        s["data"]["ntype"] = ntype
        s["state"] = NOTIF_TITLE
        edit(chat_id, mid,
            f"*{emoji} {ntype}*\n\n"
            f"Title daalo (skip = skip likhna)\n\n/cancel"
        )
        return

# ─── MAIN POLLING LOOP ───────────────────────────────────────

def main():
    print("=" * 46, flush=True)
    print("  POWER OTP BOT - CHALU HO GAYA!", flush=True)
    print("  /otp - Number + OTP bhejo")
    print("  /notif - Notification bhejo")
    print("  /cancel - Band karo")
    print("  Bot chal raha hai...", flush=True)
    print("=" * 46, flush=True)

    offset = 0
    while True:
        try:
            r = requests.get(
                f"{API}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35
            )
            updates = r.json().get("result", [])

            for upd in updates:
                offset = upd["update_id"] + 1

                if "message" in upd:
                    msg     = upd["message"]
                    chat_id = msg["chat"]["id"]
                    text    = msg.get("text", "")
                    if not text:
                        continue

                    print(f"[MSG] {chat_id}: {text[:40]}", flush=True)

                    if text.startswith("/start") or text.startswith("/help"):
                        cmd_start(chat_id)
                    elif text.startswith("/otp"):
                        cmd_otp(chat_id)
                    elif text.startswith("/notif"):
                        cmd_notif(chat_id)
                    elif text.startswith("/cancel"):
                        cmd_cancel(chat_id)
                    else:
                        handle_text(chat_id, text)

                elif "callback_query" in upd:
                    cb      = upd["callback_query"]
                    cbid    = cb["id"]
                    chat_id = cb["message"]["chat"]["id"]
                    mid     = cb["message"]["message_id"]
                    cbdata  = cb.get("data", "")
                    print(f"[BTN] {chat_id}: {cbdata}", flush=True)
                    handle_cb(cbid, chat_id, mid, cbdata)

        except requests.exceptions.ReadTimeout:
            continue
        except requests.exceptions.ConnectionError:
            print("Internet error - 5s baad retry...", flush=True)
            time.sleep(5)
        except Exception as e:
            print(f"Error: {e}", flush=True)
            time.sleep(2)

if __name__ == "__main__":
    main()
