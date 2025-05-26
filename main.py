import asyncio
import logging
import signal
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from handlers import start, forward_to_group, forward_to_user
from settings import TELEGRAM_TOKEN, TELEGRAM_SUPPORT_CHAT_ID, PERSONAL_ACCOUNT_CHAT_ID

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Событие остановки
stop_event = asyncio.Event()


def start_dummy_webserver():
    """Запускает HTTP-сервер для Heroku, чтобы избежать ошибки R10"""
    class SimpleHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running")

    port = int(os.environ.get("PORT", 5000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    logging.info(f"Dummy webserver started on port {port}")


async def main():
    # 🟢 Запуск dummy HTTP-сервера
    start_dummy_webserver()

    # Инициализация бота
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Регистрация хендлеров
    application.add_handler(CommandHandler("start", start))

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND
            & ~filters.Chat(
                chat_id=[TELEGRAM_SUPPORT_CHAT_ID, PERSONAL_ACCOUNT_CHAT_ID]
            ),
            forward_to_group,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & filters.Chat(chat_id=[TELEGRAM_SUPPORT_CHAT_ID, PERSONAL_ACCOUNT_CHAT_ID])
            & filters.REPLY,
            forward_to_user,
        )
    )

    logging.info("Handlers registered.")

    # Обработка сигналов завершения
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(application)))

    # Старт бота
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    logging.info("Bot started. Press Ctrl+C to stop.")

    # Ожидание сигнала завершения
    await stop_event.wait()

    # Завершение
    await application.stop()
    await application.shutdown()


async def shutdown(application: Application):
    logging.info("Received stop signal, shutting down...")
    stop_event.set()


if __name__ == "__main__":
    asyncio.run(main())
