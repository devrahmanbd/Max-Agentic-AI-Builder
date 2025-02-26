[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![Unlicense License][license-shield]][license-url]

<div align="center">
  <a href="https://github.com/devrahmanbd/Max-Agentic-AI-Builder">
    <img src="images/max.png" alt="Logo" width="80" height="80">
  </a>

  <h3 align="center">Max Agentic AI Builder</h3>

  <p align="center">
    An end-to-end, agentic workflow for intelligent data crawling, processing, and semantic content generation.
    <br />
    <a href="https://github.com/devrahmanbd/Max-Agentic-AI-Builder"><strong>Explore the docs »</strong></a>
    <br /><br />
    <a href="https://github.com/devrahmanbd/Max-Agentic-AI-Builder/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    ·
    <a href="https://github.com/devrahmanbd/Max-Agentic-AI-Builder/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#features">Features</a></li>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#workflow">Workflow</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

## About The Project

Max Agentic AI Builder is a fully automated system engineered to crawl, process, and generate semantic, SEO-optimized content with minimal human intervention. By combining state-of-the-art web crawling (via Crawl4AI), dynamic proxy and rate limit handling, and advanced text processing with LangChain, the project transforms raw web data into enriched, vector-ready documents. These documents are then primed for retrieval-augmented generation (RAG) and semantic content creation.

### Features
- **Automated Crawling & Extraction:**  
  Utilize asynchronous web crawling to efficiently scrape pages and extract valuable content.
- **Dynamic Proxy & Rate Limit Bypass:**  
  Seamlessly rotate proxies and employ exponential backoff to bypass restrictions and avoid rate limiting.
- **Progress & Error Management:**  
  Maintain a resumable workflow with continuous updates in `progress.json` and real-time Telegram notifications.
- **Content Processing & Enrichment:**  
  Clean, chunk, and enrich HTML content using LangChain techniques for downstream semantic processing.
- **MinIO Data Sync:**  
  Automatically sync raw and processed data to a MinIO bucket for persistent storage and versioning.
- **Extensible for RAG Pipelines:**  
  Prepare enriched content for vector indexing and retrieval-augmented generation (RAG) with minimal configuration.

### Built With
- [Python 3.13](https://www.python.org/)
- [Crawl4AI](https://pypi.org/project/crawl4ai/)
- [LangChain](https://github.com/hwchase17/langchain)
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [MinIO Python SDK](https://github.com/minio/minio-py)
- [Googlesearch-python](https://github.com/Nv7-GitHub/googlesearch)

## Getting Started

### Prerequisites
- Python 3.13 or higher
- A MinIO server (or S3-compatible storage) for data synchronization
- Telegram Bot credentials for receiving notifications
- Access to reliable proxy servers (if required)
- Required Python packages listed in `requirements.txt`

### Installation
1. **Clone the repository:**
   ```sh
   git clone https://github.com/devrahmanbd/Max-Agentic-AI-Builder.git
   cd Max-Agentic-AI-Builder
   ```
2. **(Optional) Create and activate a virtual environment:**
   ```sh
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
   ```
3. **Install the required dependencies:**
   ```sh
   pip install -r requirements.txt
   ```

## Usage

1. **Prepare your keywords file** (e.g., `./keywords.txt`).
2. **Run the main program:**
   ```sh
   python main.py -k ./keywords.txt -j YourJobName -p ON
   ```
3. **What happens next:**
   - **Google Search:** The program searches Google for each keyword, extracting unique domains and sitemap URLs.
   - **Sitemap & URL Extraction:** It validates and saves sitemap URLs, then generates domain-specific URL files.
   - **Asynchronous Crawling:** The crawler fetches pages concurrently, converts content to Markdown, and processes raw HTML.
   - **Data Enrichment:** The LangChain processor cleans and chunks HTML content, enriching it with metadata.
   - **MinIO Sync:** All raw and processed data are synchronized to a MinIO bucket.
   - **Progress Updates:** Real-time updates and error notifications are sent to your Telegram bot.

## Workflow

1. **Initial Setup & Configuration:**  
   Set up custom headers, proxy settings, and MinIO credentials in `config.py`. The workflow state is continuously tracked in `progress.json`.

2. **Content Discovery & Sitemap Extraction:**  
   Perform keyword-based Google searches with proxy fallback and exponential backoff to handle rate limits. Unique domains and sitemap URLs are extracted and stored.

3. **URL Extraction & Domain File Generation:**  
   Parse sitemaps recursively to extract all page URLs and save them as domain-specific text files.

4. **Asynchronous Web Crawling & Content Extraction:**  
   Use Crawl4AI to crawl URLs concurrently. Extracted content is filtered, converted to Markdown, and saved into domain-specific files.

5. **Data Cleaning & Processing with LangChain:**  
   Load raw HTML, remove unwanted elements, split content into chunks, and enrich it with metadata. Save the processed data in JSON format for further use in RAG pipelines and semantic SEO optimization.

6. **Progress Management & Data Sync:**  
   Update `progress.json` to maintain workflow state and resume capability. Automatically sync processed data and job results to MinIO, while Telegram notifications keep you informed of progress and errors.

## Roadmap

- [ ] Enhance real-time notification reliability and reduce duplicate messages.
- [ ] Improve MinIO sync with granular file tracking and robust error handling.
- [ ] Optimize content filtering and LangChain processing for higher-quality outputs.
- [ ] Implement advanced pagination and proxy fallback for comprehensive Google search results.
- [ ] Integrate vector databases Milvus for efficient RAG pipelines.
- [ ] Add semantic SEO optimization for the generated content.
- [ ] Add FlagEmbedding to perform similarity searches to enhance RAG pipeline

## Contributing

Contributions are what make the open source community an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

Please see the [CONTRIBUTING.md](CONTRIBUTING.md) file for more details.

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Contact

Dev Rahman – [dev@devrahman.com](mailto:dev@devrahman.com)

## Acknowledgments

- [Crawl4AI Documentation](https://docs.crawl4ai.com/)
- [LangChain](https://github.com/hwchase17/langchain)
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [MinIO Python SDK](https://github.com/minio/minio-py)
- [Googlesearch-python](https://github.com/Nv7-GitHub/googlesearch)


<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/devrahmanbd/Max-Agentic-AI-Builder.svg?style=for-the-badge
[contributors-url]: https://github.com/devrahmanbd/Max-Agentic-AI-Builder/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/devrahmanbd/Max-Agentic-AI-Builder.svg?style=for-the-badge
[forks-url]: https://github.com/devrahmanbd/Max-Agentic-AI-Builder/network/members
[stars-shield]: https://img.shields.io/github/stars/devrahmanbd/Max-Agentic-AI-Builder.svg?style=for-the-badge
[stars-url]: https://github.com/devrahmanbd/Max-Agentic-AI-Builder/stargazers
[issues-shield]: https://img.shields.io/github/issues/devrahmanbd/Max-Agentic-AI-Builder.svg?style=for-the-badge
[issues-url]: https://github.com/devrahmanbd/Max-Agentic-AI-Builder/issues
[license-shield]: https://img.shields.io/github/license/devrahmanbd/Max-Agentic-AI-Builder.svg?style=for-the-badge
[license-url]: https://github.com/devrahmanbd/Max-Agentic-AI-Builder/blob/main/LICENSE