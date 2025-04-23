import os
import datetime
import json
import re
import requests
import time
import random
import argparse
import yaml
import urllib.parse
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from newspaper import Article, ArticleException # Using newspaper4k for better web scraping
import PyPDF2 # Renamed from pypdf - assuming PyPDF2 is intended or needs update
import docx
# Removed PRAW import, adding Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager # Added to manage chromedriver install

# --- Constants & Configuration ---

# User agents for requests/scraping
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
]

# Global variable for archive directory (set in main)
run_archive_dir = None
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # Use absolute path
LLM_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "settings/llm_settings")) # Define LLM_DIR

# --- Utility Functions ---

def log_to_file(content):
    """Helper to write detailed logs to the run-specific archive directory."""
    global run_archive_dir
    if run_archive_dir:
        # Use a consistent log filename within the archive
        log_file = os.path.join(run_archive_dir, f"run_{os.path.basename(run_archive_dir)}.log")
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n[{datetime.datetime.now().isoformat()}] {content}\n")
        except IOError as e:
            print(f"Warning: Could not write to log file {log_file}: {e}")
            # Silently fail if we can't write logs after warning

def load_config():
    """Loads configuration from .env file and ai_models.yml."""
    # Try loading .env from script directory first, then current working directory
    dotenv_path_script = os.path.join(SCRIPT_DIR, '.env')
    dotenv_path_cwd = os.path.join(os.getcwd(), '.env')

    if os.path.exists(dotenv_path_script):
        load_dotenv(dotenv_path=dotenv_path_script)
        print(f"Loaded .env from script directory: {dotenv_path_script}")
    elif os.path.exists(dotenv_path_cwd):
        load_dotenv(dotenv_path=dotenv_path_cwd)
        print(f"Loaded .env from current working directory: {dotenv_path_cwd}")
    else:
        print("Warning: .env file not found in script directory or current working directory.")

    config = {
        "google_api_key": os.getenv("GOOGLE_API_KEY"),
        "google_cse_id": os.getenv("GOOGLE_CSE_ID"),
        "brave_api_key": os.getenv("BRAVE_API_KEY"),
        "reddit_client_id": os.getenv("REDDIT_CLIENT_ID"),
        "reddit_client_secret": os.getenv("REDDIT_CLIENT_SECRET"),
        "reddit_user_agent": os.getenv("REDDIT_USER_AGENT"),
    }

    # --- Load Model Configurations ---
    models_config_path = os.path.join(LLM_DIR, 'ai_models.yml')
    models_config = {} # Initialize as empty dict
    try:
        with open(models_config_path, 'r', encoding='utf-8') as f:
            models_config = yaml.safe_load(f)
        if not models_config or not isinstance(models_config, dict):
             raise ValueError("ai_models.yml is empty or not a valid dictionary.")
        print(f"Loaded model configurations from {models_config_path}")
    except FileNotFoundError:
        print(f"Error: Model configuration file not found at {models_config_path}")
        # Allow script to continue if models are not needed, but warn
        print("Warning: Proceeding without model configurations. LLM features will fail.")
    except (yaml.YAMLError, ValueError) as e:
        print(f"Error parsing model configuration file {models_config_path}: {e}")
        exit(1) # Exit if config is malformed

    # --- Basic Validation ---
    google_ok = config.get("google_api_key") and config.get("google_cse_id")
    brave_ok = config.get("brave_api_key")
    if not google_ok and not brave_ok:
         print("Warning: Neither Google (API Key + CSE ID) nor Brave API Key are set. Web search may fail.")
    reddit_ok = all(config.get(k) for k in ["reddit_client_id", "reddit_client_secret", "reddit_user_agent"])
    if not reddit_ok:
        print("Warning: Reddit credentials (client_id, client_secret, user_agent) missing. Reddit scraping via Selenium will be used.")

    print("Configuration loading process complete.")
    return config, models_config

def clean_thinking_tags(text):
    """Recursively remove all content within <think>...</think> tags."""
    if text is None: return ""
    prev_text = ""
    current_text = str(text) # Ensure it's a string
    while prev_text != current_text:
        prev_text = current_text
        current_text = re.sub(r'<think>.*?</think>', '', prev_text, flags=re.IGNORECASE | re.DOTALL)
    return current_text.strip()

def parse_ai_tool_response(response_text, tool_tag):
    """
    Parses content within the *last* occurrence of specific <toolTag>...</toolTag> markers
    after cleaning thinking tags.
    """
    cleaned_text = clean_thinking_tags(response_text)
    if not cleaned_text: return ""

    open_tag = f'<{tool_tag}>'
    close_tag = f'</{tool_tag}>'
    # Case-insensitive search for tags
    open_tag_lower = open_tag.lower()
    close_tag_lower = close_tag.lower()
    cleaned_text_lower = cleaned_text.lower()

    last_open_tag_index = cleaned_text_lower.rfind(open_tag_lower)

    if last_open_tag_index != -1:
        search_start_index = last_open_tag_index + len(open_tag)
        first_close_tag_index_after_last_open = cleaned_text_lower.find(close_tag_lower, search_start_index)

        if first_close_tag_index_after_last_open != -1:
            start_content_index = last_open_tag_index + len(open_tag)
            # Use the found indices on the original case string to preserve content casing
            content = cleaned_text[start_content_index:first_close_tag_index_after_last_open]
            return content.strip()
        else:
            log_msg = f"Warning: Found last '{open_tag}' but no subsequent '{close_tag}'. Returning full cleaned response."
            print(f"\n{log_msg}")
            log_to_file(f"{log_msg}\nResponse was:\n{cleaned_text}")
            return cleaned_text # Fallback
    else:
        log_msg = f"Warning: Tool tag '{open_tag}' not found in AI response. Returning full cleaned response."
        print(f"\n{log_msg}")
        log_to_file(f"{log_msg}\nResponse was:\n{cleaned_text}")
        return cleaned_text # Fallback

# --- AI Interaction ---

