#!/usr/bin/env python3
import asyncio
import logging
import os
import json
import time
import argparse
from urllib.parse import urlparse
import requests
import random
import datetime

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter
from src.crawler.langchain_processing import process_html_file 

try:
    from crawl4ai.rate_limiter import RateLimiter
except ImportError:
    class RateLimiter:
        def __init__(self, base_delay=(1.0, 3.0), max_delay=60.0, max_retries=3, rate_limit_codes=[429, 503]):
            self.base_delay = base_delay
            self.max_delay = max_delay
            self.max_retries = max_retries
            self.rate_limit_codes = rate_limit_codes
        async def wait_if_needed(self, response_code):
            if response_code in self.rate_limit_codes:
                delay = random.uniform(*self.base_delay)
                delay = min(delay, self.max_delay)
                await asyncio.sleep(delay)
        def update_delay(self, response_code, extra=None):
            pass
else:
    import inspect
    sig = inspect.signature(RateLimiter.update_delay)
    if len(sig.parameters) < 3:
        def update_delay(self, response_code, extra=None):
            pass
        RateLimiter.update_delay = update_delay

try:
    from crawl4ai.config import ProxyConfig
except ImportError:
    class ProxyConfig:
        def __init__(self, http, https):
            self.http = http
            self.https = https
        def __repr__(self):
            return f"ProxyConfig(http={self.http}, https={self.https})"

try:
    from crawl4ai.monitor import CrawlerMonitor, DisplayMode
except ImportError:
    class DisplayMode:
        DETAILED = "DETAILED"
        AGGREGATED = "AGGREGATED"
    class CrawlerMonitor:
        def __init__(self, max_visible_rows=15, display_mode=DisplayMode.DETAILED):
            self.max_visible_rows = max_visible_rows
            self.display_mode = display_mode
            self.tasks = {}
            self.running = False
        def start(self):
            self.running = True
            logging.info("CrawlerMonitor started.")
        def stop(self):
            self.running = False
            logging.info("CrawlerMonitor stopped.")
        def add_task(self, task_id, url):
            self.tasks[task_id] = {"url": url, "status": "added"}
            logging.info(f"Task added: {task_id} -> {url}")
            self._display_tasks()
        def update_task(self, task_id, status="updated", **kwargs):
            if task_id in self.tasks:
                self.tasks[task_id].update({"status": status})
                self.tasks[task_id].update(kwargs)
            else:
                self.tasks[task_id] = {"url": None, "status": status}
                self.tasks[task_id].update(kwargs)
            logging.info(f"Task updated: {task_id} -> {status} {kwargs}")
            self._display_tasks()
        def remove_task(self, task_id):
            if task_id in self.tasks:
                logging.info(f"Task removed: {task_id}")
                del self.tasks[task_id]
                self._display_tasks()
        def _display_tasks(self):
            if self.display_mode == DisplayMode.DETAILED:
                tasks_to_show = list(self.tasks.items())[:self.max_visible_rows]
                logging.info("Current active tasks:")
                for tid, details in tasks_to_show:
                    logging.info(f"    {tid}: {details}")
            elif self.display_mode == DisplayMode.AGGREGATED:
                logging.info(f"Total active tasks: {len(self.tasks)}")

from crawl4ai.async_dispatcher import MemoryAdaptiveDispatcher

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)
os.makedirs("data/results/markdown", exist_ok=True)
os.makedirs("data/results/html", exist_ok=True)


PROGRESS_FILE = "progress.json"

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading progress file: {e}")
            return {}
    return {}

def save_progress(progress):
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving progress file: {e}")

