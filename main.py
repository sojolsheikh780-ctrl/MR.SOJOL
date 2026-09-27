        r = c.execute("SELECT user_id FROM users WHERE ref_code=?", (code.upper(),)).fetchone()
        if not r: return False, 0
        ref_uid = r["user_id"]
        if ref_uid == new_uid: return False, 0
        if c.execute("SELECT 1 FROM referrals WHERE referred=?", (new_uid,)).fetchone():
            return False, 0
        c.execute("UPDATE users SET referred_by=? WHERE user_id=?", (ref_uid, new_uid))
        c.execute("INSERT INTO referrals (referrer,referred,joined_at) VALUES (?,?,?)",
                  (ref_uid, new_uid, now()))
        c.execute("UPDATE users SET ref_count=ref_count+1 WHERE user_id=?", (ref_uid,))
        c.commit()
    add_credits(ref_uid, REF_SIGNUP_BONUS)
    add_credits(new_uid, NEW_USER_BONUS)
    log_event("referral", ref_uid, f"Referred {new_uid}")
    return True, ref_uid

def reward_purchase(uid):
    with db() as c:
        r = c.execute("SELECT referrer,rewarded FROM referrals WHERE referred=?", (uid,)).fetchone()
        if not r or r["rewarded"]: return None
        ref_uid = r["referrer"]
        c.execute("UPDATE referrals SET rewarded=1 WHERE referred=?", (uid,)); c.commit()
    add_credits(ref_uid, REF_PURCHASE_BONUS)
    log_event("referral", ref_uid, f"Purchase bonus from {uid}")
    return ref_uid

def ref_stats(uid):
    with db() as c:
        r = c.execute("SELECT COUNT(*) total, COALESCE(SUM(rewarded),0) purchased FROM referrals WHERE referrer=?",
                      (uid,)).fetchone()
        return {"total": r["total"] or 0, "purchased": r["purchased"] or 0}

def ref_leaderboard(limit=10):
    with db() as c:
        return c.execute("""SELECT u.user_id, u.username, u.first_name, u.ref_count,
                                   COUNT(r.id) AS rewarded
                            FROM users u
                            LEFT JOIN referrals r ON r.referrer = u.user_id AND r.rewarded=1
                            WHERE u.ref_count > 0
                            GROUP BY u.user_id
                            ORDER BY u.ref_count DESC LIMIT ?""", (limit,)).fetchall()

def group_summary():
    with db() as c:
        r = c.execute("SELECT COUNT(DISTINCT chat_id) g, SUM(calls) t FROM group_stats").fetchone()
        return {"groups": r["g"] or 0, "calls": r["t"] or 0}

def top_groups(limit=20):
    with db() as c:
        return c.execute("""SELECT chat_id, chat_title, SUM(calls) AS calls,
                                   COUNT(DISTINCT user_id) AS users
                            FROM group_stats GROUP BY chat_id
                            ORDER BY calls DESC LIMIT ?""", (limit,)).fetchall()

# ══════════════════════════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════════════════════════
def user_lang(uid):
    u = get_user(uid)
    return u["lang"] if u and u["lang"] else "bn"

def main_menu(uid):
    l = user_lang(uid)
    return M([
        [B(t("ai_chat",l),cb_data="ai_chat"), B(t("ai_img",l),cb_data="ai_img")],
        [B(t("ai_voice",l),cb_data="ai_voice"), B(t("model",l),cb_data="pick_model")],
        [B(t("buy",l),cb_data="buy"), B(t("account",l),cb_data="account")],
        [B(t("referral",l),cb_data="referral"), B(t("reset",l),cb_data="reset")],
        [B("🌐 Language / ভাষা",cb_data="lang"), B(t("support",l),cb_data="support")],
    ])

def buy_menu():
    rows = [[B(f"৳{p['bdt']} → {p['credits']} credits", cb_data=f"pkg_{k}")]
            for k, p in PACKAGES.items()]
    rows.append([B("⬅️ Back", cb_data="back")])
    return M(rows)

def pkg_menu(k):
    p = PACKAGES[k]
    return M([
        [B(f"⭐ {p['bdt']*STARS_MULT} Stars — Instant", cb_data=f"star_{k}")],
        [B(f"📱 bKash/Nagad ৳{p['bdt']} — Manual", cb_data=f"manual_{k}")],
        [B("⬅️ Back", cb_data="buy")]])

def model_menu():
    rows = [[B(MODEL_NAMES[m], cb_data=f"model_{m}")] for m in MODEL_NAMES]
    rows.append([B("⬅️ Back", cb_data="back")])
    return M(rows)

def back(): return M([[B("⬅️ Back", cb_data="back")]])

