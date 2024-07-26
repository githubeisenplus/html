import sqlite3
from telegram import Update, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
)
from datetime import datetime, timedelta, time
import pytz
import logging
import os

# Set up SQLite connection
conn = sqlite3.connect('pharmacy_bot.db')
c = conn.cursor()

# Create tables for tasks, reports, and user roles
c.execute('''CREATE TABLE IF NOT EXISTS roles (user_id INTEGER PRIMARY KEY, role TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS tasks (task_id INTEGER PRIMARY KEY, description TEXT, assigned_to INTEGER, due_date TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS reports (report_id INTEGER PRIMARY KEY, submitted_by INTEGER, text TEXT, timestamp TEXT, photo_path TEXT)''')
conn.commit()

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Persian messages
START_MESSAGE = "به ربات مدیریت پرسنل و وظایف داروخانه خوش آمدید!"
ADMIN_PROMPT = "لطفا کد مدیر را وارد کنید:"
AUTH_SUCCESS = "شما با موفقیت احراز هویت شدید."
TASK_CREATED = "وظیفه جدید با موفقیت ایجاد شد."
TASK_ASSIGNED = "وظیفه به کاربر اختصاص یافت."
TASK_VIEW = "اینها وظایف شما هستند:"
REPORT_RECEIVED = "گزارش با موفقیت ارسال شد."
FEEDBACK_RECEIVED = "بازخورد شما با موفقیت ارسال شد."
NOT_AUTHORIZED = "شما مجاز به انجام این عملیات نیستید."
REMINDER_MESSAGE = "یادآوری وظیفه: "
TASK_COMPLETE = "وظیفه تکمیل شد."
FEEDBACK_PROMPT = "لطفا بازخورد خود را ارسال کنید."

# Function to add or update user roles in the database
def set_role(user_id, role):
    logger.info(f"Setting role for user {user_id} to {role}")
    c.execute("INSERT OR REPLACE INTO roles (user_id, role) VALUES (?, ?)", (user_id, role))
    conn.commit()
    logger.info(f"Role set for user {user_id} to {role}")

# Function to get user role from the database
def get_role(user_id):
    logger.info(f"Getting role for user {user_id}")
    c.execute("SELECT role FROM roles WHERE user_id=?", (user_id,))
    result = c.fetchone()
    role = result[0] if result else None
    logger.info(f"Role for user {user_id} is {role}")
    return role

# Function to add a new task to the database
def add_task(description, assigned_to, due_date):
    logger.info(f"Adding task: {description}, assigned to: {assigned_to}, due date: {due_date}")
    c.execute("INSERT INTO tasks (description, assigned_to, due_date) VALUES (?, ?, ?)", (description, assigned_to, due_date))
    conn.commit()
    task_id = c.lastrowid
    logger.info(f"Task added with ID {task_id}")
    return task_id

# Function to get all tasks from the database
def get_all_tasks():
    logger.info("Getting all tasks")
    c.execute("SELECT * FROM tasks")
    tasks = c.fetchall()
    logger.info(f"Retrieved {len(tasks)} tasks")
    return tasks

# Function to get tasks assigned to a specific user
def get_tasks_by_user(user_id):
    logger.info(f"Getting tasks for user {user_id}")
    c.execute("SELECT * FROM tasks WHERE assigned_to=?", (user_id,))
    tasks = c.fetchall()
    logger.info(f"Retrieved {len(tasks)} tasks for user {user_id}")
    return tasks

# Function to add a report to the database
def add_report(submitted_by, text, timestamp, photo_path=None):
    logger.info(f"Adding report: {text}, submitted by: {submitted_by}, timestamp: {timestamp}, photo_path: {photo_path}")
    c.execute("INSERT INTO reports (submitted_by, text, timestamp, photo_path) VALUES (?, ?, ?, ?)", (submitted_by, text, timestamp, photo_path))
    conn.commit()
    logger.info(f"Report added by user {submitted_by}")

# Authentication function
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    logger.info(f"User {chat_id} started the bot.")
    role = get_role(chat_id)
    if role is None:
        await context.bot.send_message(chat_id=chat_id, text=START_MESSAGE)
        await context.bot.send_message(chat_id=chat_id, text=ADMIN_PROMPT)
    else:
        await context.bot.send_message(chat_id=chat_id, text="شما از قبل احراز هویت شده‌اید.")
        logger.info(f"User {chat_id} already authenticated with role {role}")

# Modified authenticate function to use SQLite
async def authenticate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text
    logger.info(f"User {chat_id} is trying to authenticate with code: {text}")
    if text == "2210720":  # Replace with actual admin code
        set_role(chat_id, 'admin')
        await context.bot.send_message(chat_id=chat_id, text=AUTH_SUCCESS)
        logger.info(f"User {chat_id} authenticated as admin.")
    elif text == "123456":  # Replace with actual personnel code
        set_role(chat_id, 'personnel')
        await context.bot.send_message(chat_id=chat_id, text=AUTH_SUCCESS)
        logger.info(f"User {chat_id} authenticated as personnel.")
    else:
        await context.bot.send_message(chat_id=chat_id, text="کد نامعتبر است.")
        logger.warning(f"User {chat_id} provided an invalid code.")

