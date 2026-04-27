import asyncio
import logging
import sqlite3
import os
import json
from datetime import datetime
from typing import Final, Any, List, Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter, or_f
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, 
    InlineKeyboardButton, Message, CallbackQuery, BotCommand,
    InputFile, FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from groq import Groq

# ==========================================================================================
# 💎 [SEKRET KONFIGURATSIYA - RENDER/RAILWAY XAVFSIZLIGI]
# ==========================================================================================
class Config:
    # Tokenlar server muhitidan (Environment Variables) olinadi. 
    # Agar mahalliy kompyuterda bo'lsangiz, terminalda 'export BOT_TOKEN=...' qiling.
    TOKEN: Final[str] = os.getenv("BOT_TOKEN", "8787202401:AAHW_6fGTVtgsJACqnuL_O_yrgvQVmM4x1U")
    GROQ_KEY: Final[str] = os.getenv("GROQ_API_KEY", "gsk_KnPc24V6CJk29yXcIhWL1WGdyb3FYJZ0wtquZTo47xhArq8oGjnA3s")
    ADMIN_ID: Final[int] = 8588645504
    DB_NAME: Final[str] = "logos_premium_v150_ultimate.db"

# ==========================================================================================
# ✨ [PREMIUM V150 VIZUAL ASSETLAR]
# ==========================================================================================
class UI_Assets:
    D_LINE = "<b>▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬</b>"
    S_LINE = "<b>───────────────────────</b>"
    
    # Ikonkalar (Wow Effect)
    ICO_TEST_LIST = "📂 TЕSTLAR RO'YHATI"
    ICO_CHECK_TEST = "✍️ TESTNI TOPSHIRISH"
    ICO_AI_MENTOR = "🧠 AI USTOZ (UZB)"
    ICO_MY_RESULTS = "📊 NATIJALARIM"
    ICO_PROFILE = "👤 PROFILIM"
    ICO_SUPPORT = "📞 BOG'LANISH"
    ICO_ADMIN = "🛡 ADMIN PANEL"
    ICO_BACK = "⬅️ ORQAGA"
    ICO_HOME = "🏠 ASOSIY MENYU"

    @staticmethod
    def header(title: str):
        return f"{UI_Assets.D_LINE}\n✨ <b>{title}</b> ✨\n{UI_Assets.D_LINE}"

    @staticmethod
    def p_bar(perc: float):
        full = int(perc // 10)
        bar = "🌕" * full + "🌑" * (10 - full)
        return f"{bar} <b>{perc:.1f}%</b>"

# ==========================================================================================
# 🗄 [DATA ENGINE - EXPERT LEVEL SQL]
# ==========================================================================================
class Database:
    @staticmethod
    def connect():
        conn = sqlite3.connect(Config.DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def setup(cls):
        with cls.connect() as conn:
            c = conn.cursor()
            # Foydalanuvchilar jadvali
            c.execute("""CREATE TABLE IF NOT EXISTS users (
                uid INTEGER PRIMARY KEY, fullname TEXT, username TEXT, joined_at TIMESTAMP)""")
            # Testlar jadvali
            c.execute("""CREATE TABLE IF NOT EXISTS tests (
                kod TEXT PRIMARY KEY, javoblar TEXT, file_id TEXT, title TEXT, created_at TIMESTAMP)""")
            # Natijalar jadvali (Bir marta topshirishni nazorat qilish uchun)
            c.execute("""CREATE TABLE IF NOT EXISTS results (
                rid INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, kod TEXT, 
                ball INTEGER, total INTEGER, perc REAL, user_ans TEXT, mistakes TEXT, timestamp TIMESTAMP)""")
            conn.commit()

    @classmethod
    def execute(cls, query: str, params: tuple = (), fetch_all=False, fetch_one=False):
        with cls.connect() as conn:
            c = conn.cursor()
            c.execute(query, params)
            if fetch_all: return [dict(r) for r in c.fetchall()]
            if fetch_one:
                res = c.fetchone()
                return dict(res) if res else None
            conn.commit()
            return c.lastrowid

# ==========================================================================================
# 🎭 [FSM - STATE MANAGEMENT]
# ==========================================================================================
class Form(StatesGroup):
    registration = State()
    checking_test_code = State()
    answering_test = State()
    ai_asking = State()
    contacting_admin = State()
    # Admin States
    admin_replying = State()
    admin_adding_kod = State()
    admin_adding_title = State()
    admin_adding_ans = State()
    admin_adding_file = State()

# ==========================================================================================
# 📟 [DYNAMICAL KEYBOARDS]
# ==========================================================================================
class Keyboards:
    @staticmethod
    def main(uid: int):
        b = ReplyKeyboardBuilder()
        b.row(KeyboardButton(text=UI_Assets.ICO_TEST_LIST), KeyboardButton(text=UI_Assets.ICO_CHECK_TEST))
        b.row(KeyboardButton(text=UI_Assets.ICO_AI_MENTOR), KeyboardButton(text=UI_Assets.ICO_MY_RESULTS))
        b.row(KeyboardButton(text=UI_Assets.ICO_PROFILE), KeyboardButton(text=UI_Assets.ICO_SUPPORT))
        if uid == Config.ADMIN_ID:
            b.row(KeyboardButton(text=UI_Assets.ICO_ADMIN))
        b.adjust(2, 2, 2, 1)
        return b.as_markup(resize_keyboard=True)

    @staticmethod
    def admin_panel():
        b = ReplyKeyboardBuilder()
        b.row(KeyboardButton(text="➕ TEST QO'SHISH"), KeyboardButton(text="🗑 TESTNI O'CHIRISH"))
        b.row(KeyboardButton(text="📢 XABAR YUBORISH"), KeyboardButton(text="📊 BATAFSIL STATISTIKA"))
        b.row(KeyboardButton(text=UI_Assets.ICO_HOME))
        b.adjust(2, 2, 1)
        return b.as_markup(resize_keyboard=True)

    @staticmethod
    def back():
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=UI_Assets.ICO_BACK)]], resize_keyboard=True)

