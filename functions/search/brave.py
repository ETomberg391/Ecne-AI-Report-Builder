import requests
import json
import time
import random
import datetime # Needed for date parsing
import urllib.parse # Needed for URL parsing

# Import log_to_file from utils
from ..utils import log_to_file

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
        # Log the exact request details before sending
        prepared_request = requests.Request('GET', search_url, headers=headers, params=params).prepare()
        log_to_file(f"Brave API Request Details:\n  URL: {prepared_request.url}\n  Headers: {prepared_request.headers}")
        print(f"    - Requesting URL: {prepared_request.url}") # Also print URL for easier debugging

        response = requests.get(search_url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        search_data = response.json()
        log_to_file(f"Brave API Raw Response Body:\n{json.dumps(search_data, indent=2)}") # Log the raw JSON response

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