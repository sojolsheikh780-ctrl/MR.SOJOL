"""
╔══════════════════════════════════════════════════════════════════╗
║  AI ASSISTANT BOT — ULTIMATE SINGLE-FILE EDITION                 ║
║  Features:                                                       ║
║   • AI Chat (GPT / Gemini / Claude)                              ║
║   • Image Edit (photo + prompt)                                  ║
║   • Voice (Whisper STT + TTS reply)                              ║
║   • Group support (/ai + mention)                                ║
║   • Referral + leaderboard                                       ║
║   • Multi-language (বাংলা / English)                             ║
║   • Telegram Stars + bKash/Nagad payments                        ║
║   • Daily free trial                                             ║
║   • Admin panel (bot + web)                                      ║
║   • Web dashboard (FastAPI + live charts)                        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import io, os, time, base64, random, string, asyncio, logging, sqlite3, threading
from functools import wraps

from telegram import (Update, InlineKeyboardButton as B, InlineKeyboardMarkup as M,
                      LabeledPrice)
from telegram.constants import ParseMode
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler,
                          MessageHandler, PreCheckoutQueryHandler, ContextTypes, filters)
from openai import AsyncOpenAI

# ══════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════
BOT_TOKEN       = os.getenv("BOT_TOKEN", "PASTE_BOT_TOKEN_HERE")
ADMIN_IDS       = [int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",") if x.strip()]
PAYMENT_NUMBER  = "01342923284"

FREE_TEXT, FREE_IMG = 5, 2
COST_TEXT, COST_IMG = 1, 5
STARS_MULT = 2

PACKAGES = {
    "p50":  {"bdt": 50,  "credits": 100},
    "p200": {"bdt": 200, "credits": 500},
    "p500": {"bdt": 500, "credits": 1500},
}

REF_SIGNUP_BONUS   = 20
REF_PURCHASE_BONUS = 100
NEW_USER_BONUS     = 30

WEB_PASSWORD = os.getenv("WEB_PASSWORD", "admin123")
WEB_SECRET   = os.getenv("WEB_SECRET", "change-this-secret-key-32-char-minimum")
WEB_PORT     = int(os.getenv("WEB_PORT", "8080"))
WEB_ENABLED  = os.getenv("WEB_ENABLED", "1") == "1"

OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE        = os.getenv("OPENAI_BASE", "https://api.openai.com/v1")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
IMAGE_MODEL        = os.getenv("IMAGE_MODEL", "gpt-image-1")

DB_PATH = "ai_bot.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot")

# ══════════════════════════════════════════════════════════════════
#  i18n
# ══════════════════════════════════════════════════════════════════
STRINGS = {
    "bn": {
        "welcome":       "🤖 <b>AI Assistant Bot</b>\n\n💬 AI Chat · 🎨 Image · 🎤 Voice\n🧠 GPT / Gemini / Claude\n🎁 Refer & Earn · 👥 Group\n\n🆓 প্রতিদিন free trial!",
        "ai_chat":       "💬 AI Chat", "ai_img": "🎨 Image Edit",
        "ai_voice":      "🎤 Voice Chat", "model": "🧠 Model",
        "buy":           "💰 Buy Credits", "account": "👤 My Account",
        "referral":      "🎁 Refer & Earn", "reset": "🔄 Reset Chat",
        "support":       "📞 Support", "back": "⬅️ Back",
        "ask_question":  "💬 প্রশ্ন লিখুন:",
        "send_voice":    "🎤 Voice message পাঠান:",
        "send_image":    "🎨 ছবি পাঠান (caption-এ prompt):",
        "pick_model":    "🧠 Model বেছে নিন:",
        "credits_empty": "💎 Credits শেষ। কিনতে মেনু → Buy Credits।",
        "blocked":       "🚫 আপনি blocked।",
        "thinking":      "🤔 ভাবছি...",
        "listening":     "🎤 শুনছি...",
        "editing":       "🎨 এডিট করছি...",
        "txid_received": "🕐 TxID জমা হয়েছে। Admin verify করবে।",
        "lang_changed":  "✅ ভাষা বাংলা সেট হয়েছে।",
    },
    "en": {
        "welcome":       "🤖 <b>AI Assistant Bot</b>\n\n💬 AI Chat · 🎨 Image · 🎤 Voice\n🧠 GPT / Gemini / Claude\n🎁 Refer & Earn · 👥 Group\n\n🆓 Daily free trial!",
        "ai_chat":       "💬 AI Chat", "ai_img": "🎨 Image Edit",
        "ai_voice":      "🎤 Voice Chat", "model": "🧠 Model",
        "buy":           "💰 Buy Credits", "account": "👤 My Account",
        "referral":      "🎁 Refer & Earn", "reset": "🔄 Reset Chat",
        "support":       "📞 Support", "back": "⬅️ Back",
        "ask_question":  "💬 Type your question:",
        "send_voice":    "🎤 Send a voice message:",
        "send_image":    "🎨 Send a photo (prompt as caption):",
        "pick_model":    "🧠 Pick a model:",
        "credits_empty": "💎 Out of credits. Buy from menu.",
        "blocked":       "🚫 You are blocked.",
        "thinking":      "🤔 Thinking...",
        "listening":     "🎤 Listening...",
        "editing":       "🎨 Editing...",
        "txid_received": "🕐 TxID submitted. Awaiting verification.",
        "lang_changed":  "✅ Language set to English.",
    },
}

def t(key, lang="bn"):
    return STRINGS.get(lang, STRINGS["bn"]).get(key, key)

# ══════════════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════════════
def db():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def now(): return int(time.time())

def db_init():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            credits INTEGER DEFAULT 0, trial_date TEXT DEFAULT '',
            trial_text INTEGER DEFAULT 0, trial_img INTEGER DEFAULT 0,
            is_blocked INTEGER DEFAULT 0, preferred_model TEXT DEFAULT 'gpt',
            voice_reply INTEGER DEFAULT 0, lang TEXT DEFAULT 'bn',
            referred_by INTEGER DEFAULT 0, ref_code TEXT,
            ref_count INTEGER DEFAULT 0, joined_at INTEGER);
        CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, role TEXT DEFAULT 'mod');
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            package TEXT, amount INTEGER, txid TEXT UNIQUE,
            status TEXT DEFAULT 'pending', method TEXT DEFAULT 'bkash',
            created_at INTEGER, verified_at INTEGER);
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT, referrer INTEGER, referred INTEGER,
            joined_at INTEGER, rewarded INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS group_stats (
            chat_id INTEGER, chat_title TEXT, user_id INTEGER,
            calls INTEGER DEFAULT 0, last_call INTEGER,
            PRIMARY KEY (chat_id, user_id));
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT,
            user_id INTEGER, detail TEXT, created_at INTEGER);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        """)
        c.execute("INSERT OR IGNORE INTO settings VALUES ('system_prompt',"
                  "'You are a helpful AI assistant. Reply in the same language as the user.')")
        c.commit()