# ==========================================================================================
# 🏗 [INITIALIZATION]
# ==========================================================================================
logging.basicConfig(level=logging.INFO)
bot = Bot(token=Config.TOKEN)
dp = Dispatcher(storage=MemoryStorage())
groq_client = Groq(api_api_key=Config.GROQ_KEY)

# ==========================================================================================
# 🛠 [CORE LOGIC - START & REGISTRATION]
# ==========================================================================================
@dp.message(or_f(Command("start"), F.text == UI_Assets.ICO_HOME, F.text == UI_Assets.ICO_BACK))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    Database.setup()
    user = Database.execute("SELECT * FROM users WHERE uid=?", (message.from_user.id,), fetch_one=True)
    
    if not user:
        await state.set_state(Form.registration)
        welcome = (
            f"{UI_Assets.header('LOGOS ACADEMY V150')}\n\n"
            f"Assalomu alaykum! Bizning <b>Premium</b> platformaga xush kelibsiz.\n\n"
            f"⚠️ Davom etish uchun <b>ISM VA FAMILIYANGIZNI</b> yuboring:"
        )
        return await message.answer(welcome, parse_mode="HTML")

    dashboard = (
        f"{UI_Assets.header('ASOSIY BOSHQARUV')}\n\n"
        f"👤 Foydalanuvchi: <b>{user['fullname']}</b>\n"
        f"🏅 Daraja: <b>Platinum Member</b>\n"
        f"📅 Sana: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"<i>Quyidagi bo'limlardan birini tanlang:</i>"
    )
    await message.answer(dashboard, reply_markup=Keyboards.main(message.from_user.id), parse_mode="HTML")

@dp.message(Form.registration)
async def process_reg(message: Message, state: FSMContext):
    if len(message.text.split()) < 2:
        return await message.answer("❌ Iltimos, ism va familiyangizni to'liq kiriting (Masalan: Alisher Navoiy):")
    
    Database.execute("INSERT INTO users VALUES (?,?,?,?)", 
                    (message.from_user.id, message.text, message.from_user.username, datetime.now()))
    await message.answer(f"✅ Tabriklaymiz, <b>{message.text}</b>! Siz tizimdan to'liq foydalana olasiz.", 
                        parse_mode="HTML", reply_markup=Keyboards.main(message.from_user.id))
    await state.clear()

# ==========================================================================================
# 📂 [TESTLAR RO'YHATI BO'LIMI]
# ==========================================================================================
@dp.message(F.text == UI_Assets.ICO_TEST_LIST)
async def show_tests(message: Message):
    tests = Database.execute("SELECT * FROM tests ORDER BY created_at DESC", fetch_all=True)
    if not tests:
        return await message.answer("📭 Hozircha testlar mavjud emas.")
    
    text = f"{UI_Assets.header('MAVJUD TESTLAR')}\n\n"
    for t in tests:
        text += f"📙 <b>{t['title']}</b>\n└ 🔑 Kod: <code>{t['kod']}</code>\n{UI_Assets.S_LINE}\n"
    
    text += "\n💡 <i>Testni yechish uchun 'Testni topshirish' tugmasini bosing.</i>"
    await message.answer(text, parse_mode="HTML")

