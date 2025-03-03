import time
import random
import requests
import logging
from urllib.parse import urlparse
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from src.config import PROXY_ENABLED, PROXY_STRINGS, BACKOFF_INITIAL, BACKOFF_MULTIPLIER, MAX_RETRIES
from src.progress_manager import (
    save_progress, 
    mark_keyword_searched, 
    add_domain_found, 
    add_url_scraped, 
    add_failed_url
)
from src.google_search.sitemap import find_sitemap

from googlesearch import search

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

CURRENT_PROXY = None

def get_random_proxy():
    return random.choice(PROXY_STRINGS)

def get_proxy_str():
    global CURRENT_PROXY
    if not CURRENT_PROXY:
        CURRENT_PROXY = get_random_proxy()
    return CURRENT_PROXY

def invalidate_current_proxy(proxy):
    logger.info(f"[SEARCH] Invalidating proxy: {proxy}")
    global CURRENT_PROXY
    CURRENT_PROXY = None

def extract_domain(url):
    parsed_url = urlparse(url)
    return f"{parsed_url.scheme}://{parsed_url.netloc}" if parsed_url.netloc else None

def get_ip_info(proxy=None):
    url = "https://ipinfo.io/json"
    try:
        if proxy:
            response = requests.get(url, proxies={"https": proxy}, timeout=5, verify=False)
        else:
            response = requests.get(url, timeout=5)
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving IP info: {e}")
        return None

def show_ip_info():
    system_ip_info = get_ip_info()
    logger.info(f"[IP CHECK] System IP: {system_ip_info}")
    if PROXY_ENABLED:
        proxy_str = get_proxy_str()
        proxy_ip_info = get_ip_info(proxy=proxy_str)
        logger.info(f"[IP CHECK] Proxy IP: {proxy_ip_info}")
    else:
        logger.info("[IP CHECK] No proxy in use.")

def retry_find_sitemap(domain, retries=3, delay=5):
    for attempt in range(1, retries + 1):
        try:
            sitemap = find_sitemap(domain)
            if sitemap:
                return sitemap
            else:
                logger.info(f"[SEARCH] No sitemap found for {domain} on attempt {attempt}.")
        except Exception as e:
            error_message = str(e).lower()
            if any(trigger in error_message for trigger in ["not a gzipped file", "404", "301", "429", "geo", "blocked", "cloudflare"]):
                logger.warning(f"[SEARCH] Error for domain {domain} on attempt {attempt}: {e}")
            else:
                logger.error(f"[SEARCH] Unexpected error for domain {domain} on attempt {attempt}: {e}")
        time.sleep(delay)
    return None

def search_google(keywords_file, jobname, num_results=500):
    global CURRENT_PROXY
    show_ip_info()

    unique_domains = set()
    sitemap_urls = set()

    with open(keywords_file, "r", encoding="utf-8") as file:
        keywords = file.readlines()

    for keyword in keywords:
        keyword = keyword.strip()
        if not keyword:
            continue

        mark_keyword_searched(keyword)
        logger.info(f"[SEARCH] Searching for: {keyword}")

        retries = MAX_RETRIES
        backoff = BACKOFF_INITIAL
        if PROXY_ENABLED:
            CURRENT_PROXY = None
            current_proxy_str = get_proxy_str()
        else:
            current_proxy_str = None

        results = None
        while retries > 0:
            try:
                try:
                    all_results = list(search(
                        keyword,
                        num_results=num_results,
                        lang="en",
                        region="us",
                        safe=None,
                        unique=True,
                        proxy=current_proxy_str,
                        ssl_verify=False
                    ))
                except TypeError:
                    all_results = list(search(
                        keyword,
                        num=num_results,
                        lang="en",
                        region="us",
                        safe=None,
                        unique=True,
                        proxy=current_proxy_str,
                        ssl_verify=False
                    ))
                results = all_results
                break 
            except Exception as e:
                error_message = str(e).lower()
                if any(trigger in error_message for trigger in ["429", "blocked", "rate limit", "temporarily unavailable"]):
                    logger.warning(f"[SEARCH] Error '{error_message}' encountered for '{keyword}'. "
                                   f"Invalidating proxy and retrying in {backoff} sec... (Retries left: {retries-1})")
                    if PROXY_ENABLED:
                        invalidate_current_proxy(current_proxy_str)
                        current_proxy_str = get_proxy_str()
                    time.sleep(backoff + random.uniform(1, 3))
                    retries -= 1
                    backoff *= BACKOFF_MULTIPLIER
                else:
                    logger.error(f"[SEARCH] Error for '{keyword}': {e}")
                    add_failed_url(keyword, str(e))
                    break

        if results is None:
            logger.warning(f"[SEARCH] No results for '{keyword}'")
            continue

        new_result_found = False
        for result in results:
            domain = extract_domain(result)
            if domain and domain not in unique_domains:
                unique_domains.add(domain)
                add_domain_found(keyword, domain)
                sitemap = retry_find_sitemap(domain, retries=3, delay=5)
                if sitemap:
                    sitemap_urls.add(sitemap)
                    logger.info(f"[SEARCH] Found valid sitemap: {sitemap}")
                    add_url_scraped(keyword, sitemap)
                new_result_found = True

        if not new_result_found:
            logger.info(f"[SEARCH] No new results found for '{keyword}'.")
            continue

    if sitemap_urls:
        output_filename = f"{jobname}-results.txt"
        with open(output_filename, "w", encoding="utf-8") as output_file:
            for sitemap in sitemap_urls:
                output_file.write(sitemap + "\n")
        logger.info(f"[SEARCH] Results saved to {output_filename}")
        progress = {
            "jobname": jobname,
            "keywords_file": keywords_file,
            "stage": "domains",
            "results_file": output_filename
        }
        save_progress(progress)
        return output_filename
    else:
        logger.error("[SEARCH] No sitemaps found. Exiting...")
        return None
