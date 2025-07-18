import os
import re
import time
import random
import urllib.parse
import requests

# Import necessary functions from utils, ai, and search APIs
from ..utils import log_to_file, parse_ai_tool_response
from ..ai import call_ai_api
from .google import search_google_api
from .brave import search_brave_api

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
]


def discover_sources(keywords_list, config, args):
    """Uses AI to discover relevant websites and subreddits."""
    print("\nDiscovering sources via AI...")
    log_to_file("Starting source discovery via AI.")
    discovery_keyword_str = " | ".join(keywords_list)
    print(f"Using keywords for discovery: '{discovery_keyword_str}'")
    log_to_file(f"Keywords for discovery: '{discovery_keyword_str}'")

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
    log_to_file(f"Discovered {len(sources_list)} potential sources. Starting validation.")
    # --- Source Validation (Optional but recommended) ---
    validated_sources = []
    for source in sources_list:
        is_valid = False
        check_target_display = source # What to display initially

        try:
            if source.startswith('r/'):
                is_valid = True
                print(f"  - Checking: {check_target_display}... OK (Subreddit)")
                log_to_file(f"Source Validation: {check_target_display}... OK (Subreddit)")
            elif source.startswith(('http://', 'https://')):
                parsed_uri = urllib.parse.urlparse(source)
                # Construct base URL (scheme + domain) ensuring trailing slash
                base_url = f"{parsed_uri.scheme}://{parsed_uri.netloc}/"
                check_target_display = f"Base Domain {base_url} (from {source})" # More descriptive display

                print(f"  - Checking: {check_target_display}...", end="")
                # Use base_url for the actual check
                response = requests.head(base_url, headers={'User-Agent': random.choice(USER_AGENTS)}, timeout=10, allow_redirects=True)
                if response.status_code < 400:
                    is_valid = True
                    print(f" OK (Status: {response.status_code})")
                    log_to_file(f"Source Validation: {check_target_display}... OK (Status: {response.status_code})")
                else:
                    print(f" Failed (Status: {response.status_code})")
                    log_to_file(f"Source Validation: {check_target_display}... Failed (Status: {response.status_code})")
            else:
                 # Should not happen due to normalization earlier, but handle defensively
                 print(f"  - Checking: {check_target_display}... Failed (Invalid Format)")
                 log_to_file(f"Source Validation: {check_target_display}... Failed (Invalid Format)")

        except requests.exceptions.RequestException as e:
             # Add the print prefix here for consistency with other failure messages
             print(f" Failed (Error: {type(e).__name__})")
             log_to_file(f"Source Validation: {check_target_display}... Failed (Error: {type(e).__name__}) - {e}")
        except Exception as e:
             # Add the print prefix here for consistency
            print(f" Failed (Unexpected Validation Error: {e})")
            log_to_file(f"Source Validation: {check_target_display}... Failed (Unexpected Error: {e})")

        if is_valid:
            validated_sources.append(source) # Add original source if base domain is valid
        time.sleep(random.uniform(0.3, 0.8)) # Short delay

    print(f"Validation complete. Using {len(validated_sources)} accessible sources.")
    log_to_file(f"Source Discovery: Validation complete. Using {len(validated_sources)} accessible sources: {validated_sources}")

    # --- Filter Reddit sources if --no-reddit is specified ---
    if args.no_reddit:
        non_reddit_sources = [src for src in validated_sources if not (src.startswith('r/') or 'reddit.com/r/' in src)]
        print(f"Filtering Reddit sources due to --no-reddit flag. Using {len(non_reddit_sources)} non-Reddit sources.")
        log_to_file(f"Source Discovery: Filtered out Reddit sources due to --no-reddit. Using {len(non_reddit_sources)} sources: {non_reddit_sources}")
        return non_reddit_sources
    else:
        return validated_sources