def call_ai_api(prompt, config, tool_name="General", timeout=300):
    """Generic function to call the OpenAI-compatible API."""
    print(f"\nSending {tool_name} request to AI...")
    log_to_file(f"Initiating API Call (Tool: {tool_name})")

    model_config = config.get("selected_model_config")
    if not model_config:
        final_model_key = config.get('final_model_key', 'N/A')
        print(f"Error: Selected model configuration ('{final_model_key}') not found in loaded config. Cannot call API.")
        log_to_file(f"API Call Error: selected_model_config missing for key '{final_model_key}'.")
        return None, None

    api_key = model_config.get("api_key")
    api_endpoint = model_config.get("api_endpoint")

    if not api_key or not api_endpoint:
        final_model_key = config.get('final_model_key', 'N/A')
        print(f"Error: 'api_key' or 'api_endpoint' missing in the selected model configuration ('{final_model_key}') within ai_models.yml")
        log_to_file(f"API Call Error: api_key or api_endpoint missing for model key '{final_model_key}'.")
        return None, None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model_config.get("model"),
        "messages": [{"role": "user", "content": prompt}],
    }
    # Add optional parameters from YAML if they exist and are not None
    # Ensure type casting for safety
    def add_if_present(key, cast_func):
        if model_config.get(key) is not None:
            try:
                payload[key] = cast_func(model_config[key])
            except (ValueError, TypeError) as e:
                 print(f"Warning: Could not cast model config '{key}' value '{model_config[key]}' to {cast_func.__name__}. Skipping parameter. Error: {e}")
                 log_to_file(f"API Payload Warning: Could not cast '{key}' value '{model_config[key]}'. Skipping.")

    add_if_present("temperature", float)
    add_if_present("max_tokens", int)
    add_if_present("top_p", float)
    add_if_present("top_k", int) # Example of adding another common parameter

    if not payload.get("model"):
         print(f"Error: 'model' key is missing in the final payload construction for config '{config.get('final_model_key', 'N/A')}'.")
         log_to_file("API Call Error: 'model' key missing in payload.")
         return None, None

    log_to_file(f"API Call Details:\nEndpoint: {api_endpoint}\nPayload: {json.dumps(payload, indent=2)}")

    try:
        # Ensure endpoint doesn't already end with the completions path
        if api_endpoint.endswith("/chat/completions"):
             full_api_url = api_endpoint
        else:
             full_api_url = api_endpoint.rstrip('/') + "/chat/completions"

        response = requests.post(full_api_url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()

        result = response.json()
        log_to_file(f"Raw API Response:\n{json.dumps(result, indent=2)}")

        if not result.get("choices"): raise ValueError("No 'choices' field in API response.")
        if not result["choices"][0].get("message"): raise ValueError("No 'message' field in the first choice.")
        message_content = result["choices"][0]["message"].get("content")
        if message_content is None: raise ValueError("'content' field is missing in the message.") # Check for None specifically

        print(f"{tool_name} response received.")
        cleaned_message = clean_thinking_tags(message_content)
        return message_content, cleaned_message

    except requests.exceptions.Timeout:
        error_msg = f"Error calling AI API: Timeout after {timeout} seconds."
        print(f"\n{tool_name} request failed (Timeout).")
        log_to_file(error_msg)
        return None, None
    except requests.exceptions.HTTPError as e:
        error_msg = f"Error calling AI API (HTTP {e.response.status_code}): {e}"
        try: # Try to get response body for more info
            error_body = e.response.text
            error_msg += f"\nResponse Body: {error_body}"
        except Exception: error_body = "Could not read response body."
        print(f"\n{tool_name} request failed ({e.response.status_code}). Check logs for details.")
        log_to_file(error_msg)
        # Rate Limit Handling (429) - Simple retry once
        if e.response.status_code == 429:
            wait_time = 61
            print(f"Rate limit likely hit (429). Waiting for {wait_time} seconds before retrying once...")
            log_to_file(f"Rate limit hit (429). Waiting {wait_time}s and retrying.")
            time.sleep(wait_time)
            print(f"Retrying {tool_name} request...")
            try:
                response = requests.post(full_api_url, headers=headers, json=payload, timeout=timeout)
                response.raise_for_status()
                result = response.json()
                log_to_file(f"Raw API Response (Retry Attempt):\n{json.dumps(result, indent=2)}")
                if not result.get("choices"): raise ValueError("No 'choices' field in API response (Retry).")
                if not result["choices"][0].get("message"): raise ValueError("No 'message' field in the first choice (Retry).")
                message_content = result["choices"][0]["message"].get("content")
                if message_content is None: raise ValueError("'content' field is missing in the message (Retry).")
                print(f"{tool_name} response received (after retry).")
                cleaned_message = clean_thinking_tags(message_content)
                return message_content, cleaned_message
            except requests.exceptions.RequestException as retry_e:
                error_msg_retry = f"Error calling AI API on retry: {retry_e}"
                print(f"\n{tool_name} request failed on retry.")
                log_to_file(error_msg_retry)
                return None, None
            except (ValueError, KeyError, IndexError, TypeError) as retry_parse_e:
                error_msg_retry = f"Error parsing AI API response on retry: {retry_parse_e}"
                print(f"\n{tool_name} response parsing failed on retry.")
                log_to_file(f"{error_msg_retry}\nRaw Response (Retry, if available):\n{result if 'result' in locals() else 'N/A'}")
                return None, None
            except Exception as retry_fatal_e:
                 error_msg_retry = f"An unexpected error occurred during AI API call retry: {retry_fatal_e}"
                 print(f"\n{tool_name} request failed unexpectedly on retry.")
                 log_to_file(error_msg_retry)
                 return None, None
        else: # Different HTTP error, fail
            return None, None
    except requests.exceptions.RequestException as e:
        error_msg = f"Error calling AI API: {e}"
        print(f"\n{tool_name} request failed.")
        log_to_file(error_msg)
        return None, None
    except (ValueError, KeyError, IndexError, TypeError) as e: # Added TypeError
        error_msg = f"Error parsing AI API response: {e}"
        print(f"\n{tool_name} response parsing failed.")
        log_to_file(f"{error_msg}\nRaw Response (if available):\n{result if 'result' in locals() else 'N/A'}")
        return None, None
    except Exception as e:
        error_msg = f"An unexpected error occurred during AI API call: {e}"
        print(f"\n{tool_name} request failed (Unexpected).")
        log_to_file(error_msg)
        return None, None

# --- Argument Parsing ---

def parse_arguments():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate an AI research report.")

    # --- Load model keys dynamically for choices ---
    available_model_keys = []
    models_config_path = os.path.join(LLM_DIR, 'ai_models.yml')
    try:
        with open(models_config_path, 'r', encoding='utf-8') as f:
            models_config = yaml.safe_load(f)
        if models_config and isinstance(models_config, dict):
            available_model_keys = list(models_config.keys())
    except Exception as e:
        print(f"Warning: Error loading {models_config_path} for arg parsing: {e}. --llm-model choices might be incomplete.")
    # --- End model key loading ---

    # --- Define Arguments ---
    parser.add_argument("--keywords", type=str, default=None, help="Comma-separated keywords/phrases for searching (required unless --no-search is used).")
    parser.add_argument("--topic", type=str, required=True, help="The main topic phrase for the research report.")
    parser.add_argument("--llm-model", type=str, default=None, choices=available_model_keys if available_model_keys else None,
                        help="Specify the LLM configuration key from ai_models.yml to use (overrides .env setting).")
    parser.add_argument("--api", choices=['google', 'brave'], default='google', help="Preferred search API ('google' or 'brave').")
    parser.add_argument("--from_date", type=str, default=None, help="Start date for search (YYYY-MM-DD).")
    parser.add_argument("--to_date", type=str, default=None, help="End date for search (YYYY-MM-DD).")
    parser.add_argument("--max-web-results", type=int, default=3, help="Max results per website source domain.")
    parser.add_argument("--max-reddit-results", type=int, default=5, help="Max *posts* to scrape per subreddit source.")
    parser.add_argument("--max-reddit-comments", type=int, default=5, help="Max *comments* to scrape per Reddit post.")
    parser.add_argument("--per-keyword-results", type=int, default=None, help="Web results per keyword (defaults to max-web-results).")
    parser.add_argument("--combine-keywords", action="store_true", help="Treat keywords as one search query.")
    parser.add_argument("--score-threshold", type=int, default=5, help="Minimum summary score (0-10) to include in report context.")
    parser.add_argument("--guidance", type=str, default=None, help="Additional guidance/instructions string for the LLM report generation prompts.")
    parser.add_argument("--direct-articles", type=str, default=None, help="Path to a text file containing a list of article URLs (one per line) to scrape directly.")
    parser.add_argument("--no-search", action="store_true", help="Skip AI source discovery and web search APIs. Requires --direct-articles OR --reference-docs OR --reference-docs-folder.")
    parser.add_argument("--reference-docs", type=str, default=None, help="Comma-separated paths to files (txt, pdf, docx) containing reference information.")
    parser.add_argument("--reference-docs-summarize", action="store_true", help="Summarize and score reference docs before including them in report context.")
    parser.add_argument("--reference-docs-folder", type=str, default=None, help="Path to a folder containing reference documents (txt, pdf, docx).")
    # Added argument to skip refinement
    parser.add_argument("--skip-refinement", action="store_true", help="Skip the final report refinement step.")

    args = parser.parse_args()

    if args.per_keyword_results is None: args.per_keyword_results = args.max_web_results

    search_queries = []
    if args.keywords:
        raw_keywords = [k.strip() for k in args.keywords.split(',') if k.strip()]
        if not raw_keywords: raise ValueError("Please provide at least one keyword if using --keywords.")
        if args.combine_keywords:
            search_queries = [" ".join(raw_keywords)]
            print("Keywords combined into a single search query.")
        else:
            search_queries = raw_keywords
            print(f"Processing {len(search_queries)} separate search queries.")
    elif not args.no_search:
         parser.error("--keywords is required unless --no-search is specified.")

    def validate_date(date_str):
        if date_str is None: return None
        try:
            datetime.datetime.strptime(date_str, '%Y-%m-%d')
            return date_str
        except ValueError:
            raise ValueError(f"Invalid date format '{date_str}'. Use YYYY-MM-DD.")
    args.from_date = validate_date(args.from_date)
    args.to_date = validate_date(args.to_date)

    args.search_queries = search_queries
    print(f"Parsed Args: {vars(args)}")

    if args.no_search and not args.direct_articles and not args.reference_docs and not args.reference_docs_folder:
        parser.error("--no-search requires at least one of --direct-articles, --reference-docs, or --reference-docs-folder.")

    return args


# --- Research Phase ---

def discover_sources(keywords_list, config):
    """Uses AI to discover relevant websites and subreddits."""
    print("\nDiscovering sources via AI...")
    discovery_keyword_str = " | ".join(keywords_list)
    print(f"Using keywords for discovery: '{discovery_keyword_str}'")

    prompt = (
        f"Based on the keywords '{discovery_keyword_str}', suggest relevant information sources. "
        f"Include specific websites (news sites, reputable blogs, official project sites) and relevant subreddits. "
        f"Prioritize sources known for reliable, detailed information on this topic.\n"
        f"Format your response strictly within <toolWebsites> tags, listing each source URL or subreddit name (e.g., 'r/technology' or 'techcrunch.com') on a new line.\n"
        f"Example:\n<toolWebsites>\ntechcrunch.com\nwired.com\nexampleblog.net/relevant-section\nr/artificial\nr/machinelearning\n</toolWebsites>"
    )

    raw_response, cleaned_response = call_ai_api(prompt, config, tool_name="SourceDiscovery")
    if not cleaned_response:
        log_to_file("Error: No response received from AI API for source discovery.")
        return []

    sources_str = parse_ai_tool_response(cleaned_response, "toolWebsites")
    if not sources_str or sources_str == cleaned_response:
        log_to_file("Error: Could not parse <toolWebsites> tag in source discovery response.")
        return []

    sources_list_raw = [line.strip() for line in sources_str.split('\n') if line.strip()]
    sources_list = []
    for line in sources_list_raw:
        cleaned_line = re.sub(r'\s*\(.*\)\s*$', '', line).strip()
        if cleaned_line:
            # Basic validation/normalization
            if '.' in cleaned_line and not cleaned_line.startswith(('http://', 'https://', 'r/')):
                 # Prefer https for websites if no scheme given
                cleaned_line = f"https://{cleaned_line}"
            # Check if it looks like a URL or subreddit format
            if cleaned_line.startswith(('http://', 'https://', 'r/')):
                 sources_list.append(cleaned_line)
            else:
                 log_to_file(f"Source Discovery Warning: Ignoring potentially invalid source format: {cleaned_line}")

    if not sources_list:
        log_to_file(f"Warning: No valid sources extracted after parsing.\nParsed content: {sources_str}")
        return []

    print(f"Discovered {len(sources_list)} potential sources. Validating access...")
    # --- Source Validation (Optional but recommended) ---
    validated_sources = []
    for source in sources_list:
        is_valid = False
        print(f"  - Checking: {source}...", end="")
        try:
            if source.startswith('r/'): # Assume valid if AI suggested
                is_valid = True
                print(" OK (Subreddit)")
            else: # Check website HEAD request
                # url_to_check = source if source.startswith(('http://', 'https://')) else f'http://{source}' # Already normalized above
                url_to_check = source
                response = requests.head(url_to_check, headers={'User-Agent': random.choice(USER_AGENTS)}, timeout=10, allow_redirects=True)
                if response.status_code < 400:
                    is_valid = True
                    print(f" OK (Status: {response.status_code})")
                else:
                    print(f" Failed (Status: {response.status_code})")
        except requests.exceptions.RequestException as e:
             # Catch connection errors, SSL errors etc.
             # Treat as invalid for scraping purposes
             print(f" Failed (Error: {type(e).__name__})") # Log error type
        except Exception as e:
            print(f" Failed (Unexpected Validation Error: {e})")

        if is_valid:
            validated_sources.append(source)
        time.sleep(random.uniform(0.3, 0.8)) # Short delay

    print(f"Validation complete. Using {len(validated_sources)} accessible sources.")
    log_to_file(f"Source Discovery: Validated {len(validated_sources)} sources: {validated_sources}")
    return validated_sources


# --- Search API Functions ---

def search_google_api(query, config, num_results, from_date=None, to_date=None):
    """Performs search using Google Custom Search API."""
    urls = []
    api_key = config.get("google_api_key")
    cse_id = config.get("google_cse_id")
    if not api_key or not cse_id:
        log_to_file("Google API search skipped: API Key or CSE ID missing.")
        return None

    search_url = "https://www.googleapis.com/customsearch/v1"
    # Add date ranges using Google's `sort=date:r:YYYYMMDD:YYYYMMDD` parameter
    date_restrict = ""
    if from_date:
        try:
            from_dt_str = datetime.datetime.strptime(from_date, '%Y-%m-%d').strftime('%Y%m%d')
            to_dt_str = datetime.datetime.strptime(to_date, '%Y-%m-%d').strftime('%Y%m%d') if to_date else datetime.datetime.now().strftime('%Y%m%d')
            date_restrict = f"date:r:{from_dt_str}:{to_dt_str}"
        except ValueError:
             print(f"  - Warning: Invalid date format for Google search '{from_date}' or '{to_date}'. Ignoring date range.")
             log_to_file(f"Google API Warning: Invalid date format '{from_date}'/'{to_date}'. Ignoring date range.")

    print(f"  - Searching Google API: '{query}' (Num: {num_results}, Date: '{date_restrict or 'None'}')")
    log_to_file(f"Google API Search: Query='{query}', Num={num_results}, DateRestrict='{date_restrict}'")

    params = {'key': api_key, 'cx': cse_id, 'q': query, 'num': min(num_results, 10)}
    if date_restrict:
        params['sort'] = date_restrict # Add sort parameter for date range

    try:
        response = requests.get(search_url, params=params, timeout=20)
        response.raise_for_status()
        search_data = response.json()

        if 'items' in search_data:
            urls = [item['link'] for item in search_data['items'] if 'link' in item]
            print(f"    - Google Found: {len(urls)} results.")
            log_to_file(f"Google API Success: Found {len(urls)} URLs.")
        else:
            print("    - Google Found: 0 results.")
            log_to_file("Google API Success: No items found in response.")

        if 'error' in search_data and search_data['error'].get('code') == 429:
             print("    - !! Google API Quota limit likely reached !!")
             log_to_file("Google API Error: Quota limit reached (429 in response body).")
             return 'quota_error'
        return urls

    except requests.exceptions.HTTPError as e:
        print(f"    - Error calling Google API: {e}")
        log_to_file(f"Google API HTTP Error: {e}")
        if e.response.status_code == 429:
            print("    - !! Google API Quota limit likely reached (HTTP 429) !!")
            log_to_file("Google API Error: Quota limit reached (HTTP 429).")
            return 'quota_error'
        return None
    except requests.exceptions.RequestException as e:
        print(f"    - Error calling Google API: {e}")
        log_to_file(f"Google API Request Error: {e}")
        return None
    except Exception as e:
        print(f"    - Unexpected error during Google API search: {e}")
        log_to_file(f"Google API Unexpected Error: {e}")
        return None
    finally:
        time.sleep(random.uniform(1, 2)) # Delay

def search_brave_api(query, config, num_results, from_date=None, to_date=None):
    """Performs search using Brave Search API."""
    urls = []
    api_key = config.get("brave_api_key")
    if not api_key:
        log_to_file("Brave API search skipped: API Key missing.")
        return None

    search_url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"Accept": "application/json", "Accept-Encoding": "gzip", "X-Subscription-Token": api_key}
    freshness_param = None

    if from_date:
        try:
            from_dt = datetime.datetime.strptime(from_date, '%Y-%m-%d')
            freshness_start = from_dt.strftime('%Y%m%d')
            freshness_end = ""
            if to_date:
                to_dt = datetime.datetime.strptime(to_date, '%Y-%m-%d')
                freshness_end = to_dt.strftime('%Y%m%d')
            freshness_param = f"pd:{freshness_start},{freshness_end}"
        except ValueError:
            print(f"  - Warning: Invalid date format for Brave freshness '{from_date}' or '{to_date}'. Skipping date filter.")
            log_to_file(f"Brave API Warning: Invalid date format '{from_date}'/'{to_date}' for freshness.")

    print(f"  - Searching Brave API: '{query}' (Num: {num_results}, Freshness: '{freshness_param or 'None'}')")
    log_to_file(f"Brave API Search: Query='{query}', Num={num_results}, Freshness='{freshness_param}'")

    params = {'q': query, 'count': num_results}
    if freshness_param: params['freshness'] = freshness_param

    try:
        response = requests.get(search_url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        search_data = response.json()

        if 'web' in search_data and 'results' in search_data['web']:
            urls = [item['url'] for item in search_data['web']['results'] if 'url' in item]
            print(f"    - Brave Found: {len(urls)} results.")
            log_to_file(f"Brave API Success: Found {len(urls)} URLs.")
        else:
            print("    - Brave Found: 0 results.")
            log_to_file(f"Brave API Success: No web/results found in response. Keys: {search_data.keys()}")
        return urls

    except requests.exceptions.HTTPError as e:
        print(f"    - Error calling Brave API: {e}")
        log_to_file(f"Brave API HTTP Error: {e}")
        if e.response.status_code == 429:
             print("    - !! Brave API Quota limit likely reached (HTTP 429) !!")
             log_to_file("Brave API Error: Quota limit reached (HTTP 429).")
             return 'quota_error'
        return None
    except requests.exceptions.RequestException as e:
        print(f"    - Error calling Brave API: {e}")
        log_to_file(f"Brave API Request Error: {e}")
        return None
    except Exception as e:
        print(f"    - Unexpected error during Brave API search: {e}")
        log_to_file(f"Brave API Unexpected Error: {e}")
        return None
    finally:
        time.sleep(random.uniform(1, 2)) # Delay

# --- Content Scraping ---

def scrape_website_url(url):
    """Scrapes content from a single website URL using newspaper4k."""
    print(f"      - Scraping URL (Newspaper4k): {url}")
    log_to_file(f"Scraping website URL: {url}")
    try:
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        article = Article(url, request_headers=headers, fetch_images=False)
        article.download()
        if article.download_state != 2: # 2 means success
             # Try download with different UA if initial failed? Maybe too complex for now.
             raise ArticleException(f"Download failed (state {article.download_state})")
        article.parse()

        title = article.title
        text = article.text
        publish_date = article.publish_date

        if text and len(text) > 150:
            content = f"Source URL: {url}\n"
            if title: content += f"Title: {title}\n"
            if publish_date: content += f"Published: {publish_date.strftime('%Y-%m-%d') if publish_date else 'N/A'}\n"
            content += f"\nBody:\n{text}"
            print(f"        - Success: Scraped content ({len(text)} chars).")
            log_to_file(f"Website scrape success: {url} ({len(text)} chars)")
            return content.strip()
        elif text:
            print("        - Warning: Scraped text too short, skipping.")
            log_to_file(f"Website scrape warning (too short): {url} ({len(text)} chars)")
            return None
        else:
            # Sometimes newspaper fails parsing but might have HTML? Less reliable.
            print("        - Warning: Newspaper4k found no text.")
            log_to_file(f"Website scrape warning (no text): {url}")
            return None

    except ArticleException as e:
        print(f"        - Error (Newspaper4k) scraping {url}: {e}")
        log_to_file(f"Website scrape ArticleException: {url} - {e}")
        return None
    except requests.exceptions.RequestException as e:
         print(f"        - Error (Request) fetching {url}: {e}")
         log_to_file(f"Website scrape RequestException: {url} - {e}")
         return None
    except Exception as e:
        print(f"        - Unexpected error scraping {url}: {e}")
        log_to_file(f"Website scrape Unexpected Error: {url} - {e}")
        return None
    finally:
        time.sleep(random.uniform(1.5, 3)) # Delay between website scrapes

# --- Selenium Setup Utility ---
def setup_selenium_driver():
    """Initializes and returns a Selenium WebDriver instance."""
    driver = None
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu') # Often needed in headless
        options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
        options.add_experimental_option('excludeSwitches', ['enable-logging']) # Suppress USB device errors

        # Use webdriver-manager to handle driver download/update
        print("    - Setting up Selenium WebDriver with webdriver-manager...")
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("    - Selenium WebDriver initialized successfully.")
        return driver
    except Exception as e:
        print(f"    - Error initializing Selenium WebDriver: {e}")
        log_to_file(f"Selenium Init Error: {e}")
        if driver:
            driver.quit()
        return None

def scrape_content(sources_or_urls, direct_article_urls, args, config):
    """Scrapes content from discovered/provided sources or direct URLs."""
    print(f"\n--- Starting Content Scraping Phase ---")
    scraped_texts = []
    seen_urls_global = set()
    direct_urls_set = set(direct_article_urls or [])

    for i, item in enumerate(sources_or_urls, 1):
        print(f"\nProcessing item {i}/{len(sources_or_urls)}: {item}")
        source_texts_count = 0

        is_reddit_source = item.startswith('r/') or 'reddit.com/r/' in item
        is_direct_url = item in direct_urls_set and not is_reddit_source
        is_website_source = not is_reddit_source and not is_direct_url

        try:
            # --- Handle Explicit Direct URLs ---
            if is_direct_url:
                print(f"  - Type: Explicit Direct URL")
                if item in seen_urls_global:
                    print(f"      - Skipping already scraped URL: {item}")
                    continue

                scraped_text = scrape_website_url(item)
                if scraped_text:
                    scraped_texts.append(scraped_text)
                    seen_urls_global.add(item)
                    source_texts_count += 1

            # --- Handle Reddit Sources (Selenium) ---
            elif is_reddit_source:
                print(f"  - Type: Reddit Source")
                if args.no_search:
                     print(f"  - Warning: Skipping Reddit source '{item}' because --no-search is active.")
                     log_to_file(f"Scraping Warning: Skipped Reddit source {item} due to --no-search.")
                     continue

                source_scrape_limit = args.max_reddit_results # Limit on POSTS
                subreddit_name = item.replace('r/', '').split('/')[0]
                if not subreddit_name:
                    print(f"  - Warning: Could not extract subreddit name from '{item}'. Skipping.")
                    log_to_file(f"Scraping Warning: Invalid subreddit source format '{item}'")
                    continue

                print(f"  - Processing r/{subreddit_name} using Selenium/old.reddit.com...")
                log_to_file(f"Initiating Selenium scrape for r/{subreddit_name}")
                driver = setup_selenium_driver() # Use helper function
                if not driver:
                     print("    - ERROR: Failed to initialize Selenium driver. Skipping Reddit source.")
                     log_to_file(f"Selenium Skip: Driver initialization failed for r/{subreddit_name}")
                     continue # Skip this source if driver fails

                all_post_links_for_subreddit = set()
                reddit_texts = []
                wait = WebDriverWait(driver, 20) # 20 sec timeout for elements

                try:
                    # --- Perform Search for Each Keyword ---
                    if not args.search_queries: # Should not happen if not --no-search, but check
                        print("    - Warning: No search queries defined for Reddit search. Cannot find posts.")
                        log_to_file(f"Selenium Warning: No search queries for r/{subreddit_name}")
                    else:
                        for query_idx, search_query in enumerate(args.search_queries):
                            print(f"      - Searching subreddit for query {query_idx+1}/{len(args.search_queries)}: '{search_query}'")
                            try:
                                encoded_query = urllib.parse.quote_plus(search_query)
                                search_url = f"https://old.reddit.com/r/{subreddit_name}/search/?q={encoded_query}&restrict_sr=1&sort=relevance&t=all" # Ensure restrict_sr=1
                                print(f"        - Navigating to: {search_url}")
                                driver.get(search_url)
                                time.sleep(random.uniform(2.5, 4.5)) # Let dynamic content load

                                # Wait for search results container or a specific result link
                                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.search-result, a.search-link")))
                                link_elements = driver.find_elements(By.CSS_SELECTOR, "a.search-link, a.search-title") # Broader link selection
                                print(f"        - Found {len(link_elements)} potential result links for this query.")

                                count = 0
                                for link_element in link_elements:
                                    href = link_element.get_attribute('href')
                                    # Check if it's a valid post link, not already seen
                                    if href and '/comments/' in href and subreddit_name in href and href not in all_post_links_for_subreddit:
                                         # Simple check to avoid user profile links if possible
                                        if '/user/' not in href:
                                             all_post_links_for_subreddit.add(href)
                                             count += 1
                                print(f"        - Added {count} new unique post links for this query.")

                            except TimeoutException:
                                print(f"        - Timeout/No results found for query: '{search_query}'")
                                log_to_file(f"Selenium Timeout/No Results: r/{subreddit_name}, Query: '{search_query}'")
                            except Exception as search_e:
                                print(f"        - Error extracting search results for query '{search_query}': {search_e}")
                                log_to_file(f"Selenium Error extracting search results: r/{subreddit_name}, Query: '{search_query}': {search_e}")
                            finally:
                                time.sleep(random.uniform(1, 2)) # Delay between searches

                    # --- Scrape Collected Post Links ---
                    unique_post_links = list(all_post_links_for_subreddit)
                    print(f"    - Total unique post links found: {len(unique_post_links)}")
                    links_to_scrape = unique_post_links[:source_scrape_limit]
                    print(f"    - Scraping top {len(links_to_scrape)} posts (Limit: {source_scrape_limit})...")

                    if not links_to_scrape: print("    - No relevant post links found to scrape.")

                    for post_idx, post_url in enumerate(links_to_scrape, 1):
                        if post_url in seen_urls_global:
                            print(f"      - Post {post_idx}: Skipping already scraped URL (globally): {post_url}")
                            continue
                        # No need to check source_texts_count limit here, already limited by links_to_scrape

                        print(f"      - Post {post_idx}: Scraping {post_url}")
                        try:
                            driver.get(post_url)
                            time.sleep(random.uniform(2.5, 4.5))

                            post_title = "N/A"; post_body = ""; comment_texts = []
                            # Title (old reddit)
                            try:
                                title_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "p.title a.title")))
                                post_title = title_element.text.strip()
                            except Exception: print("        - Warning: Could not find post title.")
                            # Body (old reddit)
                            try:
                                # Look for selftext md first, then expando
                                body_elements = driver.find_elements(By.CSS_SELECTOR, "div.entry div.expando div.md")
                                if body_elements:
                                    post_body = body_elements[0].text.strip()
                            except Exception: pass # Ignore if no body
                            # Comments (old reddit)
                            try:
                                comment_limit = args.max_reddit_comments
                                print(f"        - Extracting top {comment_limit} comments...")
                                # Target the main paragraph within each comment body
                                comment_elements = driver.find_elements(By.CSS_SELECTOR, "div.commentarea .comment .md p")
                                collected_comments = 0
                                for p_element in comment_elements:
                                     if collected_comments >= comment_limit: break
                                     comment_text = p_element.text.strip()
                                     # Basic filtering: non-empty, not just '[deleted]' or '[removed]'
                                     if comment_text and comment_text.lower() not in ('[deleted]', '[removed]'):
                                        comment_texts.append(comment_text)
                                        collected_comments += 1
                                print(f"        - Extracted {len(comment_texts)} valid comment paragraphs.")
                            except Exception as comment_e: print(f"        - Warning: Error extracting comments: {comment_e}")

                            # Combine content
                            full_content = (f"Source: Reddit (r/{subreddit_name})\n"
                                            f"Permalink: {post_url}\n"
                                            f"Title: {post_title}\n\n"
                                            f"Body:\n{post_body if post_body else '[No Body Text]'}\n\n"
                                            f"--- Comments ({len(comment_texts)} scraped) ---\n" +
                                            "\n\n---\n\n".join(comment_texts)) # Use double newline between comments
                            content_length = len(full_content)
                            min_length = 100 # Lower min length for Reddit posts

                            if content_length > min_length:
                                reddit_texts.append(full_content.strip())
                                seen_urls_global.add(post_url)
                                source_texts_count += 1 # Counts successful POST scrapes
                                print(f"        - Success: Scraped content ({content_length} chars).")
                                log_to_file(f"Selenium scrape success: {post_url} ({content_length} chars)")
                            else:
                                print(f"        - Warning: Scraped content too short ({content_length} chars, min {min_length}). Skipping post.")
                                log_to_file(f"Selenium scrape warning (too short): {post_url} ({content_length} chars)")

                        except TimeoutException:
                            print(f"      - Post {post_idx}: Timeout loading post page: {post_url}")
                            log_to_file(f"Selenium Timeout loading post page: {post_url}")
                        except Exception as post_e:
                            print(f"      - Post {post_idx}: Error processing post page {post_url}: {post_e}")
                            log_to_file(f"Selenium Error processing post page {post_url}: {post_e}")
                        finally:
                             time.sleep(random.uniform(1.5, 3)) # Delay between posts

                except Exception as selenium_e:
                    print(f"    - An error occurred during Selenium processing for r/{subreddit_name}: {selenium_e}")
                    log_to_file(f"Selenium Error processing source r/{subreddit_name}: {selenium_e}")
                finally:
                    if driver:
                        print("    - Quitting Selenium WebDriver for this source.")
                        driver.quit()

                scraped_texts.extend(reddit_texts) # Add all collected texts for this subreddit

            # --- Handle Website Sources (Search API + Newspaper4k) ---
            elif is_website_source:
                print(f"  - Type: Website Source (Requires Search)")
                if args.no_search:
                    print(f"  - Warning: Skipping website source '{item}' because --no-search is active.")
                    log_to_file(f"Scraping Warning: Skipped website source {item} due to --no-search.")
                    continue

                source_scrape_limit = args.max_web_results # Limit on URLS per domain
                domain = urllib.parse.urlparse(item).netloc or item
                print(f"  - Processing domain: {domain} (Original source suggestion: {item})")
                log_to_file(f"Processing website source: {domain} (Original: {item})")
                urls_to_scrape_for_domain = set()

                search_targets = args.search_queries
                results_limit_per_api_call = args.per_keyword_results

                # --- Search APIs ---
                if not search_targets:
                    print("    - Warning: No search queries defined for website source. Cannot find specific articles.")
                    log_to_file(f"Scraping Warning: No search queries for website source {domain}")
                else:
                    for query_idx, search_query in enumerate(search_targets):
                        # Construct query for API (site: modifier)
                        current_query_for_api = f"site:{domain} {search_query}"
                        print(f"    - Searching web APIs for query {query_idx+1}/{len(search_targets)}: '{current_query_for_api}' (Limit: {results_limit_per_api_call})")

                        api_results = None
                        primary_api = args.api
                        fallback_api = 'brave' if primary_api == 'google' else 'google'

                        # Attempt Primary API
                        print(f"      - Attempting primary API: {primary_api}")
                        if primary_api == 'google':
                            api_results = search_google_api(current_query_for_api, config, results_limit_per_api_call, args.from_date, args.to_date)
                        else: # brave
                            api_results = search_brave_api(current_query_for_api, config, results_limit_per_api_call, args.from_date, args.to_date)

                        quota_hit = api_results == 'quota_error'
                        failed = api_results is None

                        if quota_hit: print(f"      - Primary API '{primary_api}' quota limit hit.")
                        elif failed: print(f"      - Primary API '{primary_api}' failed or returned no results.")

                        # Attempt Fallback API if primary failed (not due to quota initially) or hit quota
                        if failed or quota_hit:
                            print(f"      - Attempting fallback API: {fallback_api}")
                            if fallback_api == 'google':
                                api_results_fallback = search_google_api(current_query_for_api, config, results_limit_per_api_call, args.from_date, args.to_date)
                            else: # brave
                                api_results_fallback = search_brave_api(current_query_for_api, config, results_limit_per_api_call, args.from_date, args.to_date)

                            # Decide which results to use (prefer fallback if primary failed, handle double quota)
                            if api_results_fallback == 'quota_error':
                                print(f"      - Fallback API '{fallback_api}' also hit quota limit.")
                                if quota_hit: api_results = None # Both hit quota, give up
                                # else: keep original primary results if they existed before quota hit (unlikely scenario)
                            elif api_results_fallback is None:
                                print(f"      - Fallback API '{fallback_api}' also failed or returned no results.")
                                if quota_hit: api_results = None # Primary hit quota, fallback failed
                                # else: keep original primary results if they existed and weren't quota error
                            elif isinstance(api_results_fallback, list):
                                print(f"      - Fallback API '{fallback_api}' succeeded.")
                                api_results = api_results_fallback # Use fallback results
                            # If fallback was None/Error, api_results retains its state from primary attempt

                        # Add successfully found URLs
                        if isinstance(api_results, list):
                            added_count = 0
                            for url in api_results:
                                if url not in urls_to_scrape_for_domain and url not in seen_urls_global:
                                    urls_to_scrape_for_domain.add(url)
                                    added_count += 1
                            print(f"      - Added {added_count} new unique URLs from API search.")
                            log_to_file(f"API Search: Added {added_count} URLs for query '{current_query_for_api}' on site {domain}")
                        else:
                            print(f"      - No URLs obtained from APIs for this query.")
                            log_to_file(f"API Search Failed/Empty for query '{current_query_for_api}' on site {domain}")

                        time.sleep(random.uniform(1, 2)) # Delay between API calls

                # --- Scrape Content from URLs ---
                unique_urls_list = list(urls_to_scrape_for_domain)
                print(f"    - Total unique URLs found for domain '{domain}': {len(unique_urls_list)}")
                urls_to_process = unique_urls_list[:source_scrape_limit] # Apply overall limit per domain
                print(f"    - Attempting to scrape top {len(urls_to_process)} URLs (Limit: {source_scrape_limit})...")

                for url_idx, url in enumerate(urls_to_process, 1):
                    if url in seen_urls_global:
                        print(f"      - URL {url_idx}: Skipping already scraped URL (globally): {url}")
                        continue
                    # Limit already applied by urls_to_process slice

                    print(f"      - URL {url_idx}: ", end="") # scrape_website_url will add details
                    scraped_text = scrape_website_url(url)
                    if scraped_text:
                        scraped_texts.append(scraped_text)
                        seen_urls_global.add(url)
                        source_texts_count += 1
                    # scrape_website_url handles its own logging/printing

            else:
                print(f"  - Warning: Could not determine type for item: {item}. Skipping.")
                log_to_file(f"Scraping Warning: Unknown item type: {item}")

        except Exception as item_e:
            print(f"\nError processing item '{item}': {item_e}")
            log_to_file(f"Scraping Error: Unexpected error processing item '{item}': {item_e}")
            import traceback
            log_to_file(f"Traceback:\n{traceback.format_exc()}") # Log traceback for item errors

        print(f"  - Finished item: {item}. Scraped {source_texts_count} piece(s) for this item.")
        if i < len(sources_or_urls):
            delay = random.uniform(2, 5) # Slightly shorter delay between sources
            print(f"--- Delaying {delay:.2f}s before next source ---")
            time.sleep(delay)

    print(f"\n--- Finished Scraping Phase. Total unique content pieces gathered: {len(scraped_texts)} ---")
    log_to_file(f"Scraping phase complete. Gathered {len(scraped_texts)} content pieces.")
    return scraped_texts

