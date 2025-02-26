import requests
import xml.etree.ElementTree as ET
import logging
import gzip
from io import BytesIO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _get_content(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/114.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10, verify=True)
        if response.status_code == 406:
            logger.warning(f"Received 406 for {url}. Retrying without 'Accept' header.")
            headers.pop('Accept', None)
            response = requests.get(url, headers=headers, timeout=10, verify=True)
        response.raise_for_status()
        if url.endswith('.gz'):
            import gzip
            decompressed = gzip.decompress(response.content)
            return decompressed.decode('utf-8')
        else:
            return response.text
    except requests.exceptions.Timeout:
        logger.error(f"Timeout when accessing {url}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error accessing {url}: {e}")
    return ""


def is_valid_sitemap(sitemap_url):
    content = _get_content(sitemap_url)
    if not content:
        return False

    if sitemap_url.endswith('.txt') or sitemap_url.endswith('.txt.gz'):
        return "http" in content.lower()
    else:
        return '<urlset' in content.lower() or '<sitemapindex' in content.lower()

def parse_robots_for_sitemaps(domain):
    robots_url = f"{domain}/robots.txt"
    sitemap_links = []
    try:
        content = _get_content(robots_url)
        for line in content.splitlines():
            if line.lower().startswith("sitemap:"):
                sitemap_url = line.split(":", 1)[1].strip()
                if is_valid_sitemap(sitemap_url):
                    sitemap_links.append(sitemap_url)
    except Exception as e:
        logger.error(f"Error processing robots.txt at {robots_url}: {e}")
    return sitemap_links

def find_sitemap(domain):
    possible_sitemaps = [
        f"{domain}/sitemap.xml",
        f"{domain}/sitemap.xml.gz",
        f"{domain}/sitemap_index.xml",
        f"{domain}/sitemap_index.xml.gz",
        f"{domain}/sitemap.txt",
        f"{domain}/sitemap.txt.gz"
    ]
    
    for sitemap in possible_sitemaps:
        if is_valid_sitemap(sitemap):
            return sitemap

    robots_sitemaps = parse_robots_for_sitemaps(domain)
    if robots_sitemaps:
        return robots_sitemaps[0]
    
    return None

def extract_urls_from_sitemap(sitemap_url, visited=None):
    if visited is None:
        visited = set()

    if sitemap_url in visited:
        return set()
    visited.add(sitemap_url)
    
    urls = set()
    content = _get_content(sitemap_url)
    if not content:
        return urls
    if sitemap_url.endswith('.txt') or sitemap_url.endswith('.txt.gz'):
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("http"):
                urls.add(line)
        return urls
    try:
        root = ET.fromstring(content)
        if root.tag.endswith("sitemapindex"):
            for sitemap in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap"):
                loc = sitemap.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
                if loc is not None and loc.text:
                    urls.update(extract_urls_from_sitemap(loc.text, visited))
        else:
            for url in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
                loc = url.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
                if loc is not None and loc.text:
                    urls.add(loc.text)
    except ET.ParseError as e:
        logger.error(f"Error parsing XML from {sitemap_url}: {e}")

    return urls