def lang_menu():
    return M([
        [B("🇧🇩 বাংলা", cb_data="setlang_bn"), B("🇬🇧 English", cb_data="setlang_en")],
        [B("⬅️ Back", cb_data="back")]])

def admin_menu():
    return M([
        [B("📊 Stats",cb_data="ad_stats"), B("💳 Payments",cb_data="ad_pay")],
        [B("👥 Users",cb_data="ad_users"), B("🏆 Referrals",cb_data="ad_ref")],
        [B("👥 Group Analytics",cb_data="ad_grp"), B("📢 Broadcast",cb_data="ad_bc")],
        [B("📜 Logs",cb_data="ad_log"), B("⬅️ Back",cb_data="back")]])

# ══════════════════════════════════════════════════════════════════
#  STATE
# ══════════════════════════════════════════════════════════════════
STATE = {}

# ══════════════════════════════════════════════════════════════════
#  HANDLERS — Commands
# ══════════════════════════════════════════════════════════════════
async def cmd_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    us = u.effective_user
    upsert_user(us.id, us.username, us.first_name)
    args = c.args or []
    if args and args[0].startswith("ref_"):
        ok, ref_uid = apply_ref(us.id, args[0][4:])
        if ok:
            try: await c.bot.send_message(ref_uid,
                f"🎉 নতুন referral! +{REF_SIGNUP_BONUS} credits")
            except: pass
    STATE.pop(us.id, None)
    await u.message.reply_text(t("welcome", user_lang(us.id)),
                               reply_markup=main_menu(us.id), parse_mode=ParseMode.HTML)

