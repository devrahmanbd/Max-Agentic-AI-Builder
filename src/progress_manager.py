import json
import os
import time
import logging
import threading
from src.notifier import send_error_notification, send_progress_update

PROGRESS_FILE = "progress.json"

logging.basicConfig(
    level=logging.DEBUG,
    format='[PROGRESS_MANAGER] %(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('log.txt', mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                progress = json.load(f)
                logger.debug(f"Loaded progress: {progress}")
                return progress
        except Exception as e:
            logger.error(f"Error loading progress file: {e}")
            return {}
    else:
        logger.debug("Progress file not found; returning empty progress dictionary.")
    return {}

def save_progress(progress):
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=4)
        logger.debug(f"Progress saved: {progress}")
    except Exception as e:
        logger.error(f"Error saving progress file: {e}")

def initialize_progress(jobname, keywords_file, keywords_list=None):
    if not os.path.exists(PROGRESS_FILE) or os.path.getsize(PROGRESS_FILE) == 0:
        progress = {
            "jobname": jobname,
            "keywords_file": keywords_file,
            "stage": "search",
            "results_file": f"{jobname}-results.txt",
            "keywords_status": {},
            "events": []
        }
        if keywords_list:
            for keyword in keywords_list:
                progress["keywords_status"][keyword] = {
                    "status": "pending",
                    "attempts": 0,
                    "last_error": "",
                    "searched": False,
                    "pages_visited": [],
                    "domains_found": [],
                    "urls_scraped": [],
                    "failed_urls": []
                }
        save_progress(progress)
        logger.info(f"Progress initialized for job '{jobname}' using keywords file '{keywords_file}'.")
    else:
        logger.info("Progress file already exists. Skipping initialization.")

def update_stage(new_stage):
    progress = load_progress()
    progress["stage"] = new_stage
    save_progress(progress)
    logger.info(f"Stage updated to: {new_stage}")

def update_keyword_status(keyword, status, attempts=None, last_error=None):
    progress = load_progress()
    if "keywords_status" not in progress:
        progress["keywords_status"] = {}
    if keyword not in progress["keywords_status"]:
        progress["keywords_status"][keyword] = {
            "status": "pending",
            "attempts": 0,
            "last_error": "",
            "searched": False,
            "pages_visited": [],
            "domains_found": [],
            "urls_scraped": [],
            "failed_urls": []
        }
    progress["keywords_status"][keyword]["status"] = status
    if attempts is not None:
        progress["keywords_status"][keyword]["attempts"] = attempts
    if last_error is not None:
        progress["keywords_status"][keyword]["last_error"] = last_error
    save_progress(progress)
    logger.info(f"Keyword '{keyword}' status updated to '{status}' (attempts: {attempts}, last_error: {last_error})")

def add_keyword_detail(keyword, detail_key, detail_value):
    progress = load_progress()
    if "keywords_status" not in progress:
        progress["keywords_status"] = {}
    if keyword not in progress["keywords_status"]:
        progress["keywords_status"][keyword] = {
            "status": "pending",
            "attempts": 0,
            "last_error": "",
            "searched": False,
            "pages_visited": [],
            "domains_found": [],
            "urls_scraped": [],
            "failed_urls": []
        }
    current = progress["keywords_status"][keyword]
    if detail_key in ["pages_visited", "domains_found", "urls_scraped", "failed_urls"]:
        if detail_value not in current[detail_key]:
            current[detail_key].append(detail_value)
    else:
        current[detail_key] = detail_value
    save_progress(progress)
    logger.info(f"Keyword '{keyword}' detail updated: {detail_key} = {detail_value}")
def mark_keyword_searched(keyword):
    add_keyword_detail(keyword, "searched", True)

def add_page_visited(keyword, page_url):
    add_keyword_detail(keyword, "pages_visited", page_url)

def add_domain_found(keyword, domain):
    add_keyword_detail(keyword, "domains_found", domain)

def add_url_scraped(keyword, url):
    add_keyword_detail(keyword, "urls_scraped", url)

def add_failed_url(keyword, url):
    add_keyword_detail(keyword, "failed_urls", url)

def increment_keyword_attempts(keyword):
    progress = load_progress()
    if "keywords_status" not in progress:
        progress["keywords_status"] = {}
    if keyword not in progress["keywords_status"]:
        progress["keywords_status"][keyword] = {
            "status": "pending",
            "attempts": 0,
            "last_error": "",
            "searched": False,
            "pages_visited": [],
            "domains_found": [],
            "urls_scraped": [],
            "failed_urls": []
        }
    progress["keywords_status"][keyword]["attempts"] += 1
    save_progress(progress)
    logger.info(f"Keyword '{keyword}' attempts incremented to {progress['keywords_status'][keyword]['attempts']}")

def record_scraping_action(keyword, action, url):
    if action == "visited":
        add_page_visited(keyword, url)
    elif action == "domain":
        add_domain_found(keyword, url)
    elif action == "scraped":
        add_url_scraped(keyword, url)
    elif action == "failed":
        add_failed_url(keyword, url)
    else:
        logger.error(f"Unknown action '{action}' for keyword '{keyword}' with URL '{url}'")

def get_progress_summary():
    progress = load_progress()
    summary = {
        "jobname": progress.get("jobname", "N/A"),
        "stage": progress.get("stage", "N/A"),
        "total_keywords": len(progress.get("keywords_status", {})),
        "details": progress.get("keywords_status", {})
    }
    return summary


def log_event(event_type, message, details=None):
    progress = load_progress()
    event = {
        "event_type": event_type,
        "message": message,
        "details": details if details else {},
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    if "events" not in progress:
        progress["events"] = []
    progress["events"].append(event)
    save_progress(progress)
    logger.info(f"Event logged: {event_type} - {message}")

    if event_type.lower() == "error":
        send_error_notification_threadsafe(message)



def start_hourly_updates(interval=3600):
    def send_update():
        while True:
            time.sleep(interval)
            send_progress_update(PROGRESS_FILE)
            logger.info("Hourly progress update sent.")
    thread = threading.Thread(target=send_update, daemon=True)
    thread.start()
    logger.info("Hourly update thread started.")