# ==========================================================================================
# ✍️ [TEST TOPSHIRISH - BIR MARTALIK CHEKLOV BILAN]
# ==========================================================================================
@dp.message(F.text == UI_Assets.ICO_CHECK_TEST)
async def check_init(message: Message, state: FSMContext):
    await state.set_state(Form.checking_test_code)
    await message.answer("🆔 <b>TEST KODINI KIRITING:</b>", reply_markup=Keyboards.back(), parse_mode="HTML")

@dp.message(Form.checking_test_code)
async def check_code(message: Message, state: FSMContext):
    # Bir marta topshirganligini tekshirish
    check_done = Database.execute("SELECT * FROM results WHERE uid=? AND kod=?", 
                                (message.from_user.id, message.text), fetch_one=True)
    if check_done:
        return await message.answer(f"❌ <b>Xatolik!</b>\nSiz ushbu testni ({message.text}) oldin topshirgansiz. "
                                   f"Natijangizni 'Natijalarim' bo'limidan ko'ring.", parse_mode="HTML")

    test = Database.execute("SELECT * FROM tests WHERE kod=?", (message.text,), fetch_one=True)
    if not test:
        return await message.answer("🚫 Bunday kodli test topilmadi. Qaytadan kiriting:")

    await state.update_data(active_test=test)
    await state.set_state(Form.answering_test)
    
    info = (
        f"{UI_Assets.header('TEST BOSHLANDI')}\n\n"
        f"📖 Fan: <b>{test['title']}</b>\n"
        f"🔢 Savollar: <b>{len(test['javoblar'])} ta</b>\n\n"
        f"📥 Javoblarni formatda yuboring: <code>abcd...</code>"
    )
    if test['file_id']:
        await message.answer_document(test['file_id'], caption=info, parse_mode="HTML")
    else:
        await message.answer(info, parse_mode="HTML")

@dp.message(Form.answering_test)
async def process_answers(message: Message, state: FSMContext):
    data = await state.get_data()
    test = data['active_test']
    u_ans = message.text.lower().strip()
    t_ans = test['javoblar'].lower().strip()

    if len(u_ans) != len(t_ans):
        return await message.answer(f"⚠️ Javoblar soni mos kelmadi. Testda {len(t_ans)} ta savol bor. Siz {len(u_ans)} ta yubordingiz.")

    correct, mistakes = 0, []
    for i in range(len(t_ans)):
        if u_ans[i] == t_ans[i]:
            correct += 1
        else:
            mistakes.append(f"{i+1} (To'g'ri: {t_ans[i].upper()})")

    perc = (correct / len(t_ans)) * 100
    Database.execute("""INSERT INTO results (uid, kod, ball, total, perc, user_ans, mistakes, timestamp) 
                       VALUES (?,?,?,?,?,?,?,?)""", 
                    (message.from_user.id, test['kod'], correct, len(t_ans), perc, u_ans, ", ".join(mistakes), datetime.now()))

    res_msg = (
        f"{UI_Assets.header('TEST YAKUNLANDI')}\n\n"
        f"👤 Foydalanuvchi: {message.from_user.full_name}\n"
        f"✅ To'g'ri: <b>{correct}</b>\n"
        f"❌ Xato: <b>{len(t_ans)-correct}</b>\n"
        f"📊 Natija: {UI_Assets.p_bar(perc)}\n\n"
        f"<i>Batafsil ma'lumot 'Natijalarim' bo'limiga saqlandi.</i>"
    )
    await message.answer(res_msg, reply_markup=Keyboards.main(message.from_user.id), parse_mode="HTML")
    await state.clear()

# ==========================================================================================
# 🧠 [AI USTOZ & AI TAHLIL]
# ==========================================================================================
@dp.message(F.text == UI_Assets.ICO_AI_MENTOR)
async def ai_mentor_start(message: Message, state: FSMContext):
    await state.set_state(Form.ai_asking)
    await message.answer("🤖 <b>AI USTOZ ONLINE:</b>\nTushunmagan savolingizni matn, rasm yoki audio shaklida yuboring (Hozircha matnli tahlil expert darajada):", 
                        reply_markup=Keyboards.back(), parse_mode="HTML")

@dp.message(Form.ai_asking)
async def ai_handle(message: Message):
    if message.text == UI_Assets.ICO_BACK: return
    
    wait = await message.answer("💎 <i>AI mulohaza yuritmoqda...</i>")
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Siz professional o'qituvchisiz. O'quvchining savollariga tushunarli, aniq va faqat o'zbek tilida javob bering."},
                {"role": "user", "content": message.text}
            ],
            model="llama-3.3-70b-versatile",
        )
        response = chat_completion.choices[0].message.content
        await wait.edit_text(f"🎓 <b>AI Ustoz Javobi:</b>\n\n{response}\n\n{UI_Assets.S_LINE}", parse_mode="HTML")
    except Exception as e:
        await wait.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")

