import logging
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_content_filter(threshold=0.5, min_word_threshold=50, threshold_type="fixed"):
    try:
        content_filter = PruningContentFilter(
            threshold=threshold,
            threshold_type=threshold_type,
            min_word_threshold=min_word_threshold
        )
        logger.info("Content filter created successfully with threshold=%s, min_word_threshold=%s, threshold_type=%s",
                    threshold, min_word_threshold, threshold_type)
        return content_filter
    except Exception as e:
        logger.error("Error creating content filter: %s", e)
        raise

def create_markdown_generator(content_filter, options=None):
    default_options = {
        "ignore_links": True,
        "ignore_images": True,
        "escape_html": True,
        "body_width": 80,
        "skip_internal_links": True,
        "include_sup_sub": True
    }
    if options:
        default_options.update(options)

    try:
        markdown_generator = DefaultMarkdownGenerator(
            content_filter=content_filter,
            options=default_options
        )
        logger.info("Markdown generator created successfully with options: %s", default_options)
        return markdown_generator
    except Exception as e:
        logger.error("Error creating markdown generator: %s", e)
        raise
