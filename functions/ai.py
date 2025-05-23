import requests
import json
import time
import random
import traceback # For printing tracebacks

# Import necessary functions from utils
from .utils import log_to_file, clean_thinking_tags

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