# --- Summarization Phase ---

def summarize_content(scraped_texts, reference_docs, topic, config, args):
    """
    Uses AI to summarize scraped content and optionally reference documents,
    assigning a relevance score to each.
    """
    content_to_process = []
    # Add scraped texts
    for idx, text in enumerate(scraped_texts):
        content_to_process.append({"type": "scraped", "content": text, "source_index": idx + 1})

    # Add reference docs (conditionally based on summarize flag)
    ref_docs_for_summary = []
    if args.reference_docs_summarize and reference_docs:
        print(f"\nIncluding {len(reference_docs)} reference documents in summarization process.")
        log_to_file(f"Summarization: Adding {len(reference_docs)} reference docs for summarization.")
        ref_docs_for_summary = reference_docs
    elif reference_docs:
         print(f"\nNote: {len(reference_docs)} reference documents provided but --reference-docs-summarize is OFF. They will be used in the final report directly, not summarized here.")
         log_to_file(f"Summarization: Skipping summarization for {len(reference_docs)} reference docs (--reference-docs-summarize=False).")

    # Add reference docs marked for summarization to the processing list
    for doc in ref_docs_for_summary:
         content_to_process.append({"type": "reference", "content": doc["content"], "path": doc["path"]})

    total_pieces = len(content_to_process)
    if total_pieces == 0:
        print("\nWarning: No content (scraped or reference for summarization) available to summarize.")
        log_to_file("Summarization Warning: No content found to process.")
        return []

    print(f"\n--- Starting Summarization & Scoring Phase ({total_pieces} pieces) ---")
    log_to_file(f"Starting summarization for {total_pieces} piece(s). Topic: {topic}")
    summaries_with_scores = []
    successful_summaries = 0

    for i, item in enumerate(content_to_process, 1):
        text = item["content"]
        item_type = item["type"]
        item_source_id = item.get("path", f"Scraped_{item.get('source_index', i)}")

        # Basic check for meaningful content length
        if len(text) < 100:
            print(f"\rSkipping summary for short text piece {i}/{total_pieces} ({item_source_id}).", end='', flush=True)
            log_to_file(f"Summary {i}/{total_pieces} ({item_source_id}) skipped (too short: {len(text)} chars).")
            continue

        print(f"\rSummarizing & Scoring {i}/{total_pieces} ({item_type}: {os.path.basename(str(item_source_id))[:30]}...) (Success: {successful_summaries})", end='', flush=True)

        # Truncate potentially very long texts (adjust limit based on model context window)
        # Get max_tokens from model config if available, estimate input capacity
        model_cfg = config.get("selected_model_config", {})
        # Rough estimation: 4 chars per token, leave room for prompt/output
        # Default to a safe limit if max_tokens not specified
        max_model_tokens = model_cfg.get("max_tokens", 4096)
        # Leave maybe 1/4 for prompt and response, use 3/4 for input text
        # This is a very rough estimate!
        estimated_char_limit = int(max_model_tokens * 0.75 * 3.5) # Lower chars/token estimate for safety
        max_summary_input_chars = min(150000, estimated_char_limit) # Use lower of hard limit or estimated

        truncated_text = text[:max_summary_input_chars]
        if len(text) > max_summary_input_chars:
            log_to_file(f"Warning: Summary {i} ({item_source_id}) input text truncated from {len(text)} to {max_summary_input_chars} chars.")

        guidance_text = f"\n**Additional Guidance:** {args.guidance}\n" if args.guidance else ""
        prompt = (
            f"Please provide a concise yet comprehensive summary of the following text. Focus on the key information, main arguments, findings, and any specific data points (statistics, percentages, benchmark results, dates, names) relevant to the main topic.\n"
            f"**Main Topic:** {topic}{guidance_text}\n"
            f"**Text to Summarize:**\n---\n{truncated_text}\n---\n\n"
            f"**Instructions:**\n"
            f"1. Format your summary *only* within <toolScrapeSummary> tags.\n"
            f"2. After the summary tag, provide a relevance score (integer 0-10) indicating how relevant the *summary* is to the Main Topic ('{topic}') and adheres to any Additional Guidance provided. Enclose the score *only* in <summaryScore> tags.\n\n"
            f"**Example Response Structure:**\n"
            f"<toolScrapeSummary>This is a concise summary preserving key details like a 95% accuracy rate achieved in 2023 according to Dr. Smith.</toolScrapeSummary>\n"
            f"<summaryScore>8</summaryScore>"
        )

        # Use a reasonable timeout for summarization
        raw_response, cleaned_response = call_ai_api(prompt, config, tool_name=f"Summary_{i}_{item_type}", timeout=180)

        summary = "Error: Summarization Failed"
        score = -1
        summary_details = {"type": item_type, "source_id": item_source_id} # Store type and source id

        if cleaned_response:
            parsed_summary = parse_ai_tool_response(cleaned_response, "toolScrapeSummary")
            if parsed_summary == cleaned_response and '<toolScrapeSummary>' not in cleaned_response.lower():
                 log_to_file(f"Error: Summary {i} ({item_source_id}) parsing failed - <toolScrapeSummary> tag missing.")
                 summary = f"Error: Could not parse summary {i} ({item_source_id}) (<toolScrapeSummary> tag missing)"
            elif not parsed_summary:
                 log_to_file(f"Error: Summary {i} ({item_source_id}) parsing failed - No content found in <toolScrapeSummary> tag.")
                 summary = f"Error: Could not parse summary {i} ({item_source_id}) (empty tag)"
            else:
                 summary = parsed_summary

            score_match = re.search(r'<summaryScore>(\d{1,2})</summaryScore>', cleaned_response, re.IGNORECASE)
            if score_match:
                try:
                    parsed_score = int(score_match.group(1))
                    if 0 <= parsed_score <= 10:
                        score = parsed_score
                        successful_summaries += 1
                    else:
                        log_to_file(f"Warning: Summary {i} ({item_source_id}) score '{parsed_score}' out of range (0-10). Using -1.")
                except ValueError:
                    log_to_file(f"Warning: Could not parse summary {i} ({item_source_id}) score '{score_match.group(1)}'. Using -1.")
            else:
                 log_to_file(f"Warning: Could not find/parse <summaryScore> tag for summary {i} ({item_source_id}). Using -1.")

        else:
            log_to_file(f"Error: API call failed for Summary_{i} ({item_source_id})")
            summary = f"Error: Could not summarize text piece {i} ({item_source_id}) (API call failed)"

        summary_details.update({'summary': summary, 'score': score})
        summaries_with_scores.append(summary_details)

        if run_archive_dir:
            safe_source_id = re.sub(r'[\\/*?:"<>|]', "_", str(item_source_id).replace(os.path.sep, '_')) # Sanitize path separators too
            summary_filename = os.path.join(run_archive_dir, f"summary_{i}_{item_type}_{safe_source_id[:50]}.txt")
            try:
                with open(summary_filename, 'w', encoding='utf-8') as sf:
                    sf.write(f"Source: {item_source_id}\nType: {item_type}\nScore: {score}\n\n{summary}")
            except IOError as e:
                log_to_file(f"Warning: Could not save summary {i} ({item_source_id}) to file {summary_filename}: {e}")

    print(f"\rSummarization & Scoring complete. Generated {successful_summaries}/{total_pieces} summaries successfully (with valid scores).")
    log_to_file(f"Summarization phase complete. Successful summaries (with score): {successful_summaries}/{total_pieces}")
    print("--- Finished Summarization Phase ---")
    return summaries_with_scores


