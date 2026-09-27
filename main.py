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