async def cmd_admin(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not is_admin(u.effective_user.id):
        await u.message.reply_text("⛔"); return
    await u.message.reply_text("👑 Admin Panel", reply_markup=admin_menu())

async def cmd_lang(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("🌐 Choose language:", reply_markup=lang_menu())

async def cmd_user(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not is_admin(u.effective_user.id): return
    try: uid = int(c.args[0])
    except: return
    usr = get_user(uid)
    if not usr: await u.message.reply_text("Not found."); return
    await u.message.reply_text(
        f"👤 <code>{uid}</code>\n@{usr['username'] or '-'}\n💎 {usr['credits']}\n"
        f"🚫 {'Yes' if usr['is_blocked'] else 'No'}\n"
        f"🎁 Trial: {usr['trial_text']}t/{usr['trial_img']}i\n"
        f"👥 Refs: {usr['ref_count']}", parse_mode=ParseMode.HTML)

async def cmd_block(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not is_admin(u.effective_user.id): return
    try: uid = int(c.args[0])
    except: return
    with db() as cc:
        cc.execute("UPDATE users SET is_blocked=1 WHERE user_id=?", (uid,)); cc.commit()
    await u.message.reply_text(f"🚫 Blocked {uid}")

async def cmd_unblock(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not  is_admin(u.effective_user.id): return
    try: uid = int(c.args[0])
    except: return
    with db() as cc:
        cc.execute("UPDATE users SET is_blocked=0 WHERE user_id=?", (uid,)); cc.commit()
    await u.message.reply_text(f"✅ Unblocked {uid}")

async def cmd_dm(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not is_admin(u.effective_user.id): return
    try: uid = int(c.args[0]); msg = " ".join(c.args[1:])
    except: return
    try:
        await c.bot.send_message(uid, f"📩 <b>Admin:</b>\n{msg}", parse_mode=ParseMode.HTML)
        await u.message.reply_text("✅ Sent.")
    except Exception as e: await u.message.reply_text(f"❌ {e}")

async def cmd_stats(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not is_admin(u.effective_user.id): return
    with db() as cc:
        t_ = cc.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        a_ = cc.execute("SELECT COUNT(*) n FROM users WHERE credits>0").fetchone()["n"]
        r_ = cc.execute("SELECT COALESCE(SUM(amount),0) s FROM payments WHERE status='success'").fetchone()["s"]
        p_ = cc.execute("SELECT COUNT(*) n FROM payments WHERE status='pending'").fetchone()["n"]
    g = group_summary()
    await u.message.reply_text(
        f"📊 <b>Stats</b>\n👥 Users: {t_}\n💎 Paying: {a_}\n"
        f"💰 Revenue: ৳{r_}\n⏳ Pending: {p_}\n"
        f"👥 Groups: {g['groups']}\n🔊 Calls: {g['calls']}",
        parse_mode=ParseMode.HTML)                                                    # ══════════════════════════════════════════════════════════════════
#  CALLBACK ROUTER
# ══════════════════════════════════════════════════════════════════
async def cb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query; uid = u.effective_user.id; d = q.data
    await q.answer()
    usr = get_user(uid)
    l = user_lang(uid)

    if d == "back":
        STATE.pop(uid, None)
        await q.edit_message_text(t("welcome", l), reply_markup=main_menu(uid),
                                  parse_mode=ParseMode.HTML); return

    if d == "lang":
        await q.edit_message_text("🌐 Choose language:", reply_markup=lang_menu()); return
    if d.startswith("setlang_"):
        lang = d.split("_")[1]"""
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
        lang = d.split("_")[1]
        set_lang_db(uid, lang)
        await q.edit_message_text(t("lang_changed", lang), reply_markup=main_menu(uid)); return

    if d == "ai_chat":  STATE[uid]="chat";  await q.edit_message_text(t("ask_question",l), reply_markup=back()); return
    if d == "ai_voice": STATE[uid]="voice"; await q.edit_message_text(t("send_voice",l), reply_markup=back()); return
    if d == "ai_img":   STATE[uid]="image"; await q.edit_message_text(t("send_image",l), reply_markup=back()); return
    if d == "pick_model": await q.edit_message_text(t("pick_model",l), reply_markup=model_menu()); return

    if d.startswith("model_"):
        m = d.split("_")[1]
        with db() as cc:
            cc.execute("UPDATE users SET preferred_model=? WHERE user_id=?", (m, uid)); cc.commit()
        await q.edit_message_text(f"✅ {MODEL_NAMES[m]}", reply_markup=back()); return

    if d == "buy": await q.edit_message_text("💰 Packages:", reply_markup=buy_menu()); return
    if d.startswith("pkg_"):
        k = d[4:]
        await q.edit_message_text(
            f"📦 {PACKAGES[k]['credits']} credits\n💰 ৳{PACKAGES[k]['bdt']}",
            reply_markup=pkg_menu(k)); return
    if d.startswith("star_"):
        k = d[5:]; p = PACKAGES[k]
        await c.bot.send_invoice(chat_id=u.effective_chat.id,
            title=f"{p['credits']} Credits", description=f"৳{p['bdt']}",
            payload=f"credits:{k}", provider_token="", currency="XTR",
            prices=[LabeledPrice(label=f"{p['credits']} credits", amount=p['bdt']*STARS_MULT)])
        return
    if d.startswith("manual_"):
        k = d[7:]; p = PACKAGES[k]
        STATE[uid] = f"txid:{k}"
        await q.edit_message_text(
            f"📱 Send Money ৳{p['bdt']} → <code>{PAYMENT_NUMBER}</code>\n"
            f"⚠️ No Agent\n\nSend TxID 👇",
            reply_markup=back(), parse_mode=ParseMode.HTML); return

    if d == "referral":
        code = gen_ref_code(uid)
        bot_un = (await c.bot.get_me()).username
        link = f"https://t.me/{bot_un}?start=ref_{code}"
        s = ref_stats(uid)
        await q.edit_message_text(
            f"🎁 <b>Refer & Earn</b>\n\n🔗 <code>{link}</code>\n\n"
            f"👥 Referred: {s['total']}\n💎 Bonuses: {s['purchased']}\n\n"
            f"💰 Friend join → +{REF_SIGNUP_BONUS}\n"
            f"💰 Friend purchase → +{REF_PURCHASE_BONUS}\n"
            f"🎉 Friend পাবে +{NEW_USER_BONUS} free",
            reply_markup=back(), parse_mode=ParseMode.HTML); return
if d == "account":
        left = f"{FREE_TEXT-usr['trial_text']}t / {FREE_IMG-usr['trial_img']}i"
        vr = "ON" if usr["voice_reply"] else "OFF"
        await q.edit_message_text(
            f"👤 <b>Account</b>\n🆔 <code>{uid}</code>\n💎 Credits: {usr['credits']}\n"
            f"🧠 Model: {MODEL_NAMES.get(usr['preferred_model'],'GPT')}\n"
            f"🔊 Voice: {vr}\n🌐 Lang: {usr['lang']}\n🎁 Free left: {left}",
            reply_markup=M([
                [B(f"🔊 Voice Reply: {vr}", cb_data="tog_voice")],
                [B("⬅️ Back", cb_data="back")]]),
            parse_mode=ParseMode.HTML); return
    if d == "tog_voice":
        with db() as cc:
            cc.execute("UPDATE users SET voice_reply=1-voice_reply WHERE user_id=?", (uid,)); cc.commit()
        return await cb(u, c)

    if d == "reset": reset_history(uid); await q.edit_message_text("✅ Cleared.", reply_markup=back()); return
    if d == "support": await q.edit_message_text("📞 @YourSupport", reply_markup=back()); return

    # ── Admin ──
    if not is_admin(uid): return
    if d == "ad_stats":
        with db() as cc:
            t_ = cc.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
            a_ = cc.execute("SELECT COUNT(*) n FROM users WHERE credits>0").fetchone()["n"]
            r_ = cc.execute("SELECT COALESCE(SUM(amount),0) s FROM payments WHERE status='success'").fetchone()["s"]
            g_ = group_summary()
        await q.edit_message_text(
            f"📊 Users: {t_}\n💎 Paying: {a_}\n💰 ৳{r_}\n"
            f"👥 Groups: {g_['groups']}\n🔊 Calls: {g_['calls']}",
            reply_markup=admin_menu()); return

    if d == "ad_pay":
        with db() as cc:
            rows = cc.execute("SELECT * FROM payments WHERE status='pending' ORDER BY id DESC LIMIT 10").fetchall()
        if not rows: await q.edit_message_text("No pending.", reply_markup=admin_menu()); return
        txt = "💳 <b>Pending</b>\n"; btns=[]
        for r in rows:
            txt += f"#{r['id']} <code>{r['user_id']}</code> {r['package']} <code>{r['txid']}</code>\n"
            btns.append([B(f"✅ #{r['id']}", cb_data=f"ok_{r['id']}"), B(f"❌ #{r['id']}", cb_data=f"no_{r['id']}")])
        btns.append([B("⬅️", cb_data="back")])
        await q.edit_message_text(txt, reply_markup=M(btns), parse_mode=ParseMode.HTML); return
    if d.startswith("ok_"):
        pid = int(d.split("_")[1])
        with db() as cc:
            p = cc.execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone()
        if p:
            add_credits(p["user_id"], PACKAGES[p["package"]]["credits"])
            with db() as cc:
                cc.execute("UPDATE payments SET status='success', verified_at=? WHERE id=?", (now(), pid)); cc.commit()
            try: await c.bot.send_message(p["user_id"], f"✅ +{PACKAGES[p['package']]['credits']} credits!")
            except: pass
            ref = reward_purchase(p["user_id"])
            if ref:
                try: await c.bot.send_message(ref, f"🎉 Referral bonus! +{REF_PURCHASE_BONUS}")
                except: pass
        await q.edit_message_text(f"✅ #{pid}", reply_markup=admin_menu()); return
    if d.startswith("no_"):
        pid = int(d.split("_")[1])
        with db() as cc:
            cc.execute("UPDATE payments SET status='failed' WHERE id=?", (pid,)); cc.commit()
        await q.edit_message_text(f"❌ #{pid}", reply_markup=admin_menu()); return

    if d == "ad_users":
        with db() as cc:
            rows = cc.execute("SELECT user_id,username,credits,is_blocked FROM users ORDER BY joined_at DESC LIMIT 15").fetchall()
        txt = "👥 <b>Recent Users</b>\n"
        for r in rows:
            flag = "🚫" if r["is_blocked"] else "✅"
            txt += f"{flag} <code>{r['user_id']}</code> @{r['username'] or '-'} | 💎{r['credits']}\n"
        txt += "\nCommands: /user <id> · /block <id> · /unblock <id> · /dm <id> <msg>"
        await q.edit_message_text(txt, reply_markup=admin_menu(), parse_mode=ParseMode.HTML); return

    if d == "ad_ref":
        lb = ref_leaderboard(10)
        txt = "🏆 <b>Referral Leaderboard</b>\n\n"
        for i, r in enumerate(lb, 1):
            txt += f"{i}. <code>{r['user_id']}</code> @{r['username'] or r['first_name'] or '-'} → {r['ref_count']}\n"
        await q.edit_message_text(txt or "No referrals yet.",
                                  reply_markup=admin_menu(), parse_mode=ParseMode.HTML); return

    if d == "ad_grp":
        gs = top_groups(15)
        txt = "👥 <b>Top Groups</b>\n\n"
        for g in gs:
            txt += f"• {g['chat_title'] or g['chat_id']} — {g['calls']} calls, {g['users']} users\n"
        await q.edit_message_text(txt or "No activity.",
                                  reply_markup=admin_menu(), parse_mode=ParseMode.HTML); return

    if d == "ad_bc":
        kb = M([
            [B("✉️ Text", cb_data="bc_text")],
            [B("⬅️ Back", cb_data="back")]])
        await q.edit_message_text("📢 Send broadcast text. Next message will be sent to all.",
                                  reply_markup=kb); return
    if d.startswith("bc_"):
        STATE[uid] = f"broadcast:{d[3:]}"
        await q.edit_message_text("Send content now:", reply_markup=back()); return

    if d == "ad_log":
        with db() as cc:
            rows = cc.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 20").fetchall()
        txt = "📜 <b>Recent Logs</b>\n"