class AsyncCrawl4AI:
    def __init__(self, domains_dir, concurrency_limit=10, use_proxy=False, proxy_config=None, use_rate_limiter=True):
        self.domains_dir = domains_dir
        self.concurrency_limit = concurrency_limit
        self.use_proxy = use_proxy
        self.proxy_config = proxy_config
        self.use_rate_limiter = use_rate_limiter
        self.urls_to_crawl = []

    def load_urls(self):
        urls = []
        if os.path.isdir(self.domains_dir):
            for fname in os.listdir(self.domains_dir):
                fpath = os.path.join(self.domains_dir, fname)
                if os.path.isfile(fpath) and fpath.endswith(".txt"):
                    with open(fpath, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                urls.append(line)
        self.urls_to_crawl = urls
        logger.info(f"[CRAWL] Loaded {len(self.urls_to_crawl)} page URL(s) from {self.domains_dir}")

    async def crawl(self):
        proxy_conf = None
        if self.use_proxy and self.proxy_config:
            proxy_conf = self.proxy_config
            logger.info(f"[CRAWL] Using proxy configuration: {proxy_conf}")

        browser_config = BrowserConfig(
            headless=True,
            verbose=True,
            proxy_config=proxy_conf
        )

        from .content_filter import create_content_filter, create_markdown_generator
        content_filter = create_content_filter(threshold=0.5, min_word_threshold=50, threshold_type="fixed")
        md_generator = create_markdown_generator(content_filter, options={
            "ignore_links": True,
            "ignore_images": True,
            "escape_html": True,
            "body_width": 80,
            "skip_internal_links": True,
            "include_sup_sub": True
        })

        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.ENABLED,
            check_robots_txt=True,
            markdown_generator=md_generator
        )

        rate_limiter = None
        if self.use_rate_limiter:
            rate_limiter = RateLimiter(
                base_delay=(2.0, 4.0),
                max_delay=30.0,
                max_retries=3,
                rate_limit_codes=[429, 503]
            )

        dispatcher = MemoryAdaptiveDispatcher(
            memory_threshold_percent=70.0,
            check_interval=1.0,
            max_session_permit=self.concurrency_limit,
            rate_limiter=rate_limiter,
            monitor=CrawlerMonitor(max_visible_rows=15, display_mode=DisplayMode.DETAILED)
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            results = await crawler.arun_many(
                urls=self.urls_to_crawl,
                config=run_config,
                dispatcher=dispatcher
            )
            for result in results:
                if result.success:
                    domain = urlparse(result.url).netloc
                    markdown_filename = f"data/results/markdown/{domain}.md"
                    with open(markdown_filename, "a", encoding="utf-8") as md_file:
                        md_file.write(result.markdown + "\n\n")
                    logger.info(f"[CRAWL] Saved markdown for {result.url} to {markdown_filename}")
                    if hasattr(result, "html") and result.html:
                        html_temp_file = f"data/results/html/{domain}.html"
                        with open(html_temp_file, "w", encoding="utf-8") as html_file:
                            html_file.write(result.html)
                        timestamp = datetime.datetime.now().isoformat()
                        try:
                            process_html_file(html_temp_file, result.url, domain, timestamp)
                            logger.info(f"[CRAWL] Processed and saved JSON for {result.url}")
                        except Exception as e:
                            logger.error(f"[CRAWL] Error processing HTML for {result.url}: {e}")
                        os.remove(html_temp_file)
                else:
                    error_lower = result.error_message.lower() if result.error_message else ""
                    if (not self.use_proxy) and any(kw in error_lower for kw in ["429", "blocked", "geo", "restricted"]):
                        logger.info(f"[CRAWL] Retrying {result.url} with proxy due to error: {result.error_message}")
                        new_browser_config = BrowserConfig(
                            headless=True,
                            verbose=True,
                            proxy_config=self.proxy_config
                        )
                        new_result = await crawler.arun(url=result.url, config=new_browser_config)
                        if new_result.success:
                            domain = urlparse(new_result.url).netloc
                            markdown_filename = f"data/results/markdown/{domain}.md"
                            with open(markdown_filename, "a", encoding="utf-8") as md_file:
                                md_file.write(new_result.markdown + "\n\n")
                            logger.info(f"[CRAWL] Saved markdown for {new_result.url} (retried with proxy) to {markdown_filename}")
                        else:
                            logger.error(f"[CRAWL] Failed to crawl {result.url} with proxy: {new_result.error_message}")
                    else:
                        logger.error(f"[CRAWL] Failed to crawl {result.url}: {result.error_message}")

    async def start_crawling(self):
        logger.info("[CRAWL] Starting crawling process...")
        self.load_urls()
        await self.crawl()

def main():
    parser = argparse.ArgumentParser(description="Crawl4AI Resumable Crawler for Page URLs")
    parser.add_argument("-d", "--domains_dir", required=True, help="Path to the directory containing domain files (page URLs)")
    parser.add_argument("-j", "--jobname", required=True, help="Job name for output files")
    parser.add_argument("-p", "--proxy", default="OFF", choices=["ON", "OFF"],
                        help="Enable proxy for crawling page URLs? (ON or OFF, default OFF)")
    args = parser.parse_args()

    domains_dir = args.domains_dir
    jobname = args.jobname
    use_proxy = (args.proxy.upper() == "ON")

    from src.config import PROXY_ENABLED, PROXY_CONFIGS
    proxy_config = None
    if use_proxy and PROXY_CONFIGS:
        proxy_config = random.choice(PROXY_CONFIGS)
    else:
        use_proxy = False

    if not os.path.isdir(domains_dir):
        logger.error(f"Error: Domains directory '{domains_dir}' not found!")
        return

    logger.info(f"[SETUP] Proxy usage {'enabled' if use_proxy else 'disabled'} for crawling page URLs.")

    def get_ip_info(proxy=None):
        url = "https://ipinfo.io/json"
        try:
            if proxy:
                response = requests.get(url, proxies=proxy, timeout=10)
            else:
                response = requests.get(url, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Error retrieving IP info: {e}")
            return None

    system_ip_info = get_ip_info()
    logger.info(f"[IP] System IP info: {system_ip_info}")
    if use_proxy and proxy_config:
        def convert_proxy_config_for_requests(proxy_config):
            server = proxy_config.get("host", "")
            username = proxy_config.get("username", "")
            password = proxy_config.get("password", "")
            proxy_str = f"http://{username}:{password}@{server}:{proxy_config.get('port', '')}"
            return {"http": proxy_str, "https": proxy_str}
        req_proxy = convert_proxy_config_for_requests(proxy_config)
        proxy_ip_info = get_ip_info(proxy=req_proxy)
        logger.info(f"[IP] Proxy IP info: {proxy_ip_info}")
    else:
        logger.info("[IP] No proxy in use.")

    progress = {}
    PROGRESS_FILE = "progress.json"
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                progress = json.load(f)
        except Exception as e:
            logger.error(f"Error loading progress file: {e}")
    if (progress.get("jobname") == jobname and progress.get("domains_dir") == domains_dir):
        stage = progress.get("stage", "crawl")
        logger.info(f"[PROGRESS] Resuming from stage '{stage}'...")
    else:
        stage = "crawl"
        progress = {
            "jobname": jobname,
            "domains_dir": domains_dir,
            "stage": stage
        }
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=4)
        logger.info("[PROGRESS] Starting new job...")

    while progress.get("stage") != "done":
        try:
            crawler_instance = AsyncCrawl4AI(
                domains_dir,
                concurrency_limit=10,
                use_proxy=use_proxy,
                proxy_config=proxy_config,
                use_rate_limiter=True
            )
            asyncio.run(crawler_instance.start_crawling())
            progress["stage"] = "done"
            with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                json.dump(progress, f, indent=4)
        except Exception as e:
            logger.error(f"[MAIN] Error occurred: {e}. Restarting in 5 seconds...")
            time.sleep(5)
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                progress = json.load(f)
        except Exception as e:
            logger.error(f"Error reloading progress file: {e}")
            progress = {}
    logger.info("[MAIN] Crawling process complete.")

if __name__ == "__main__":
    main()