# AI TAHLIL TUGMASI UCHUN CALLBACK
@dp.callback_query(F.data.startswith("ai_analyze_"))
async def ai_analyze_results(call: CallbackQuery):
    rid = call.data.split("_")[2]
    res = Database.execute("SELECT * FROM results WHERE rid=?", (rid,), fetch_one=True)
    
    await call.message.answer("🔍 <i>AI barcha xatolaringizni tahlil qilib yechim tayyorlamoqda...</i>")
    
    prompt = f"O'quvchi test ishladi. Natija: {res['ball']}/{res['total']}. Xatolar ro'yxati: {res['mistakes']}. Iltimos, ushbu o'quvchiga motivatsiya beruvchi va xatolari ustida ishlash uchun qisqa maslahat ber."
    
    try:
        chat = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile"
        )
        await call.message.answer(f"📈 <b>AI TAHLILI:</b>\n\n{chat.choices[0].message.content}", parse_mode="HTML")
    except:
        await call.message.answer("⚠️ Hozirda tahlil qilish imkonsiz.")
    await call.answer()

# ==========================================================================================
# 📊 [NATIJALARIM & PROFIL]
# ==========================================================================================
@dp.message(F.text == UI_Assets.ICO_MY_RESULTS)
async def my_results(message: Message):
    res = Database.execute("SELECT * FROM results WHERE uid=? ORDER BY timestamp DESC", 
                         (message.from_user.id,), fetch_all=True)
    if not res:
        return await message.answer("🥺 Siz hali birorta test topshirmadingiz.")

    await message.answer(f"{UI_Assets.header('MENING NATIJALARIM')}")
    for r in res:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🧠 AI Tahlil", callback_data=f"ai_analyze_{r['rid']}"))
        
        info = (
            f"📅 Sana: {r['timestamp'][:16]}\n"
            f"🔑 Test ID: {r['kod']}\n"
            f"✅ Ball: {r['ball']}/{r['total']}\n"
            f"📈 Foiz: {r['perc']:.1f}%\n"
            f"❌ Xatolar: <code>{r['mistakes'] if r['mistakes'] else 'Yoq'}</code>"
        )
        await message.answer(info, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.message(F.text == UI_Assets.ICO_PROFILE)
async def show_profile(message: Message):
    u = Database.execute("SELECT * FROM users WHERE uid=?", (message.from_user.id,), fetch_one=True)
    stats = Database.execute("SELECT COUNT(*) as count, AVG(perc) as avg FROM results WHERE uid=?", 
                           (message.from_user.id,), fetch_one=True)
    
    prof = (
        f"{UI_Assets.header('SHAXSIY KABINET')}\n\n"
        f"👤 Ism: <b>{u['fullname']}</b>\n"
        f"🆔 ID: <code>{u['uid']}</code>\n"
        f"📝 Ishlangan testlar: <b>{stats['count']} ta</b>\n"
        f"📈 O'rtacha samaradorlik: <b>{stats['avg'] or 0:.1f}%</b>\n\n"
        f"✨ <i>Maqomingiz: Premium User</i>"
    )
    await message.answer(prof, parse_mode="HTML")

# ==========================================================================================
# 📞 [BOG'LANISH - ADMIN BILAN ALOQA]
# ==========================================================================================
@dp.message(F.text == UI_Assets.ICO_SUPPORT)
async def support_init(message: Message, state: FSMContext):
    await state.set_state(Form.contacting_admin)
    await message.answer("✍️ Adminga o'z xabaringizni yoki taklifingizni yuboring:", reply_markup=Keyboards.back())

@dp.message(Form.contacting_admin)
async def support_send(message: Message, state: FSMContext):
    if message.text == UI_Assets.ICO_BACK: return
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✍️ Javob berish", callback_data=f"adm_rep_{message.from_user.id}"))
    
    await bot.send_message(
        Config.ADMIN_ID,
        f"📩 <b>YANGI MUROJAAT</b>\n\nKimdan: {message.from_user.full_name}\nID: {message.from_user.id}\nXabar: {message.text}",
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )
    await message.answer("✅ Xabaringiz yuborildi. Admin tez orada javob beradi.", reply_markup=Keyboards.main(message.from_user.id))
    await state.clear()

# ==========================================================================================
# 🛡 [ADMIN PANEL - ADVANCED CONTROL]
# ==========================================================================================
@dp.message(F.text == UI_Assets.ICO_ADMIN)
async def admin_main(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    await message.answer("🛠 <b>ADMINISTRATOR BOSHQARUVI:</b>", reply_markup=Keyboards.admin_panel(), parse_mode="HTML")

# TEST QO'SHISH LOGIKASI
@dp.message(F.text == "➕ TEST QO'SHISH")
async def adm_add_1(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID: return
    await state.set_state(Form.admin_adding_kod)
    await message.answer("1️⃣ Test uchun <b>KOD</b> kiriting (raqamli):", reply_markup=Keyboards.back(), parse_mode="HTML")

@dp.message(Form.admin_adding_kod)
async def adm_add_2(message: Message, state: FSMContext):
    await state.update_data(k=message.text)
    await state.set_state(Form.admin_adding_title)
    await message.answer("2️⃣ Test <b>SARLAVHASI</b> (Fan nomi):")

@dp.message(Form.admin_adding_title)
async def adm_add_3(message: Message, state: FSMContext):
    await state.update_data(t=message.text)
    await state.set_state(Form.admin_adding_ans)
    await message.answer("3️⃣ <b>TO'G'RI JAVOBLARNI</b> yuboring (Masalan: abcd...):")

@dp.message(Form.admin_adding_ans)
async def adm_add_4(message: Message, state: FSMContext):
    await state.update_data(a=message.text.lower())
    await state.set_state(Form.admin_adding_file)
    await message.answer("4️⃣ Test <b>FAYLINI</b> (PDF/DOC) yuboring yoki /skip yuboring:")

@dp.message(Form.admin_adding_file)
async def adm_add_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    fid = message.document.file_id if message.document else None
    
    Database.execute("INSERT INTO tests VALUES (?,?,?,?,?)", 
                    (data['k'], data['a'], fid, data['t'], datetime.now()))
    
    await message.answer("✅ <b>Test muvaffaqiyatli saqlandi va barcha foydalanuvchilarga ko'rinadi!</b>", 
                        reply_markup=Keyboards.admin_panel(), parse_mode="HTML")
    await state.clear()

# TESTNI O'CHIRISH
@dp.message(F.text == "🗑 TESTNI O'CHIRISH")
async def adm_del_list(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    tests = Database.execute("SELECT * FROM tests", fetch_all=True)
    kb = InlineKeyboardBuilder()
    for t in tests:
        kb.row(InlineKeyboardButton(text=f"❌ {t['kod']} | {t['title']}", callback_data=f"del_test_{t['kod']}"))
    await message.answer("O'chirish uchun testni tanlang:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("del_test_"))
async def confirm_del(call: CallbackQuery):
    kod = call.data.split("_")[2]
    Database.execute("DELETE FROM tests WHERE kod=?", (kod,))
    Database.execute("DELETE FROM results WHERE kod=?", (kod,))
    await call.message.edit_text(f"✅ Kod {kod} bo'lgan test va uning natijalari o'chirildi.")

# STATISTIKA
@dp.message(F.text == "📊 BATAFSIL STATISTIKA")
async def adm_stats(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    tests = Database.execute("SELECT * FROM tests", fetch_all=True)
    kb = InlineKeyboardBuilder()
    for t in tests:
        kb.row(InlineKeyboardButton(text=f"📈 {t['title']}", callback_data=f"view_stat_{t['kod']}"))
    await message.answer("Statistikasini ko'rish uchun testni tanlang:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("view_stat_"))
async def view_stat(call: CallbackQuery):
    kod = call.data.split("_")[2]
    results = Database.execute("""SELECT u.fullname, r.ball, r.total FROM results r 
                                JOIN users u ON r.uid = u.uid WHERE r.kod=? ORDER BY r.ball DESC""", 
                             (kod,), fetch_all=True)
    if not results:
        return await call.answer("Bu testda hech kim qatnashmagan.", show_alert=True)
    
    msg = f"📊 <b>{kod} KODLI TEST NATIJALARI:</b>\n\n"
    for i, r in enumerate(results, 1):
        msg += f"{i}. {r['fullname']} - {r['ball']}/{r['total']}\n"
    
    await call.message.answer(msg, parse_mode="HTML")

# ==========================================================================================
# 🚀 [RUNNER]
# ==========================================================================================
async def main():
    Database.setup()
    await bot.set_my_commands([
        BotCommand(command="start", description="Asosiy menyu"),
    ])
    print("💎 LOGOS PLATINUM V150 IS ONLINE...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.error("Bot to'xtatildi!")
