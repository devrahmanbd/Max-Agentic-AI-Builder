import os
import logging
from urllib.parse import urlparse
from src.progress_manager import add_page_visited, add_domain_found, add_failed_url
from src.google_search.sitemap import extract_urls_from_sitemap

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def generate_domain_files(results_file, job_name="url_extraction"):
    try:
        with open(results_file, "r", encoding="utf-8") as file:
            sitemap_urls = [line.strip() for line in file if line.strip()]
        logger.info(f"Found {len(sitemap_urls)} sitemap URL(s) in {results_file}")
    except Exception as e:
        logger.error(f"Error reading results file {results_file}: {e}")
        return

    if not sitemap_urls:
        logger.warning("No sitemap URLs found in the results file.")
        return
    domain_map = {}
    for sitemap in sitemap_urls:
        parsed = urlparse(sitemap)
        domain = parsed.netloc if parsed.netloc else parsed.path.split('/')[0]
        domain = domain.replace("www.", "")
        if domain:
            domain_map.setdefault(domain, []).append(sitemap)
        else:
            logger.warning(f"Unable to extract domain from sitemap URL: {sitemap}")
            add_failed_url(job_name, sitemap)

    logger.info(f"Grouped sitemaps by domain: {domain_map}")

    for domain, sitemaps in domain_map.items():
        logger.info(f"Processing domain '{domain}' with {len(sitemaps)} sitemap(s)")
        add_domain_found(job_name, domain)
        all_urls = set()
        for sitemap in sitemaps:
            try:
                urls = extract_urls_from_sitemap(sitemap)
                logger.info(f"Extracted {len(urls)} URL(s) from sitemap: {sitemap}")
                all_urls.update(urls)
            except Exception as e:
                logger.error(f"Error extracting URLs from sitemap {sitemap} for domain {domain}: {e}")
                add_failed_url(job_name, sitemap)
        logger.info(f"Total URLs extracted for domain '{domain}': {len(all_urls)}")
        if all_urls:
            output_dir = os.path.join("data", "results", "domains")
            os.makedirs(output_dir, exist_ok=True)
            domain_file = os.path.join(output_dir, f"{domain}.txt")
            try:
                with open(domain_file, "w", encoding="utf-8") as df:
                    for url in sorted(all_urls):
                        df.write(url + "\n")
                        add_page_visited(job_name, url)
                logger.info(f"Saved {len(all_urls)} unique URL(s) for domain '{domain}' in {domain_file}")
            except Exception as e:
                logger.error(f"Error writing to file {domain_file}: {e}")
                add_failed_url(job_name, domain_file)
        else:
            logger.warning(f"No URLs found for domain: {domain}")
            add_failed_url(job_name, domain)
