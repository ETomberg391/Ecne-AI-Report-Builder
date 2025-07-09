<img src="https://github.com/user-attachments/assets/e766db6f-21ce-4d02-a4fc-8050832d0c53" alt="generatedreportExample1" width="48%"><img src="https://github.com/user-attachments/assets/cd608837-dc2d-4e8a-b280-a77bcf494e3b" alt="generatedreportExample2" width="48%">
![image](https://github.com/user-attachments/assets/c7f181e1-2047-4b51-8e41-129601bb89a9)

*API Key in example has already been expired don't worry about it.*

# Ecne Report Builder

Automated AI research report generation. Leverages web research (Google/Brave), local documents (TXT, PDF, DOCX), and Large Language Models (LLMs) to produce structured reports on a given topic.

---

## ✨ Features

*   **Automated Environment Setup:** Includes simple run scripts for both Linux and Windows to handle installation and launch the application.
*   **Web-Based GUI:** A user-friendly web interface for generating reports, managing settings, and monitoring progress.
*   **Flexible Data Sourcing:**
    *   Utilizes web search via Google Custom Search API or Brave Search API.
    *   Accepts direct website URLs for research and sourcing.
    *   Processes local files (`.txt`, `.pdf`, `.docx`) as reference material.
*   **AI-Powered Content Processing:** Employs Large Language Models for discovering sources, summarizing content, and generating a final, structured research report.
*   **Configurable LLM Backend:** Supports any OpenAI-API compatible endpoints.
*   **Detailed Archiving:** Creates a timestamped archive for each report, storing logs, intermediate summaries, and the final report in both `.txt` and `.pdf` formats.

---

## 🚀 Installation and Running

The recommended way to use the Ecne Report Builder is via the Web GUI.

### For Linux

1.  Make the script executable:
    ```bash
    chmod +x run_main.sh
    ```
2.  Run the script:
    ```bash
    ./run_main.sh
    ```
    The script will handle dependency installation and automatically open the web interface in your browser.

### For Windows

1.  Right-click `Install.bat` and select "Run as administrator" to install the necessary dependencies.
2.  Once the installation is complete, run `run_app.bat` to start the application. This will open the web interface in your browser.

### Web GUI Usage

1.  Once the application is running, it will open a tab in your web browser.
2.  Navigate to the **Settings** page to configure your Search API (Brave/Google) and LLM API keys.
3.  Return to the **Main** page.
4.  Use the "AI Easy Mode" to help build your topic, search keywords, and guidance.
5.  Press **Generate Report**. The process can take anywhere from 10 to 45 minutes.
6.  The final report will be generated in both `.txt` and `.pdf` formats.

---

## 🛠️ Direct Command-Line Usage

For advanced users, the `report_builder.py` script can be run directly from the command line.

First, activate the virtual environment:
*   **Linux:** `source host_venv/bin/activate`
*   **Windows:** `host_venv\Scripts\activate.bat`

Then, use the following commands:

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
*   `selenium`: For browser automation.

**External Tools:**

*   Git
*   Python 3 & Pip

---

## 📜 License

Licensed under Apache 2.0
