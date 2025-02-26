#!/usr/bin/env python3
import argparse
import os
import time
import json
import asyncio
import logging
from functools import wraps
from rich.logging import RichHandler
from rich.console import Console

from src.google_search.search import search_google
from src.url_extractor import generate_domain_files
from src.crawler.async_crawler import AsyncCrawl4AI
from src.progress_manager import save_progress, load_progress
from src.config import PROXY_ENABLED
from src.notifier import start_hourly_notifications, watchdog_monitor, send_progress_update, send_error_notification

from src.config import (
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_SECURE,
    BUCKET_NAME,
    RESULT_FOLDER,
    JOB_RESULT_FILE,
    PROGRESS_FILE
)

from src.storage.minio_upload import start_hourly_sync
from minio import Minio

console = Console()

log_formatter = logging.Formatter('%(message)s')
console_handler = RichHandler(console=console)
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)
file_handler = logging.FileHandler('log.txt')
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(console_handler)
logger.addHandler(file_handler)

watchdog_monitor(interval=60)

def log_function_args(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug(f"Calling {func.__name__} with arguments: {args}, {kwargs}")
        return func(*args, **kwargs)
    return wrapper

async def main():
    parser = argparse.ArgumentParser(
        description="Crawl4AI Resumable Crawler with Optional Proxy and MinIO Sync"
    )
    parser.add_argument("-k", "--keywords", required=True, help="Path to the keywords file")
    parser.add_argument("-j", "--jobname", required=True, help="Job name for output files")
    parser.add_argument("-p", "--proxy", default="OFF", choices=["ON", "OFF"],
                        help="Enable proxy for Google search requests? (ON or OFF, default OFF)")
    args = parser.parse_args()

    keywords_file = args.keywords
    jobname = args.jobname

    global PROXY_ENABLED
    PROXY_ENABLED = (args.proxy.upper() == "ON")

    logger.info("Starting job with parameters:")
    logger.info(f"  Keywords file: {keywords_file}")
    logger.info(f"  Job name: {jobname}")
    logger.info(f"  Proxy enabled: {PROXY_ENABLED}")

    if not os.path.exists(keywords_file):
        logger.error(f"Keywords file '{keywords_file}' not found!")
        return

    job_result_file = JOB_RESULT_FILE.format(jobname=jobname)
    if not os.path.exists(job_result_file):
        logger.info(f"Job result file '{job_result_file}' not found. Creating empty file.")
        open(job_result_file, "w").close()

    start_hourly_notifications(interval=3600)
    watchdog_monitor(interval=3600)           
    await send_progress_update()

    minio_client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )
    start_hourly_sync(minio_client, BUCKET_NAME, RESULT_FOLDER, job_result_file, PROGRESS_FILE, interval=3600)

    progress = load_progress()
    if (progress.get("jobname") == jobname and progress.get("keywords_file") == keywords_file):
        stage = progress.get("stage", "search")
        sitemap_results_file = progress.get("results_file", f"{jobname}-results.txt")
        logger.info(f"Resuming from stage '{stage}'...")
    else:
        stage = "search"
        sitemap_results_file = f"{jobname}-results.txt"
        progress = {
            "jobname": jobname,
            "keywords_file": keywords_file,
            "stage": stage,
            "results_file": sitemap_results_file
        }
        save_progress(progress)
        logger.info("Starting new job...")

    while progress.get("stage") != "done":
        try:
            if progress["stage"] == "search":
                logger.info("Stage: SEARCH")
                sitemap_results_file = search_google(keywords_file, jobname, num_results=50)
                if sitemap_results_file is None:
                    logger.error("Exiting due to no sitemaps found.")
                    return
                if not os.path.exists(sitemap_results_file):
                    logger.warning(f"Job result file '{sitemap_results_file}' not found. Creating empty file.")
                    open(sitemap_results_file, "w").close()
                progress["results_file"] = sitemap_results_file
                progress["stage"] = "domains"
                save_progress(progress)
                logger.info("Transitioning to stage: DOMAINS")
            if progress["stage"] == "domains":
                logger.info("Stage: DOMAINS")
                generate_domain_files(sitemap_results_file, job_name=jobname)
                progress["stage"] = "crawl"
                save_progress(progress)
                logger.info("Transitioning to stage: CRAWL")
            if progress["stage"] == "crawl":
                logger.info("Stage: CRAWL")
                domains_dir = os.path.join("data", "results", "domains")
                crawler = AsyncCrawl4AI(domains_dir, concurrency_limit=10)
                await crawler.start_crawling() 
                progress["stage"] = "done"
                save_progress(progress)
                logger.info("Crawling complete. Job marked as done.")
            await send_progress_update()

        except Exception as e:
            logger.error(f"Error occurred: {e}. Restarting service from last saved state in 5 seconds...")
            await send_error_notification(str(e))
            await asyncio.sleep(5)
        
        progress = load_progress()

    logger.info("Crawling process complete.")

if __name__ == "__main__":
    asyncio.run(main())