def get_setting(k, d=""):
    with db() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone()
        return r["value"] if r else d

def set_setting(k, v):
    with db() as c:
        c.execute("INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (k, str(v))); c.commit()

def upsert_user(uid, un, fn):
    today = time.strftime("%Y-%m-%d")
    with db() as c:
        if not c.execute("SELECT 1 FROM users WHERE user_id=?", (uid,)).fetchone():
            c.execute("INSERT INTO users (user_id,username,first_name,joined_at) VALUES (?,?,?,?)",
                      (uid, un or "", fn or "", now()))
        else:
            c.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?",
                      (un or "", fn or "", uid))
        r = c.execute("SELECT trial_date FROM users WHERE user_id=?", (uid,)).fetchone()
        if r["trial_date"] != today:
            c.execute("UPDATE users SET trial_date=?, trial_text=0, trial_img=0 WHERE user_id=?",
                      (today, uid))
        c.commit()

def get_user(uid):
    with db() as c:
        return c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()

def is_admin(uid):
    if uid in ADMIN_IDS: return True
    with db() as c:
        return c.execute("SELECT 1 FROM admins WHERE user_id=?", (uid,)).fetchone() is not None

def add_credits(uid, n):
    with db() as c:
        c.execute("UPDATE users SET credits=credits+? WHERE user_id=?", (n, uid)); c.commit()

def use_credit(uid, n):
    with db() as c:
        r = c.execute("SELECT credits FROM users WHERE user_id=?", (uid,)).fetchone()
        if r and r["credits"] >= n:
            c.execute("UPDATE users SET credits=credits-? WHERE user_id=?", (n, uid)); c.commit()
            return True
    return False