# --- Report Generation & Refinement ---

def generate_report(summaries_with_scores, reference_docs_content, topic, config, args):
    """Uses AI to generate the initial research report."""
    global run_archive_dir
    print("\n--- Starting Initial Report Generation ---")
    log_to_file(f"Starting initial report generation. Topic: {topic}")

    # --- Prepare Context ---
    valid_summaries = [s for s in summaries_with_scores if s['score'] >= args.score_threshold and not s['summary'].startswith("Error:")]
    combined_summaries_text = f"No valid summaries met the score threshold ({args.score_threshold}) or were generated without errors."
    num_summaries_used = len(valid_summaries)

    if valid_summaries:
        top_summaries = sorted(valid_summaries, key=lambda x: x['score'], reverse=True)
        print(f"Using {num_summaries_used} summaries (score >= {args.score_threshold}) for report generation.")
        log_to_file(f"Report Gen: Using {num_summaries_used} summaries meeting score threshold {args.score_threshold}.")
        combined_summaries_text = "\n\n".join([
            f"Summary {i+1} (Source: {s['source_id']}, Type: {s['type']}, Score: {s['score']}):\n{s['summary']}"
            for i, s in enumerate(top_summaries)
        ])
    else:
         print(f"Warning: No valid summaries met the score threshold ({args.score_threshold}) for report generation.")
         log_to_file(f"Report Gen Warning: No valid summaries met score threshold {args.score_threshold}.")

    full_reference_docs_text = ""
    num_ref_docs_used = 0
    # Include non-summarized ref docs directly
    if reference_docs_content and not args.reference_docs_summarize:
        num_ref_docs_used = len(reference_docs_content)
        print(f"Including {num_ref_docs_used} full reference documents directly in the report prompt.")
        log_to_file(f"Report Gen: Including {num_ref_docs_used} full reference documents.")
        full_reference_docs_text = "\n\n---\n\n".join([
            f"Reference Document (Path: {doc['path']}):\n{doc['content']}"
            for doc in reference_docs_content
        ])
        full_reference_docs_text = f"**Full Reference Documents (Use for context):**\n---\n{full_reference_docs_text}\n---"

    if num_summaries_used == 0 and num_ref_docs_used == 0:
         print("Error: No summaries or reference documents available to generate report.")
         log_to_file("Report Gen Error: No summaries or reference documents available for context.")
         return None, None # Return None for both path and content

    # --- Construct Prompt ---
    guidance_text = f"\n**Additional Guidance:** {args.guidance}\n" if args.guidance else ""
    prompt = (
        f"You are an AI research assistant. Write a comprehensive, well-structured, and formal research report on: '{topic}'.{guidance_text}\n"
        f"**Task:** Generate a detailed research report based *exclusively* on the provided context (summaries and/or full reference documents). Synthesize the information, identify key themes, arguments, evidence, and specific details. Structure logically with Introduction, Body Paragraphs (thematic), and Conclusion. Maintain an objective, formal tone. Do *not* introduce outside knowledge.\n\n"
        f"**Context for Report Generation:**\n\n"
        f"--- Summaries ---\n{combined_summaries_text}\n---\n\n"
        f"{full_reference_docs_text}\n\n"
        f"**CRITICAL FORMATTING:** Enclose the *entire* report content within a single pair of `<reportContent>` tags. ONLY include the report text inside the tags. NO other text, remarks, or explanations outside the tags.\n"
        f"<reportContent>" # Start the tag for the LLM
    )
    # Add closing tag instruction separately for clarity, though included above
    prompt += "\n</reportContent>" # Make sure LLM knows where to end

    # Save report prompt
    if run_archive_dir:
        prompt_filename = os.path.join(run_archive_dir, "report_prompt_initial.txt")
        try:
            with open(prompt_filename, 'w', encoding='utf-8') as pf: pf.write(prompt)
            log_to_file(f"Saved initial report prompt to {prompt_filename}")
        except IOError as e: log_to_file(f"Warning: Could not save initial report prompt: {e}")

    # --- Call AI ---
    # Use a longer timeout for potentially complex report generation
    raw_response, cleaned_response = call_ai_api(prompt, config, tool_name="ReportGeneration", timeout=3000)

    # Save raw response
    if run_archive_dir and raw_response:
        raw_resp_filename = os.path.join(run_archive_dir, "report_response_initial_raw.txt")
        try:
            with open(raw_resp_filename, 'w', encoding='utf-8') as rf: rf.write(raw_response)
            log_to_file(f"Saved initial report raw response to {raw_resp_filename}")
        except IOError as e: log_to_file(f"Warning: Could not save initial report raw response: {e}")

    if not cleaned_response:
        print("\nError: Failed to generate initial report from AI (empty cleaned response).")
        log_to_file("Report Gen Error: Failed (empty cleaned response).")
        return None, None

    # --- Parse and Save Initial Report ---
    report_text = parse_ai_tool_response(cleaned_response, "reportContent")

    # Check if parsing failed or returned nothing *or* returned the full response (meaning tag wasn't used correctly)
    if not report_text or report_text == clean_thinking_tags(cleaned_response):
        print("\nError: Could not parse valid <reportContent> from the AI response for the initial report.")
        log_to_file(f"Report Gen Error: Failed to parse <reportContent> tag or content was empty.\nCleaned Response was:\n{clean_thinking_tags(cleaned_response)}")
        if run_archive_dir:
            failed_report_path = os.path.join(run_archive_dir, "report_INITIAL_FAILED_PARSE.txt")
            try:
                with open(failed_report_path, 'w', encoding='utf-8') as frf: frf.write(clean_thinking_tags(cleaned_response) or "Original cleaned response was empty.")
            except IOError: pass
        return None, None # Return None for path and content

    # Save the initial, unrefined report to the archive
    initial_report_filename = "research_report_initial_raw.txt" # Name indicating it's the raw version
    initial_report_filepath = os.path.join(run_archive_dir, initial_report_filename) if run_archive_dir else initial_report_filename

    try:
        with open(initial_report_filepath, 'w', encoding='utf-8') as ef:
            ef.write(report_text)
        print(f"Saved initial (unrefined) report to archive: {initial_report_filepath}")
        log_to_file(f"Initial research report saved to archive: {initial_report_filepath}")
        # Return BOTH the path and the content for the refinement step
        return initial_report_filepath, report_text
    except IOError as e:
        print(f"\nError: Could not save initial research report to {initial_report_filepath}: {e}")
        log_to_file(f"Report Saving Error: Failed to save initial report to {initial_report_filepath}: {e}")
        # Try CWD fallback ONLY if archive failed
        if run_archive_dir:
            try:
                cwd_filename = initial_report_filename
                with open(cwd_filename, 'w', encoding='utf-8') as ef_cwd: ef_cwd.write(report_text)
                print(f"Saved initial report to {cwd_filename} (CWD fallback)")
                log_to_file(f"Initial report saved to CWD fallback: {cwd_filename}")
                return cwd_filename, report_text # Return path and content
            except IOError as e_cwd:
                print(f"\nError: Could not save initial report to CWD fallback path either: {e_cwd}")
                log_to_file(f"Report Saving Error: Failed to save initial report to CWD fallback: {e_cwd}")
                return None, None # Failed completely
        else: # No archive dir was set, fail saving
             return None, None