def perform_direct_keyword_search(keywords_list, config, args):
    """
    Performs a direct web search for each keyword using the specified search API
    and returns a list of unique URLs.
    """
    print("\nPerforming direct keyword web search...")
    log_to_file("Starting direct keyword web search.")
    
    all_found_urls = set()
    results_limit_per_api_call = args.per_keyword_results if args.per_keyword_results else args.max_web_results # Use per-keyword limit if set, else max-web-results

    for keyword_idx, keyword in enumerate(keywords_list, 1):
        search_query = keyword.strip()
        if not search_query:
            continue

        print(f"  - Searching for keyword {keyword_idx}/{len(keywords_list)}: '{search_query}' (Limit: {results_limit_per_api_call})")
        log_to_file(f"Direct Keyword Search: Query {keyword_idx}: '{search_query}' (Limit: {results_limit_per_api_call})")

        api_results = None
        primary_api = args.api
        fallback_api = 'brave' if primary_api == 'google' else 'google'

        # Attempt Primary API
        print(f"    - Attempting primary API: {primary_api}")
        log_to_file(f"Direct Keyword Search: Attempting primary API: {primary_api}")
        if primary_api == 'google':
            api_results = search_google_api(search_query, config, results_limit_per_api_call, args.from_date, args.to_date)
        else: # brave
            api_results = search_brave_api(search_query, config, results_limit_per_api_call, args.from_date, args.to_date)

        quota_hit = api_results == 'quota_error'
        failed = api_results is None

        if quota_hit:
            print(f"    - Primary API '{primary_api}' quota limit hit.")
            log_to_file(f"Direct Keyword Search: Primary API '{primary_api}' quota limit hit.")
        elif failed:
            print(f"    - Primary API '{primary_api}' failed or returned no results.")
            log_to_file(f"Direct Keyword Search: Primary API '{primary_api}' failed or returned no results.")

        # Attempt Fallback API if primary failed (not due to quota initially) or hit quota
        if failed or quota_hit:
            print(f"    - Attempting fallback API: {fallback_api}")
            log_to_file(f"Direct Keyword Search: Attempting fallback API: {fallback_api}")
            if fallback_api == 'google':
                api_results_fallback = search_google_api(search_query, config, results_limit_per_api_call, args.from_date, args.to_date)
            else: # brave
                api_results_fallback = search_brave_api(search_query, config, results_limit_per_api_call, args.from_date, args.to_date)

            if api_results_fallback == 'quota_error':
                print(f"    - Fallback API '{fallback_api}' also hit quota limit.")
                log_to_file(f"Direct Keyword Search: Fallback API '{fallback_api}' also hit quota limit.")
                if quota_hit: api_results = None # Both hit quota, give up
            elif api_results_fallback is None:
                print(f"    - Fallback API '{fallback_api}' also failed or returned no results.")
                log_to_file(f"Direct Keyword Search: Fallback API '{fallback_api}' also failed or returned no results.")
                if quota_hit: api_results = None # Primary hit quota, fallback failed
            elif isinstance(api_results_fallback, list):
                print(f"    - Fallback API '{fallback_api}' succeeded.")
                log_to_file(f"Direct Keyword Search: Fallback API '{fallback_api}' succeeded.")
                api_results = api_results_fallback # Use fallback results

        # Add successfully found URLs
        if isinstance(api_results, list):
            added_count = 0
            for url in api_results:
                if url not in all_found_urls:
                    all_found_urls.add(url)
                    added_count += 1
            print(f"    - Added {added_count} new unique URLs from API search for '{search_query}'.")
            log_to_file(f"Direct Keyword Search: Added {added_count} URLs for query '{search_query}'.")
        else:
            print(f"    - No URLs obtained from APIs for keyword '{search_query}'.")
            log_to_file(f"Direct Keyword Search Failed/Empty for keyword '{search_query}'.")

        time.sleep(random.uniform(1, 2)) # Delay between API calls for different keywords

    final_urls = list(all_found_urls)
    print(f"\nFinished direct keyword web search. Total unique URLs found: {len(final_urls)}")
    log_to_file(f"Direct Keyword Search: Complete. Total unique URLs: {len(final_urls)}")
    return final_urls