def inc_trial(uid, kind="text"):
    col = "trial_text" if kind == "text" else "trial_img"
    with db() as c:
        c.execute(f"UPDATE users SET {col}={col}+1 WHERE user_id=?", (uid,)); c.commit()

def set_lang_db(uid, lang):
    with db() as c:
        c.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, uid)); c.commit()

def log_event(cat, uid, det):
    with db() as c:
        c.execute("INSERT INTO logs (category,user_id,detail,created_at) VALUES (?,?,?,?)",
                  (cat, uid, det, now())); c.commit()

def track_group(chat_id, chat_title, uid):
    with db() as c:
        c.execute("""INSERT INTO group_stats (chat_id,chat_title,user_id,calls,last_call)
                     VALUES (?,?,?,1,?)
                     ON CONFLICT(chat_id,user_id) DO UPDATE SET
                       calls=calls+1, last_call=excluded.last_call,
                       chat_title=excluded.chat_title""",
                  (chat_id, chat_title, uid, now())); c.commit()

# ══════════════════════════════════════════════════════════════════
#  AI
# ══════════════════════════════════════════════════════════════════
PROVIDERS = {}
if OPENAI_API_KEY:
    PROVIDERS["gpt"] = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE)
if GEMINI_API_KEY:
    PROVIDERS["gemini"] = AsyncOpenAI(api_key=GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
if OPENROUTER_API_KEY:
    PROVIDERS["claude"] = AsyncOpenAI(api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1")

MODEL_MAP   = {"gpt":"gpt-4o-mini","gemini":"gemini-2.0-flash","claude":"anthropic/claude-3.5-sonnet"}
MODEL_NAMES = {"gpt":"🤖 GPT-4o Mini","gemini":"✨ Gemini 2.0 Flash","claude":"🎭 Claude 3.5"}
_history = {}

async def ai_chat(uid, msg, model="gpt"):
    if model not in PROVIDERS:
        model = next(iter(PROVIDERS), None)
        if not model: return "❌ No AI configured."
    hist = _history.setdefault(uid, [])
    hist.append({"role":"user","content":msg})
    try:
        r = await PROVIDERS[model].chat.completions.create(
            model=MODEL_MAP[model],
            messages=[{"role":"system","content":get_setting("system_prompt")}]+hist[-20:])
        out = r.choices[0].message.content
        hist.append({"role":"assistant","content":out})
        return out
    except Exception as e:
        return f"❌ {model} error: {e}"

async def ai_edit(img_bytes, prompt, model="gpt"):
    if model not in PROVIDERS: return None
    try:
        f = io.BytesIO(img_bytes); f.name = "in.png"
        r = await PROVIDERS[model].images.edit(
            model=IMAGE_MODEL, image=f, prompt=prompt, size="1024x1024")
        return base64.b64decode(r.data[0].b64_json)
    except Exception as e:
        log.warning(f"img edit: {e}"); return None

async def stt(ogg):
    if "gpt" not in PROVIDERS: return ""
    try:
        f = io.BytesIO(ogg); f.name = "v.ogg"
        r = await PROVIDERS["gpt"].audio.transcriptions.create(
            model="whisper-1", file=f, response_format="text")
        return r if isinstance(r, str) else r.text
    except Exception as e:
        log.warning(f"stt: {e}"); return ""

async def tts(text):
    if "gpt" not in PROVIDERS: return None
    try:
        r = await PROVIDERS["gpt"].audio.speech.create(
            model="tts-1", voice="alloy", input=text[:4000])
        return r.read()
    except Exception as e:
        log.warning(f"tts: {e}"); return None

def reset_history(uid): _history.pop(uid, None)

# ══════════════════════════════════════════════════════════════════
#  REFERRAL
# ══════════════════════════════════════════════════════════════════
def gen_ref_code(uid):
    with db() as c:
        r = c.execute("SELECT ref_code FROM users WHERE user_id=?", (uid,)).fetchone()
        if r and r["ref_code"]: return r["ref_code"]
        code = "AI" + str(uid)[-6:] + "".join(random.choices(string.ascii_uppercase, k=2))
        c.execute("UPDATE users SET ref_code=? WHERE user_id=?", (code, uid)); c.commit()
        return code

def apply_ref(new_uid, code):
    with db() as c:
