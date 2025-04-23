# Ecne Report Builder

Automated AI research report generation. Leverages web research (Google/Brave), local documents (TXT, PDF, DOCX), and Large Language Models (LLMs) to produce structured reports on a given topic.

---

## ✨ Features

*   **Automated Environment Setup:** Includes an `Installer.sh` script to check prerequisites, set up a Python virtual environment, install dependencies, and guide through initial configuration.
*   **Flexible Data Sourcing:**
    *   Utilizes web search via Google Custom Search API or Brave Search API (requires API keys, Google = 100 free requests/day, Brave API = 2,000 free requests/month).
    *   Accepts direct website URLs for scraping.
    *   Processes local files (`.txt`, `.pdf`, `.docx`) as reference material.
*   **AI-Powered Content Processing:** Employs Large Language Models (configurable via `settings/llm_settings/ai_models.yml`) for:
    *   Discovering relevant web sources (optional).
    *   Summarizing scraped web content and local documents.
    *   Scoring summaries based on relevance to the main topic.
    *   Generating a final, structured research report based on the processed context.
*   **Configurable LLM Backend:** Supports any OpenAI-API compatible endpoints, including Google Gemini models in as a recommended reference. Configuration managed in `settings/llm_settings/ai_models.yml`.
*   **Detailed Archiving:** Creates a timestamped archive directory for each run, storing logs, intermediate summaries, AI prompts, and the final report.
*   **Command-Line Interface:** Fully operated via CLI arguments for specifying topics, keywords, sources, and other options.

---

## 🚀 Workflow Overview

1.  **Setup:** Run `Installer.sh` to check dependencies, install required Python packages into a virtual environment (`host_venv`), and set up initial configuration files (`.env`, `ai_models.yml`).
2.  **Configuration:** Edit `.env` and `settings/llm_settings/ai_models.yml` to add necessary API keys (Google, Brave) and select the LLM model configuration.
3.  **Activate Environment:** Activate the Python virtual environment: `source host_venv/bin/activate`.
4.  **Generate Report:** Execute `report_builder.py` with command-line arguments specifying the topic, keywords (or other sources like `--direct-articles`, `--reference-docs`), and any desired options.
5.  **Retrieve Report:** Find the generated `research_report.txt` and other run artifacts inside the `archive/` directory within a timestamped subfolder.

---

## ⚙️ Key Components

*   **`Installer.sh`**:
    *   Checks for core prerequisites (Git, Python 3, Pip).
    *   Detects the Linux distribution or if using Windows 10/11, to attempt installation of optional dependencies like Chrome/ChromeDriver (used by Selenium for some scraping tasks).
    *   Creates the Python virtual environment (`host_venv`).
    *   Installs Python dependencies from `requirements_host.txt`.
    *   Copies `settings/env.example` to `.env` if it doesn't exist.
    *   Interactively prompts the user to configure API keys in `.env` and `settings/llm_settings/ai_models.yml`.
*   **`report_builder.py`**:
    *   The main script that orchestrates the report generation process.
    *   Parses command-line arguments (`argparse`).
    *   Loads configuration (`.env`, `ai_models.yml`).
    *   Manages data gathering:
        *   Calls search APIs (Google/Brave) if configured and not using `--no-search`.
        *   Scrapes web URLs (`newspaper4k`, `requests`, `BeautifulSoup4`, `selenium`).
        *   Loads and parses local documents (`PyPDF2` for PDF, `python-docx` for DOCX, plain text).
    *   Interacts with the configured LLM API for:
        *   Source discovery (optional).
        *   Content summarization and relevance scoring.
        *   Final report generation.
    *   Handles detailed logging and archiving of run artifacts.
*   **Configuration Files**:
    *   `.env`: Stores API keys (Google, Brave, Reddit - though Reddit usage seems less primary now), and the `DEFAULT_MODEL_CONFIG` key pointing to `ai_models.yml`.
    *   `settings/llm_settings/ai_models.yml`: Defines configurations for different LLM models (API endpoint, key, model name, parameters like temperature).

---

## 🛠️ Setup

### Prerequisites

*   Linux-based OS (Installer attempts OS detection for package managers like `apt`, `yum`, `pacman`, `zypper`). (Working on Windows 10/11 compatibility)
*   Git
*   Python 3.8+ & Pip
*   **(Optional)** Google Chrome/Chromium and matching ChromeDriver for Selenium features (Installer attempts to handle this).
*   **(Optional)** API Keys for:
    *   Google Custom Search (API Key & CSE ID)
    *   Brave Search API
    *   Your chosen LLM provider (e.g., Google AI Studio for Gemini, OpenAI)

### Installation Steps

1.  **Clone the Repository:**
    ```bash
    git clone Ecne-AI-Report-Builder
    cd Ecne_report_builder 
    ```

2.  **Run the Installer:**
    *   Make the installer executable:
        ```bash
        chmod +x Installer.sh
        ```
    *   Execute the installer script:
        ```bash
        ./Installer.sh
        ```
    *   The script will check for prerequisites. Follow the prompts to install any missing dependencies and configure your API keys in the `.env` and `ai_models.yml` files when prompted.

---

## ▶️ Usage

1.  **Activate Host Virtual Environment:**
    ```bash
    source host_venv/bin/activate
    ```

2.  **Generate a Report:**
    *   **Basic Web Search:**
        ```bash
        python report_builder.py --topic "Artificial Intelligence in Healthcare" --keywords "AI diagnostics, machine learning drug discovery, predictive analytics patient care"
        ```
    *   **Using Local Reference Documents Folder (Skipping Web Search):**
        ```bash
        python report_builder.py --topic "Analysis of Provided Documents on Feline Behavior" --reference-docs-folder research/cat_papers --no-search
        ```
    *   **Using Specific URLs:**
        ```bash
        python report_builder.py --topic "Summary of Recent Tech Articles" --no-search --direct-articles research/articles_list.txt
        # (Where articles_list.txt contains one URL per line)
        ```
    *   **Specifying a Different LLM Configuration (from `ai_models.yml`):**
        ```bash
        python report_builder.py --topic "Quantum Computing Basics" --keywords "qubits, superposition, entanglement" --llm-model gemini_flash
        ```
    *   **Adding Extra Instructions for the LLM:**
        ```bash
        python report_builder.py --topic "Impact of Social Media on Teenagers" --keywords "mental health, screen time, cyberbullying" --guidance "Focus specifically on studies published in the last 3 years and mention potential positive impacts too."
        ```

3.  **Check Output:** Look for the `research_report.txt` file inside the `archive/` directory in the latest timestamped folder.

4.  **Deactivate Environment:**
    ```bash
    deactivate
    ```

---

## 🔌 Dependencies & Credits

**Core Python Libraries (see `requirements_host.txt`):**

*   `requests`: For making HTTP requests to APIs and websites.
*   `python-dotenv`: For loading environment variables from `.env`.
*   `PyYAML`: For parsing YAML configuration files (`ai_models.yml`).
*   `beautifulsoup4`: Used indirectly or directly for HTML parsing during scraping.
*   `newspaper4k`: For article scraping and metadata extraction.
*   `PyPDF2`: For extracting text from PDF documents.
*   `python-docx`: For extracting text from DOCX documents.
*   `selenium`: For browser automation (used for some complex scraping tasks, e.g., potentially Reddit).

**External Tools:**

*   Git
*   Python 3 & Pip

**Optional Tools/APIs:**

*   Google Chrome/Chromium & ChromeDriver
*   Google Custom Search API
*   Brave Search API
*   OpenAI-compatible LLM API

---

## 📜 License

Licensed under Apache 2.0