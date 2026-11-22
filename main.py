import sqlite3
import logging
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = "9000277306:AAFie-0GAlnXfVZYYZQz-ZDXOaZihQKo2mA"
ADMIN_ID = 8767100769
GMAIL_REWARD = 8
REF_REWARD = 2
MIN_WITHDRAW = 50
DB_NAME = "cashmail.db"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

def init():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, referred_by INTEGER DEFAULT NULL, ref_rewarded INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, account_data TEXT, status TEXT DEFAULT 'pending')")
    c.execute("CREATE TABLE IF NOT EXISTS withdrawals (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, wallet TEXT, status TEXT DEFAULT 'pending')")
    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect(DB_NAME)

def register_user(user_id, referred_by=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not c.fetchone():
        if referred_by and referred_by != user_id:
            c.execute("SELECT user_id FROM users WHERE user_id = ?", (referred_by,))
            if not c.fetchone():
                referred_by = None
        else:
            referred_by = None
        c.execute("INSERT INTO users (user_id, referred_by) VALUES (?, ?)", (user_id, referred_by))
        conn.commit()
    conn.close()

def main_menu():
    kb = [
        ["الربح من الجيميلات 📧", "الاحالة 👥"],
        ["الاموال المعلقة ⏳", "المحفظة 💳"]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["wait_gmail"] = False
    context.user_data["wait_wallet"] = False
    ref = None
    if context.args and context.args[0].startswith("ref_"):
        try:
            ref = int(context.args[0].split("_")[1])
        except Exception:
            ref = None
    register_user(user.id, ref)
    msg = f"أهلاً بك يا {user.first_name} في بوت CashMail 💰\n\nاكسب فلوس من تسليم حسابات Gmail جديدة أو من دعوة أصدقائك.\nاختر من القائمة بالأسفل 👇"
    await update.message.reply_text(msg, reply_markup=main_menu())

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_id = update.effective_user.id
    text = update.message.text.strip()
    register_user(user_id)

    if "الربح من الجيميلات" in text:
        context.user_data["wait_gmail"] = False
        context.user_data["wait_wallet"] = False
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("تسليم حساب Gmail ➕", callback_data="submit_gmail")]])
        msg = f"📧 قسم الربح من الجيميلات\n\n• سعر الحساب المقبول: {GMAIL_REWARD} جنيه.\n• يجب أن يكون الحساب جديداً وغير مرتبط برقم هاتف.\n\nاضغط على الزر بالأسفل لتسليم حساب 👇"
        await update.message.reply_text(msg, reply_markup=kb)
        return

    elif "الاحالة" in text:
        context.user_data["wait_gmail"] = False
        context.user_data["wait_wallet"] = False
        bot_user = context.bot.username
        ref_link = f"https://t.me/{bot_user}?start=ref_{user_id}"
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
        total_refs = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE referred_by = ? AND ref_rewarded = 1", (user_id,))
        succ_refs = c.fetchone()[0]
        conn.close()
        msg = f"👥 نظام الإحالة\n\n🔗 رابط الإحالة الخاص بك:\n{ref_link}\n\n👤 عدد اللي دخلوا من رابطك: {total_refs}\n✅ الإحالات الناجحة: {succ_refs}\n\n💡 شرح: كل واحد يدخل من رابطك ويتقبل أول حساب ليه تاخد {REF_REWARD} جنيه مكافأة!"
        await update.message.reply_text(msg)
        return

    elif "الاموال المعلقة" in text:
        context.user_data["wait_gmail"] = False
        context.user_data["wait_wallet"] = False
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM tasks WHERE user_id = ? AND status = 'pending'", (user_id,))
        p_tasks = c.fetchall()
        c.execute("SELECT id, amount FROM withdrawals WHERE user_id = ? AND status = 'pending'", (user_id,))
        p_with = c.fetchall()
        conn.close()
        if not p_tasks and not p_with:
            await update.message.reply_text("مفيش اموال معلقة عندك دلوقتي ✅")
            return
        total = 0
        msg = "⏳ تفاصيل الأموال المعلقة:\n\n"
        if p_tasks:
            msg += "📧 حسابات Gmail قيد المراجعة:\n"
            for t in p_tasks:
                msg += f"- طلب رقم #{t[0]} ⬅️ القيمة: {GMAIL_REWARD} جنيه\n"
                total += GMAIL_REWARD
            msg += "\n"
        if p_with:
            msg += "💸 طلبات سحب قيد التنفيذ:\n"
            for w in p_with:
                msg += f"- سحب رقم #{w[0]} ⬅️ المبلغ: {w[1]} جنيه\n"
                total += w[1]
            msg += "\n"
        msg += f"💰 إجمالي المبلغ المعلق: {total} جنيه"
        await update.message.reply_text(msg)
        return

    elif "المحفظة" in text:
        context.user_data["wait_gmail"] = False
        context.user_data["wait_wallet"] = False
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        bal = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND status = 'accepted'", (user_id,))
        acc = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND status = 'rejected'", (user_id,))
        rej = c.fetchone()[0]
        conn.close()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("سحب الرصيد 💸", callback_data="withdraw_req")]])
        msg = f"💳 محفظتك الشخصية\n\n💵 الرصيد الحالي: {bal} جنيه\n✅ المهام المقبولة: {acc}\n❌ المهام المرفوضة: {rej}\n📉 الحد الأدنى للسحب: {MIN_WITHDRAW} جنيه"
        await update.message.reply_text(msg, reply_markup=kb)
        return

    if context.user_data.get("wait_gmail"):
        if "@gmail.com" not in text.lower():
            await update.message.reply_text("⚠️ صيغة غير صحيحة! لازم الرسالة تحتوي على @gmail.com\nابعت الحساب بالشكل ده:\ntest@gmail.com\n12345678")
            return
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO tasks (user_id, account_data, status) VALUES (?, ?, 'pending')", (user_id, text))
        task_id = c.lastrowid
        conn.commit()
        conn.close()
        context.user_data["wait_gmail"] = False
        await update.message.reply_text(f"✅ تم استلام الحساب بنجاح (رقم الطلب #{task_id}).\nسيتم مراجعته من الإدارة قريباً.")
        adm_kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"قبول + {GMAIL_REWARD} جنيه ✅", callback_data=f"acc_task_{task_id}"), InlineKeyboardButton("رفض ❌", callback_data=f"rej_task_{task_id}")]])
        adm_msg = f"📩 طلب تسليم Gmail جديد\n\n🆔 رقم الطلب: #{task_id}\n👤 ID المستخدم: {user_id}\n📝 الحساب:\n{text}"
        await context.bot.send_message(chat_id=ADMIN_ID, text=adm_msg, reply_markup=adm_kb)
        return

    if context.user_data.get("wait_wallet"):
        if not (text.isdigit() and len(text) == 11):
            await update.message.reply_text("⚠️ رقم غير صحيح! لازم تبعت رقم فودافون كاش مكون من 11 رقم وأرقام إنجليزية فقط.")
            return
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        bal = c.fetchone()[0]
        if bal < MIN_WITHDRAW:
            context.user_data["wait_wallet"] = False
            conn.close()
            await update.message.reply_text(f"❌ رصيدك الحالي ({bal} جنيه) أقل من الحد الأدنى للسحب ({MIN_WITHDRAW} جنيه).")
            return
        c.execute("INSERT INTO withdrawals (user_id, amount, wallet, status) VALUES (?, ?, ?, 'pending')", (user_id, bal, text))
        w_id = c.lastrowid
        conn.commit()
        conn.close()
        context.user_data["wait_wallet"] = False
        await update.message.reply_text(f"✅ تم تسجيل طلب السحب رقم #{w_id} بقيمة {bal} جنيه بنجاح!\n📱 رقم المحفظة: {text}")
        adm_kb = InlineKeyboardMarkup([[InlineKeyboardButton("تم الدفع ✅", callback_data=f"pay_w_{w_id}"), InlineKeyboardButton("رفض ❌", callback_data=f"rej_w_{w_id}")]])
        adm_msg = f"💸 طلب سحب رصيد جديد\n\n🆔 رقم السحب: #{w_id}\n👤 ID المستخدم: {user_id}\n💰 المبلغ: {bal} جنيه\n📱 الرقم: {text}"
        await context.bot.send_message(chat_id=ADMIN_ID, text=adm_msg, reply_markup=adm_kb)
        return

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "submit_gmail":
        context.user_data["wait_gmail"] = True
        context.user_data["wait_wallet"] = False
        await query.message.reply_text("📧 ابعت حساب الـ Gmail الآن بالشكل ده:\n\ntest@gmail.com\n12345678")

    elif data == "withdraw_req":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        bal = c.fetchone()[0]
        c.execute("SELECT id FROM withdrawals WHERE user_id = ? AND status = 'pending'", (user_id,))
        has_p = c.fetchone()
        conn.close()
        if has_p:
            await query.message.reply_text("⏳ لديك طلب سحب معلق بالفعل، يرجى انتظار تنفيذه أولاً.")
            return
        if bal < MIN_WITHDRAW:
            await query.message.reply_text(f"❌ رصيدك الحالي {bal} جنيه، لازم تكمل {MIN_WITHDRAW} جنيه عشان تقدر تسحب.")
        else:
            context.user_data["wait_wallet"] = True
            context.user_data["wait_gmail"] = False
            await query.message.reply_text(f"💰 المبلغ المتاح للسحب: {bal} جنيه\n\n📱 ابعت رقم فودافون كاش المكون من 11 رقم الآن:")

    elif data.startswith("acc_task_") or data.startswith("rej_task_"):
        if user_id != ADMIN_ID:
            return
        parts = data.split("_")
        action = parts[0]
        task_id = int(parts[2])
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, status FROM tasks WHERE id = ?", (task_id,))
        task = c.fetchone()
        if not task or task[1] != "pending":
            conn.close()
            await query.edit_message_text(query.message.text + "\n\n⚠️ تم التعامل مع هذا الطلب مسبقاً.")
            return
        target_id = task[0]
        if action == "acc":
            c.execute("UPDATE tasks SET status = 'accepted' WHERE id = ?", (task_id,))
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (GMAIL_REWARD, target_id))
            c.execute("SELECT balance, referred_by, ref_rewarded FROM users WHERE user_id = ?", (target_id,))
            u_data = c.fetchone()
            new_bal, ref_id, ref_rew = u_data[0], u_data[1], u_data[2]
            bonus = False
            if ref_id and ref_rew == 0:
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REF_REWARD, ref_id))
                c.execute("UPDATE users SET ref_rewarded = 1 WHERE user_id = ?", (target_id,))
                bonus = True
            conn.commit()
            conn.close()
            await query.edit_message_text(query.message.text + f"\n\n✅ تم القبول وإضافة {GMAIL_REWARD} جنيه.")
            try:
                await context.bot.send_message(chat_id=target_id, text=f"🎉 مبروك! تم قبول حسابك (طلب #{task_id}) وإضافة {GMAIL_REWARD} جنيه.\n💵 رصيدك الحالي: {new_bal} جنيه")
            except Exception:
                pass
            if bonus:
                try:
                    await context.bot.send_message(chat_id=ref_id, text=f"🎁 مكافأة إحالة جديدة!\nتم قبول أول حساب لصديقك المدعو من رابطك، وتمت إضافة {REF_REWARD} جنيه لرصيدك!")
                except Exception:
                    pass
        elif action == "rej":
            c.execute("UPDATE tasks SET status = 'rejected' WHERE id = ?", (task_id,))
            conn.commit()
            conn.close()
            await query.edit_message_text(query.message.text + "\n\n❌ تم رفض الحساب.")
            try:
                await context.bot.send_message(chat_id=target_id, text=f"❌ للأسف تم رفض حساب الجيميل الخاص بك (طلب #{task_id}).")
            except Exception:
                pass

    elif data.startswith("pay_w_") or data.startswith("rej_w_"):
        if user_id != ADMIN_ID:
            return
        parts = data.split("_")
        action = parts[0]
        w_id = int(parts[2])
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, amount, wallet, status FROM withdrawals WHERE id = ?", (w_id,))
        w_data = c.fetchone()
        if not w_data or w_data[3] != "pending":
            conn.close()
            await query.edit_message_text(query.message.text + "\n\n⚠️ تم التعامل مع طلب السحب هذا مسبقاً.")
            return
        target_id, amount, wallet = w_data[0], w_data[1], w_data[2]
        if action == "pay":
            c.execute("UPDATE withdrawals SET status = 'paid' WHERE id = ?", (w_id,))
            c.execute("UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id = ?", (amount, target_id))
            conn.commit()
            conn.close()
            await query.edit_message_text(query.message.text + "\n\n✅ تم تأكيد الدفع وخصم الرصيد.")
            try:
                await context.bot.send_message(chat_id=target_id, text=f"💸 تم الدفع بنجاح!\nتم تحويل مبلغ {amount} جنيه إلى محفظتك ({wallet}).")
            except Exception:
                pass
        elif action == "rej":
            c.execute("UPDATE withdrawals SET status = 'rejected' WHERE id = ?", (w_id,))
            conn.commit()
            conn.close()
            await query.edit_message_text(query.message.text + "\n\n❌ تم رفض طلب السحب.")
            try:
                await context.bot.send_message(chat_id=target_id, text=f"❌ تم رفض طلب السحب رقم #{w_id} بقيمة {amount} جنيه.\nرصيدك لا يزال محفوظاً في محفظتك.")
            except Exception:
                pass

def main():
    init()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
