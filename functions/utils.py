import os
import datetime
import re
import traceback # For printing tracebacks

# Global variable for archive directory
run_archive_dir = None

def set_run_archive_dir(path):
    """Sets the global run_archive_dir variable."""
    global run_archive_dir
    run_archive_dir = path

def get_run_archive_dir():
    """Gets the global run_archive_dir variable."""
    global run_archive_dir
    return run_archive_dir

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