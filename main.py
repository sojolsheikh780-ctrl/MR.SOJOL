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