#!/usr/bin/env python3
import logging
import json
import os
import time
import threading
import asyncio
from telegram import Bot
from telegram.error import TelegramError, NetworkError, TimedOut, RetryAfter
from telegram.request import HTTPXRequest 
__all__ = [
    "send_progress_update",
    "send_progress_update_threadsafe",
    "send_error_notification",
    "send_error_notification_threadsafe",
    "start_hourly_notifications",
    "watchdog_monitor"
]

logging.basicConfig(
    level=logging.INFO,
    format='[NOTIFIER] %(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "Add Your Bot Token"
TELEGRAM_CHAT_ID = "Add Your Chat ID"
PROGRESS_FILE = "progress.json"

def run_notifier_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

notifier_loop = asyncio.new_event_loop()
notifier_thread = threading.Thread(target=run_notifier_loop, args=(notifier_loop,), daemon=True)
notifier_thread.start()

def ensure_notifier_loop():
    global notifier_loop, notifier_thread
    if notifier_loop.is_closed():
        logger.error("Notifier event loop is closed. Reinitializing...")
        notifier_loop = asyncio.new_event_loop()
        notifier_thread = threading.Thread(target=run_notifier_loop, args=(notifier_loop,), daemon=True)
        notifier_thread.start()

request_instance = HTTPXRequest(
    connect_timeout=10.0,
    pool_timeout=10.0,
    connection_pool_size=5000
)

bot = Bot(token=TELEGRAM_TOKEN, request=request_instance)

async def send_message(message):
    retry_count = 0
    while retry_count < 3:
        try:
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message,
                parse_mode="Markdown"
            )
            logger.info(f"📢 Message sent to Telegram: {message}")
            return
        except (TelegramError, NetworkError, TimedOut) as e:
            logger.error(f"❌ Error sending message: {e}")
            retry_count += 1
            if retry_count < 3:
                logger.info(f"Retrying... Attempt {retry_count}/3")
                await asyncio.sleep(15)
            else:
                logger.error("Maximum retries reached. Giving up.")
                return
        except RetryAfter as e:
            logger.warning(f"Rate limited. Retrying after {e.retry_after} seconds.")
            await asyncio.sleep(e.retry_after)
            retry_count += 1

def send_message_threadsafe(message):
    ensure_notifier_loop()
    try:
        future = asyncio.run_coroutine_threadsafe(send_message(message), notifier_loop)
        future.result()  
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            logger.error("Notifier event loop was closed. Reinitializing...")
            ensure_notifier_loop()
            future = asyncio.run_coroutine_threadsafe(send_message(message), notifier_loop)
            try:
                future.result()
            except Exception as ex:
                logger.error(f"Error after reinitialization: {ex}")
        else:
            logger.error(f"❌ Error in send_message_threadsafe: {e}")
            send_error_notification_threadsafe(f"Error in send_message_threadsafe: {e}")
    except Exception as e:
        logger.error(f"❌ Error in send_message_threadsafe: {e}")
        send_error_notification_threadsafe(f"Error in send_message_threadsafe: {e}")

async def send_progress_update():
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                progress_data = json.load(f)
            jobname = progress_data.get("jobname", "Unknown Job")
            stage = progress_data.get("stage", "Unknown Stage")
            keywords_status = progress_data.get("keywords_status", {})
            total = len(keywords_status)
            completed = sum(1 for v in keywords_status.values() if v.get("searched") is True)
            in_progress = sum(1 for v in keywords_status.values() if v.get("status") not in ("completed", "failed") and not v.get("searched"))
            failed = sum(1 for v in keywords_status.values() if v.get("status") == "failed")
            message = (
                f"📊 *Progress Update*\n"
                f"📌 *Job:* {jobname}\n"
                f"🔄 *Stage:* {stage}\n"
                f"📋 *Total Keywords:* {total}\n"
                f"✅ *Completed:* {completed}\n"
                f"⏳ *In Progress:* {in_progress}\n"
                f"❌ *Failed:* {failed}"
            )
        else:
            message = "⚠️ progress.json not found."
        await send_message(message)
    except Exception as e:
        logger.error(f"❌ Error in send_progress_update: {e}")
        await send_error_notification(f"⚠️ Error in send_progress_update: {e}")

def send_progress_update_threadsafe():
    ensure_notifier_loop()
    try:
        future = asyncio.run_coroutine_threadsafe(send_progress_update(), notifier_loop)
        future.result()
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            logger.error("Notifier event loop was closed in send_progress_update_threadsafe. Reinitializing...")
            ensure_notifier_loop()
            future = asyncio.run_coroutine_threadsafe(send_progress_update(), notifier_loop)
            try:
                future.result()
            except Exception as ex:
                logger.error(f"Error after reinitialization in send_progress_update_threadsafe: {ex}")
        else:
            logger.error(f"❌ Error in send_progress_update_threadsafe: {e}")
    except Exception as e:
        logger.error(f"❌ Error in send_progress_update_threadsafe: {e}")

async def send_error_notification(error_message):
    try:
        error_msg = f"❌ *Error Occurred:* {error_message}"
        logger.error(error_msg)
        await send_message(error_msg)
    except Exception as e:
        logger.error(f"❌ Error in send_error_notification: {e}")

def send_error_notification_threadsafe(error_message):
    ensure_notifier_loop()
    try:
        future = asyncio.run_coroutine_threadsafe(send_error_notification(error_message), notifier_loop)
        future.result()
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            logger.error("Notifier event loop was closed in send_error_notification_threadsafe. Reinitializing...")
            ensure_notifier_loop()
            future = asyncio.run_coroutine_threadsafe(send_error_notification(error_message), notifier_loop)
            try:
                future.result()
            except Exception as ex:
                logger.error(f"Error after reinitialization in send_error_notification_threadsafe: {ex}")
        else:
            logger.error(f"❌ Error in send_error_notification_threadsafe: {e}")
    except Exception as e:
        logger.error(f"❌ Error in send_error_notification_threadsafe: {e}")

def start_hourly_notifications(interval=3600):
    def send_updates():
        while True:
            try:
                time.sleep(interval)
                send_progress_update_threadsafe()
                logger.info("🔄 Hourly progress update sent.")
            except Exception as e:
                logger.error(f"Hourly notification error: {e}")
                send_error_notification_threadsafe(f"Hourly notification error: {e}")
    thread = threading.Thread(target=send_updates, daemon=True)
    thread.start()
    logger.info("⏳ Hourly notification thread started.")

def watchdog_monitor(interval=60):
    def monitor():
        while True:
            try:
                time.sleep(interval)
                if os.path.exists(PROGRESS_FILE):
                    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                        progress_data = json.load(f)
                    upload_history = progress_data.get("upload_history", [])
                    final_failures = [e for e in upload_history if e.get("status") in ("failed", "not_found")]
                    if final_failures:
                        summary = "🚨 *Realtime Alert: Upload Failures Detected*\n"
                        for event in final_failures[-3:]:
                            action = event.get("action", "N/A")
                            file_or_folder = event.get("file") or event.get("folder") or "N/A"
                            ts = event.get("timestamp", "N/A")
                            summary += f"- {action} on {file_or_folder} at {ts}\n"
                        send_message_threadsafe(summary)
                        logger.info("Watchdog: Realtime failure alert sent.")
            except Exception as e:
                logger.error(f"Watchdog encountered an error: {e}")
                send_error_notification_threadsafe(f"Watchdog error: {e}")
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    logger.info("🐶 Watchdog monitor thread started.")