def refine_report_presentation(initial_report_content, topic, config, timestamp, topic_slug):
    """Uses AI to refine the presentation of the generated report."""
    print("\n--- Starting Report Refinement Phase ---")
    log_to_file("Starting report refinement phase.")

    if not initial_report_content:
        print("Error: No initial report content provided for refinement.")
        log_to_file("Refinement Error: Initial report content was empty.")
        return None # Cannot refine nothing

    # --- Construct Refinement Prompt ---
    refinement_prompt = (
        f"You are an AI assistant specializing in document presentation and formatting.\n"
        f"**Task:** Refine the following research report text to significantly improve its presentation for a supervisor. Focus on enhancing readability, structure, scannability, and visual appeal using standard text formatting. The topic is '{topic}'.\n\n"
        f"**Refinement Instructions:**\n"
        f"1.  **Executive Summary:** Add a concise (2-4 sentence) 'Executive Summary' or 'Key Takeaways' section at the very beginning, summarizing the report's core findings.\n"
        f"2.  **Headings/Subheadings:** Ensure clear, descriptive headings (e.g., using markdown-style `#`, `##`, `###`) for sections like Introduction, different Body themes, Conclusion, and potentially Recommendations or Methods if applicable based on the content.\n"
        f"3.  **Lists:** Convert dense paragraph descriptions of items, steps, pros/cons, or methods into bulleted (`*` or `-`) or numbered lists.\n"
        f"4.  **Tables (Optional but Recommended):** If the text compares multiple methods, items, or data points (e.g., different acquisition methods with costs/limits), try to structure this into a simple markdown table for easy comparison. If a table is not feasible, use parallel bullet points under clear subheadings.\n"
        f"5.  **Paragraphs:** Break down long paragraphs into shorter, more focused ones, each addressing a single idea.\n"
        f"6.  **Bolding:** Use bold text (`**text**`) strategically and sparingly for key terms or crucial conclusions within sentences, not entire sentences.\n"
        f"7.  **Clarity & Flow:** Ensure smooth transitions and logical flow between sections.\n"
        f"8.  **No New Content:** Do NOT add information not present in the original text. Focus *only* on restructuring and formatting.\n\n"
        f"**Original Report Text to Refine:**\n"
        f"--- START ORIGINAL REPORT ---\n"
        f"{initial_report_content}\n"
        f"--- END ORIGINAL REPORT ---\n\n"
        f"**CRITICAL OUTPUT FORMAT:** Enclose the *entire* refined report within a single pair of `<refinedReport>` tags. ONLY include the refined report text inside these tags. NO other text, remarks, or explanations outside the tags.\n"
        f"<refinedReport>" # Start the tag
    )
    refinement_prompt += "\n</refinedReport>" # End the tag

    # Save refinement prompt
    if run_archive_dir:
        ref_prompt_filename = os.path.join(run_archive_dir, "report_prompt_refinement.txt")
        try:
            with open(ref_prompt_filename, 'w', encoding='utf-8') as pf: pf.write(refinement_prompt)
            log_to_file(f"Saved refinement prompt to {ref_prompt_filename}")
        except IOError as e: log_to_file(f"Warning: Could not save refinement prompt: {e}")

    # --- Call AI for Refinement ---
    raw_response, cleaned_response = call_ai_api(refinement_prompt, config, tool_name="ReportRefinement", timeout=1200) # Allow decent time

    # Save raw refinement response
    if run_archive_dir and raw_response:
        ref_raw_resp_filename = os.path.join(run_archive_dir, "report_response_refinement_raw.txt")
        try:
            with open(ref_raw_resp_filename, 'w', encoding='utf-8') as rf: rf.write(raw_response)
            log_to_file(f"Saved refinement raw response to {ref_raw_resp_filename}")
        except IOError as e: log_to_file(f"Warning: Could not save refinement raw response: {e}")

    if not cleaned_response:
        print("\nWarning: Failed to get response from AI for report refinement.")
        log_to_file("Refinement Warning: Failed (empty cleaned response).")
        return None

    # --- Parse Refined Report ---
    refined_report_text = parse_ai_tool_response(cleaned_response, "refinedReport")

    if not refined_report_text or refined_report_text == clean_thinking_tags(cleaned_response):
        print("\nWarning: Could not parse valid <refinedReport> content from the AI refinement response. Skipping refinement.")
        log_to_file(f"Refinement Warning: Failed to parse <refinedReport> tag or content was empty.\nCleaned Response was:\n{clean_thinking_tags(cleaned_response)}")
        if run_archive_dir:
            failed_ref_report_path = os.path.join(run_archive_dir, "report_REFINED_FAILED_PARSE.txt")
            try:
                with open(failed_ref_report_path, 'w', encoding='utf-8') as frf: frf.write(clean_thinking_tags(cleaned_response) or "Original cleaned response was empty.")
            except IOError: pass
        return None # Indicate refinement failed

    # --- Save Refined Report to Designated Folder ---
    # Directory: <script_run_directory>/outputs/
    # Filename: <timestamp>_<topic_slug>_report.txt
    try:
        # Define the main output directory name
        output_dir_name = "outputs"
        # Create the full path to the output directory in the CWD
        final_output_dir = os.path.join(os.getcwd(), output_dir_name)
        # Create the directory if it doesn't exist
        os.makedirs(final_output_dir, exist_ok=True)
        print(f"Ensured output directory exists: {final_output_dir}")

        # Construct the desired filename using timestamp and topic_slug
        final_filename = f"{timestamp}_{topic_slug}_report.txt"
        # Create the full path to the final file inside the 'outputs' directory
        final_filepath = os.path.join(final_output_dir, final_filename)

        with open(final_filepath, 'w', encoding='utf-8') as ff:
            ff.write(refined_report_text)

        print(f"Successfully saved refined report to: {final_filepath}")
        log_to_file(f"Refined report saved successfully to: {final_filepath}")
        return final_filepath # Return the path of the refined report

    except IOError as e:
        print(f"\nError: Could not save refined report to {final_filepath}: {e}")
        log_to_file(f"Refinement Saving Error: Failed to save refined report to {final_filepath}: {e}")
        # Also save to archive as fallback if possible
        if run_archive_dir:
            fallback_filename = os.path.join(run_archive_dir, f"refined_report_FALLBACK_{timestamp}.txt")
            try:
                 with open(fallback_filename, 'w', encoding='utf-8') as fbf: fbf.write(refined_report_text)
                 print(f"Saved refined report to archive as fallback: {fallback_filename}")
                 log_to_file(f"Refinement Saving Fallback: Saved refined report to {fallback_filename}")
            except IOError as e_fb:
                 log_to_file(f"Refinement Saving Fallback Error: Could not save to archive fallback: {e_fb}")
        return None # Indicate saving failed
    except Exception as e:
         print(f"\nError creating directory or saving refined report: {e}")
         log_to_file(f"Refinement Saving Error: Unexpected error: {e}")
         return None


