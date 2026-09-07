import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from agent import run_agent
from db import init_db

load_dotenv()
logging.basicConfig(level=logging.INFO)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kirana Store Agent initialized and ready. How can I help you today?")

async def new_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id in chat_sessions:
        del chat_sessions[chat_id]
    await update.message.reply_text("Conversation cleared. Store inventory and persistent preferences are retained.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user_text = update.message.text
    
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        reply_text, file_path = run_agent(user_text, chat_id)
        
        safe_reply = str(reply_text)[:4000]
        await update.message.reply_text(safe_reply)
        
        if file_path and os.path.exists(file_path):
            with open(file_path, "rb") as doc:
                await update.message.reply_document(document=doc)
                
    except Exception as e:
        logging.error(f"Error processing message: {e}")
        await update.message.reply_text("Telegram API Error: Check VS Code Terminal.")

def main():
    init_db()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN is missing. Please check your .env file.")
        return

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("new", new_chat_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Telegram Agent is running...")
    app.run_polling()

if __name__ == "__main__":
    main()