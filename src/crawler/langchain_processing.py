import os
import logging
import json
from datetime import datetime
from langchain_community.document_loaders import BSHTMLLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROCESSED_DIR = os.path.join("data", "results", "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

def load_and_clean_html(file_path):
    try:
        loader = BSHTMLLoader(file_path)
        documents = loader.load()
        if documents:
            cleaned_content = documents[0].page_content
            logger.info(f"Loaded and cleaned content from {file_path}")
            return cleaned_content
        else:
            raise ValueError("No document loaded.")
    except Exception as e:
        logger.error(f"Error loading or cleaning HTML content from {file_path}: {e}")
        raise

def chunk_content(content, chunk_size=6000, chunk_overlap=1200):
    try:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        chunks = text_splitter.split_text(content)
        logger.info(f"Content chunked into {len(chunks)} parts")
        return chunks
    except Exception as e:
        logger.error(f"Error chunking content: {e}")
        raise

def enrich_with_metadata(chunks, url, title, timestamp=None):
    try:
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        enriched_chunks = []
        for chunk in chunks:
            enriched_chunk = {
                "content": chunk,
                "url": url,
                "title": title,
                "timestamp": timestamp
            }
            enriched_chunks.append(enriched_chunk)
        logger.info("Metadata enriched for content chunks")
        return enriched_chunks
    except Exception as e:
        logger.error(f"Error enriching content with metadata: {e}")
        raise

def save_processed_data(data, output_filename):
    output_path = os.path.join(PROCESSED_DIR, output_filename)
    try:
        if os.path.exists(output_path):
            with open(output_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            combined_data = existing_data + data  
        else:
            combined_data = data
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(combined_data, f, ensure_ascii=False, indent=4)
        logger.info(f"Processed data saved to {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error saving processed data to {output_path}: {e}")
        raise

def process_html_file(file_path, url, title, timestamp=None, minio_client=None, bucket_name=None):
    try:
        cleaned_content = load_and_clean_html(file_path)
        chunks = chunk_content(cleaned_content)
        enriched_data = enrich_with_metadata(chunks, url, title, timestamp)
        
        base = os.path.basename(file_path).replace(".html", "")
        output_filename = f"{base}-processed.json"
        save_processed_data(enriched_data, output_filename)
        
        logger.info(f"Processing completed for {file_path}")
        return enriched_data
    except Exception as e:
        logger.error(f"Error processing HTML file {file_path}: {e}")
        raise