# --- Main Execution ---

def main():
    """Main function to orchestrate the AI report generation workflow."""
    global run_archive_dir

    print("--- Starting AI Report Generator ---")
    start_time = time.time()

    # --- Setup ---
    # Ensure SCRIPT_DIR is correctly determined at the start
    print(f"Script directory: {SCRIPT_DIR}")
    print(f"Current working directory: {os.getcwd()}")

    env_config, models_config = load_config()
    args = parse_arguments()

    # --- Determine Final Model Configuration ---
    final_model_key = "default_model"
    env_model_key = os.getenv("DEFAULT_MODEL_CONFIG")

    if args.llm_model: final_model_key = args.llm_model; source = "command line"
    elif env_model_key: final_model_key = env_model_key; source = ".env"
    else: source = "default"

    print(f"Using LLM model configuration '{final_model_key}' (Source: {source})")
    log_to_file(f"Model Selection: Using '{final_model_key}' (Source: {source})")
    env_config['final_model_key'] = final_model_key

    final_model_config = models_config.get(final_model_key)
    if not final_model_config or not isinstance(final_model_config, dict):
        print(f"Error: Final model key '{final_model_key}' configuration not found or invalid in ai_models.yml")
        print(f"Available configurations: {list(models_config.keys())}")
        log_to_file(f"Run Error: Invalid final model key selected: '{final_model_key}'")
        exit(1)
    if 'model' not in final_model_config:
        print(f"Error: 'model' name is missing in the configuration for '{final_model_key}' in ai_models.yml")
        log_to_file(f"Run Error: 'model' name missing for selected config key: '{final_model_key}'")
        exit(1)

    env_config["selected_model_config"] = final_model_config
    log_to_file(f"Final Model Config Used: {json.dumps(final_model_config)}")

    # --- Create Archive Directory ---
    archive_base_dir = os.path.join(SCRIPT_DIR, "archive") # Store archive relative to script
    topic_slug = re.sub(r'\W+', '_', args.topic)[:50]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_archive_dir_name = f"{timestamp}_{topic_slug}"
    run_archive_dir = os.path.join(archive_base_dir, run_archive_dir_name)
    try:
        os.makedirs(run_archive_dir, exist_ok=True)
        print(f"Archive directory for this run: {run_archive_dir}")
        # Initialize log file for this run (will be created by first log_to_file call)
        log_to_file(f"--- AI Report Generator Run Start ({timestamp}) ---")
        log_to_file(f"Run CWD: {os.getcwd()}")
        log_to_file(f"Args: {vars(args)}")
        log_to_file(f"Env Config Keys Loaded: {list(env_config.keys())}")
        log_to_file(f"Model Config Keys Loaded: {list(models_config.keys())}")
    except OSError as e:
        print(f"Error creating archive directory {run_archive_dir}: {e}. Archiving might fail.")
        run_archive_dir = None # Attempt to continue without archiving
        # Try logging to CWD if archive fails? For now, just disable.
        print("Warning: Archiving disabled for this run.")

    # --- Load Reference Documents ---
    reference_docs_content = []
    loaded_ref_paths = set() # Keep track of loaded paths to avoid duplicates

    def load_document(doc_path):
        """Helper to load content from a single document path."""
        if doc_path in loaded_ref_paths:
            print(f"    - Skipping already loaded document: {doc_path}")
            log_to_file(f"Skipping duplicate reference doc: {doc_path}")
            return None
        if not os.path.isfile(doc_path):
            print(f"  - Error: Reference document file not found or is not a file: {doc_path}")
            log_to_file(f"Error: Reference document not found/not a file: {doc_path}")
            return None

        content = None
        file_ext = os.path.splitext(doc_path)[1].lower()
        print(f"  - Processing reference document: {doc_path}")
        try:
            if file_ext == '.pdf':
                text_content = []
                with open(doc_path, 'rb') as pdf_file:
                    reader = PyPDF2.PdfReader(pdf_file)
                    if reader.is_encrypted:
                        print(f"    - Warning: Skipping encrypted PDF: {doc_path}")
                        log_to_file(f"Warning: Skipping encrypted PDF: {doc_path}")
                        return None
                    for page_num, page in enumerate(reader.pages):
                        try:
                             page_text = page.extract_text()
                             if page_text: text_content.append(page_text)
                        except Exception as page_e:
                            print(f"    - Warning: Error extracting text from page {page_num+1} of {doc_path}: {page_e}")
                            log_to_file(f"Warning: PDF page extraction error {doc_path} (Page {page_num+1}): {page_e}")
                content = "\n".join(text_content)
                print(f"    - Extracted text from PDF.")
            elif file_ext == '.docx':
                doc = docx.Document(doc_path)
                text_content = [para.text for para in doc.paragraphs if para.text]
                content = "\n".join(text_content)
                print(f"    - Extracted text from DOCX.")
            elif file_ext == '.txt':
                # Try common encodings
                encodings_to_try = ['utf-8', 'latin-1', 'windows-1252']
                for enc in encodings_to_try:
                    try:
                        with open(doc_path, 'r', encoding=enc) as f:
                            content = f.read()
                        print(f"    - Read as plain text ({enc}).")
                        break # Stop if successful
                    except UnicodeDecodeError:
                        continue # Try next encoding
                    except Exception as read_e: # Catch other read errors
                         raise read_e # Re-raise other errors
                if content is None:
                    print(f"    - Error: Could not decode text file {doc_path} with tested encodings.")
                    log_to_file(f"Error: Failed to decode text file {doc_path}")
                    return None
            else:
                print(f"    - Skipping unsupported file type: {doc_path}")
                log_to_file(f"Skipping unsupported reference file type: {doc_path}")
                return None

            if content and content.strip():
                print(f"    - Successfully loaded content ({len(content)} chars).")
                log_to_file(f"Loaded reference doc: {doc_path} ({len(content)} chars)")
                loaded_ref_paths.add(doc_path) # Mark as loaded
                return {"path": doc_path, "content": content.strip()}
            else:
                print(f"    - Warning: No text content extracted or file is empty.")
                log_to_file(f"Warning: Reference document {doc_path} empty or no text extracted.")
                return None

        except PyPDF2.errors.PdfReadError as pdf_err:
             print(f"  - Error reading PDF file {doc_path}: {pdf_err}")
             log_to_file(f"Error reading PDF file {doc_path}: {pdf_err}")
             return None
        except Exception as e:
            print(f"  - Error processing reference document {doc_path}: {e}")
            log_to_file(f"Error processing reference document {doc_path}: {e} (Type: {type(e).__name__})")
            return None

    # Load from --reference-docs
    if args.reference_docs:
        print("\nLoading specified reference documents...")
        log_to_file(f"Loading specified reference documents from: {args.reference_docs}")
        ref_doc_paths = [p.strip() for p in args.reference_docs.split(',') if p.strip()]
        for doc_path in ref_doc_paths:
            doc_content = load_document(doc_path)
            if doc_content:
                reference_docs_content.append(doc_content)

    # Load from --reference-docs-folder
    if args.reference_docs_folder:
        print(f"\nLoading reference documents from folder: {args.reference_docs_folder}")
        log_to_file(f"Loading reference documents from folder: {args.reference_docs_folder}")
        if not os.path.isdir(args.reference_docs_folder):
            print(f"  - Error: Provided path is not a valid directory: {args.reference_docs_folder}")
            log_to_file(f"Error: --reference-docs-folder path is not a directory: {args.reference_docs_folder}")
        else:
            for filename in os.listdir(args.reference_docs_folder):
                doc_path = os.path.join(args.reference_docs_folder, filename)
                # Check if it's a file before processing
                if os.path.isfile(doc_path):
                    doc_content = load_document(doc_path) # Use helper function
                    if doc_content:
                        reference_docs_content.append(doc_content)
            log_to_file(f"Finished processing reference documents folder. Total loaded so far: {len(reference_docs_content)}")

    if not reference_docs_content and (args.reference_docs or args.reference_docs_folder):
        print("Warning: No valid reference documents were loaded despite flags being set.")
        log_to_file("Warning: Reference doc flags set, but no content loaded.")

    # --- Workflow Steps ---
    try:
        # 1. Load Direct Articles URLs
        direct_article_urls = []
        if args.direct_articles:
            print(f"\nLoading direct articles list from: {args.direct_articles}")
            log_to_file(f"Loading direct articles from {args.direct_articles}")
            try:
                with open(args.direct_articles, 'r', encoding='utf-8') as f:
                    direct_article_urls = [line.strip() for line in f if line.strip() and line.strip().startswith(('http://', 'https://'))]
                if direct_article_urls:
                    print(f"Successfully loaded {len(direct_article_urls)} direct article URLs.")
                    log_to_file(f"Loaded {len(direct_article_urls)} direct URLs.")
                else:
                    print(f"Warning: File {args.direct_articles} was empty or contained no valid URLs.")
                    log_to_file(f"Warning: Direct articles file {args.direct_articles} empty or invalid.")
            except FileNotFoundError:
                print(f"Error: Direct articles file not found: {args.direct_articles}")
                log_to_file(f"Error: Direct articles file not found: {args.direct_articles}")
                if args.no_search and not reference_docs_content: # Only critical if no search AND no refs
                     raise FileNotFoundError(f"Direct articles file '{args.direct_articles}' not found, and no other input provided (--no-search used).")
            except Exception as e:
                print(f"Error reading direct articles file {args.direct_articles}: {e}")
                log_to_file(f"Error reading direct articles file {args.direct_articles}: {e}")
                if args.no_search and not reference_docs_content: # Only critical if no search AND no refs
                     raise IOError(f"Failed to read direct articles file '{args.direct_articles}' and no other input provided (--no-search used). Error: {e}")

        # 2. Determine Sources for Scraping
        sources_for_scraping = []
        if args.no_search:
            print("\n--no-search specified. Using only direct articles for scraping.")
            log_to_file("Source Determination: --no-search active. Using only direct URLs.")
            sources_for_scraping = direct_article_urls
            if not sources_for_scraping:
                 print("No direct articles provided. Scraping phase will be skipped.")
                 log_to_file("Source Determination: No direct articles for scraping.")
        else:
            print("\nDiscovering sources via AI and combining with direct articles...")
            log_to_file("Source Determination: Discovering sources + combining direct URLs.")
            if not args.search_queries:
                 raise ValueError("Search is enabled, but no keywords were provided.") # Should be caught by argparse, but safety check
            discovered_sources = discover_sources(args.search_queries, env_config)

            combined_sources = direct_article_urls + discovered_sources
            seen_sources = set()
            unique_combined_sources = []
            for src in combined_sources:
                # Basic normalization for deduplication (e.g., strip trailing slash)
                normalized_src = src.strip().rstrip('/')
                if normalized_src not in seen_sources:
                    unique_combined_sources.append(src) # Keep original URL
                    seen_sources.add(normalized_src)

            sources_for_scraping = unique_combined_sources
            print(f"Combined sources for scraping: {len(sources_for_scraping)} unique sources/URLs.")
            log_to_file(f"Source Determination: Combined sources result in {len(sources_for_scraping)} unique items for scraping.")

            if not sources_for_scraping and not reference_docs_content:
                 raise RuntimeError("No valid sources found (discovered or direct) and no reference documents loaded. Cannot proceed.")
            elif not sources_for_scraping:
                 print("Warning: No sources found for scraping, but proceeding with reference documents (if any).")
                 log_to_file("Warning: No sources found for scraping, using only reference docs.")

        # 3. Scrape Content
        scraped_content = []
        if sources_for_scraping:
            scraped_content = scrape_content(sources_for_scraping, direct_article_urls, args, env_config)
            if not scraped_content and not reference_docs_content:
                 raise RuntimeError("Failed to scrape any content and no reference documents loaded. Cannot proceed.")
            elif not scraped_content:
                  print("Warning: Failed to scrape any content, but proceeding with reference documents (if any).")
                  log_to_file("Warning: Scraping failed, using only reference docs.")
        else:
             print("\nSkipping content scraping as no sources were identified for it.")
             log_to_file("Skipping scraping phase (no sources).")

        # Check for ANY content before proceeding
        if not scraped_content and not reference_docs_content:
             raise RuntimeError("No content available from scraping or reference documents. Cannot generate a report.")

        # 4. Summarize Content
        # Summarize scraped content AND reference docs if flag is set
        summaries = summarize_content(scraped_content, reference_docs_content, args.topic, env_config, args)
        have_valid_summaries = any(s['score'] >= args.score_threshold for s in summaries if not s['summary'].startswith("Error:"))
        have_usable_ref_docs = reference_docs_content and not args.reference_docs_summarize

        if not have_valid_summaries and not have_usable_ref_docs:
             raise RuntimeError(f"No summaries met the threshold ({args.score_threshold}) and no reference documents available for direct use. Cannot generate report.")
        elif not have_valid_summaries:
             print(f"\nWarning: No summaries met the threshold ({args.score_threshold}). Report will rely solely on reference documents.")
             log_to_file(f"Warning: No summaries met threshold {args.score_threshold}. Using only reference docs for report.")

        # 5. Generate Initial Report
        initial_report_filepath, initial_report_content = generate_report(summaries, reference_docs_content, args.topic, env_config, args)
        if not initial_report_filepath or not initial_report_content:
             raise RuntimeError("Failed to generate the initial research report.")
        print(f"\nSuccessfully generated initial report (content length: {len(initial_report_content)} chars)")
        final_report_path_to_show = initial_report_filepath # Default to initial if refinement skipped/fails

        # 6. Refine Report Presentation (Conditional)
        if not args.skip_refinement:
            refined_report_filepath = refine_report_presentation(
                initial_report_content,
                args.topic,
                env_config,
                timestamp, # Pass timestamp
                topic_slug # Pass topic_slug
            )
            if refined_report_filepath:
                print(f"\nSuccessfully refined report presentation.")
                final_report_path_to_show = refined_report_filepath # Update to show the refined path
            else:
                print("\nWarning: Report refinement failed or was skipped. The initial (unrefined) report is available.")
                log_to_file("Warning: Report refinement failed or was skipped.")
                # Keep final_report_path_to_show as the initial path
        else:
            print("\nSkipping report refinement step as requested by --skip-refinement.")
            log_to_file("Skipping report refinement step (--skip-refinement=True).")


        # --- Completion ---
        end_time = time.time()
        duration = end_time - start_time
        print("\n--- AI Report Generation Workflow Complete ---")
        print(f"Final Report Output: {final_report_path_to_show}") # Show path to refined or initial
        if run_archive_dir:
             print(f"Run Archive/Logs: {run_archive_dir}")
        print(f"Total Duration: {duration:.2f} seconds")
        log_to_file(f"--- AI Report Generator Run End --- Duration: {duration:.2f}s ---")

    except Exception as e:
        print(f"\n--- FATAL WORKFLOW ERROR ---")
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback_str = traceback.format_exc()
        print("\n--- Traceback ---")
        print(traceback_str)
        print("-----------------")
        log_to_file(f"FATAL WORKFLOW ERROR: {e}\n{traceback_str}")
        exit(1)


if __name__ == "__main__":
    # Check essential imports early
    try:
        import newspaper
        import selenium
        from webdriver_manager.chrome import ChromeDriverManager
        import PyPDF2
        import docx
        import yaml
        from dotenv import load_dotenv
    except ImportError as e:
        print(f"\nImport Error: {e}. One or more required libraries are missing.")
        print("Please ensure all dependencies are installed. You might need to run:")
        print("pip install newspaper4k selenium webdriver-manager python-dotenv PyYAML requests beautifulsoup4 PyPDF2 python-docx")
        print("\nAlternatively, check your Python environment and interpreter.")
        exit(1)

    main()