# Admin commands
async def create_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if get_role(chat_id) != 'admin':
        await context.bot.send_message(chat_id=chat_id, text=NOT_AUTHORIZED)
        logger.warning(f"Unauthorized task creation attempt by user {chat_id}")
        return

    task_description = " ".join(context.args)
    task_id = add_task(task_description, None, datetime.now(pytz.timezone('Asia/Tehran')) + timedelta(days=1))
    await context.bot.send_message(chat_id=chat_id, text=TASK_CREATED)
    logger.info(f"Admin {chat_id} created a task with ID {task_id}")

async def assign_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if get_role(chat_id) != 'admin':
        await context.bot.send_message(chat_id=chat_id, text=NOT_AUTHORIZED)
        logger.warning(f"Unauthorized task assignment attempt by user {chat_id}")
        return

    if len(context.args) < 2:
        await context.bot.send_message(chat_id=chat_id, text="استفاده: /assign_task <task_id> <user_id>")
        return

    task_id = int(context.args[0])
    user_id = int(context.args[1])

    c.execute("UPDATE tasks SET assigned_to=? WHERE task_id=?", (user_id, task_id))
    conn.commit()
    await context.bot.send_message(chat_id=chat_id, text=TASK_ASSIGNED)
    await context.bot.send_message(chat_id=user_id, text=f"وظیفه جدید به شما اختصاص داده شده است: {task_id}")
    logger.info(f"Admin {chat_id} assigned task {task_id} to user {user_id}")

async def view_all_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if get_role(chat_id) != 'admin':
        await context.bot.send_message(chat_id=chat_id, text=NOT_AUTHORIZED)
        logger.warning(f"Unauthorized view all tasks attempt by user {chat_id}")
        return

    tasks = get_all_tasks()
    response = "لیست همه وظایف:\n"
    for task_id, description, assigned_to, due_date in tasks:
        status = "در انتظار" if assigned_to is None else f"تخصیص داده شده به {assigned_to}"
        response += f"وظیفه {task_id}: {description} - {status}\n"

    await context.bot.send_message(chat_id=chat_id, text=response)
    logger.info(f"Admin {chat_id} viewed all tasks")

# Personnel commands

# Function for personnel to view their tasks
async def view_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    role = get_role(chat_id)
    if role != 'personnel':
        await context.bot.send_message(chat_id=chat_id, text=NOT_AUTHORIZED)
        logger.warning(f"Unauthorized view tasks attempt by user {chat_id}")
        return

    tasks = get_tasks_by_user(chat_id)
    response = TASK_VIEW + "\n"
    for task_id, description, assigned_to, due_date in tasks:
        response += f"{task_id}: {description} - {due_date}\n"

    await context.bot.send_message(chat_id=chat_id, text=response)
    logger.info(f"User {chat_id} viewed their tasks")

# Function for personnel to submit a report
async def submit_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    role = get_role(chat_id)
    if role != 'personnel':
        await context.bot.send_message(chat_id=chat_id, text=NOT_AUTHORIZED)
        logger.warning(f"Unauthorized submit report attempt by user {chat_id}")
        return

    report_text = update.message.caption if update.message.caption else "بدون توضیح"
    photo_file = update.message.photo[-1] if update.message.photo else None

    if photo_file:
        photo_path = f"photos/{photo_file.file_id}.jpg"
        await photo_file.download(photo_path)
    else:
        photo_path = None

    add_report(chat_id, report_text, datetime.now(pytz.timezone('Asia/Tehran')), photo_path)
    await context.bot.send_message(chat_id=chat_id, text=REPORT_RECEIVED)
    logger.info(f"User {chat_id} submitted a report with text '{report_text}' and photo_path '{photo_path}'")

# Function for personnel to submit feedback
async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    role = get_role(chat_id)
    if role != 'personnel':
        await context.bot.send_message(chat_id=chat_id, text=NOT_AUTHORIZED)
        logger.warning(f"Unauthorized feedback attempt by user {chat_id}")
        return

    feedback_text = " ".join(context.args)
    await context.bot.send_message(chat_id=chat_id, text=FEEDBACK_RECEIVED)
    await context.bot.send_message(chat_id=chat_id, text=FEEDBACK_PROMPT)
    logger.info(f"User {chat_id} provided feedback: {feedback_text}")

async def remind_task(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    task_id = job.data['task_id']
    task = c.execute("SELECT description, assigned_to FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    if task:
        description, assigned_to = task
        await context.bot.send_message(chat_id=assigned_to, text=f"{REMINDER_MESSAGE} {description}")
        logger.info(f"Sent reminder for task {task_id} to user {assigned_to}")

def main():
    application = ApplicationBuilder().token("7442902949:AAF0q1Zy_pp6VNr3vr0DsVB-oVSfTSlq0Yw").build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), authenticate))  # Handles text messages for authentication
    application.add_handler(CommandHandler("create_task", create_task))
    application.add_handler(CommandHandler("assign_task", assign_task))
    application.add_handler(CommandHandler("view_all_tasks", view_all_tasks))
    application.add_handler(CommandHandler("view_tasks", view_tasks))
    application.add_handler(MessageHandler(filters.PHOTO & filters.Caption, submit_report))
    application.add_handler(CommandHandler("feedback", feedback))

    # Job queue for reminders
    job_queue = application.job_queue
    job_queue.run_daily(remind_task, time=time(hour=8, minute=0, second=0, tzinfo=pytz.timezone('Asia/Tehran')))

    # Start the Bot
    application.run_polling()

if __name__ == "__main__":
    # Ensure photos directory exists
    if not os.path.exists('photos'):
        os.makedirs('photos')
    main()