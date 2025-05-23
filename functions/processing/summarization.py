import os
import re
import time
import random
import json
import traceback # For printing tracebacks

# Import necessary functions from utils and ai
from ..utils import log_to_file, clean_thinking_tags, parse_ai_tool_response, get_run_archive_dir
from ..ai import call_ai_api

def summarize_content(scraped_data, reference_docs, topic, config, args):
    """
    Uses AI to summarize scraped content and optionally reference documents,
    assigning a relevance score to each.
    """
    print(f"\n--- Starting Summarization & Scoring Phase ---")
    log_to_file("Starting summarization and scoring phase.")
    content_to_process = []
    # Add scraped data (which are dictionaries)
    for idx, data_item in enumerate(scraped_data): # Iterate over scraped_data (list of dicts)
        content = data_item.get("content", "")
        url = data_item.get("url", "")
        if content and url: # Only add if we have both content and URL
            content_to_process.append({
                "type": "scraped",
                "content": content,
                "url": url, # Pass the URL along
                "source_index": idx + 1 # Keep original index if needed
            })
        else:
            log_to_file(f"Warning: Skipping scraped item index {idx+1} due to missing URL or content during summary prep.")

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
        # Determine the source identifier based on type
        if item_type == "scraped":
            # Use the 'url' key added when building content_to_process
            item_source_id = item.get("url", f"Scraped_URL_Missing_{i}") # Use i as fallback index
        elif item_type == "reference":
            item_source_id = item.get("path", f"Reference_Path_Missing_{i}")
        else: # Should not happen
            item_source_id = f"Unknown_Source_{i}"

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

        # --- Retry Logic for Summarization ---
        max_retries = 3
        retry_delay = 5 # seconds
        summary = "Error: Summarization Failed (Unknown)"
        score = -1
        summary_details = {"type": item_type, "source_id": item_source_id} # Store type and source id
        raw_response = None
        cleaned_response = None

        for attempt in range(max_retries):
            print(f"\rSummarizing & Scoring {i}/{total_pieces} ({item_type}: {os.path.basename(str(item_source_id))[:30]}...) (Attempt {attempt + 1}/{max_retries}) (Success: {successful_summaries})", end='', flush=True)

            # Use a reasonable timeout for summarization
            raw_response, cleaned_response = call_ai_api(prompt, config, tool_name=f"Summary_{i}_{item_type}_Attempt{attempt+1}", timeout=180)

            if not cleaned_response:
                log_to_file(f"Error: API call failed for Summary_{i} ({item_source_id}) on attempt {attempt + 1}.")
                summary = f"Error: Could not summarize text piece {i} ({item_source_id}) (API call failed)"
                score = -1
                break # No point retrying if API call fails

            # Try parsing
            parsed_summary = parse_ai_tool_response(cleaned_response, "toolScrapeSummary")

            # Check for the specific error: tag missing
            is_tag_missing_error = (parsed_summary == cleaned_response and '<toolScrapeSummary>' not in cleaned_response.lower())

            if is_tag_missing_error:
                log_msg = f"Error: Summary {i} ({item_source_id}) parsing failed - <toolScrapeSummary> tag missing (Attempt {attempt + 1}/{max_retries})."
                log_to_file(log_msg)
                if attempt < max_retries - 1:
                    print(f"\n{log_msg} Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    continue # Go to the next attempt
                else:
                    # Last attempt failed for tag missing
                    summary = f"Error: Could not parse summary {i} ({item_source_id}) (<toolScrapeSummary> tag missing after {max_retries} attempts)"
                    score = -1
                    break # Exit loop after final attempt failure
            elif not parsed_summary:
                # Handle empty tag error (no retry needed for this)
                log_to_file(f"Error: Summary {i} ({item_source_id}) parsing failed - No content found in <toolScrapeSummary> tag.")
                summary = f"Error: Could not parse summary {i} ({item_source_id}) (empty tag)"
                score = -1
                break # Exit loop, parsing failed differently
            else:
                # Success! Summary parsed correctly
                summary = parsed_summary
                # Now parse the score
                score_match = re.search(r'<summaryScore>(\d{1,2})</summaryScore>', cleaned_response, re.IGNORECASE)
                if score_match:
                    try:
                        parsed_score = int(score_match.group(1))
                        if 0 <= parsed_score <= 10:
                            score = parsed_score
                            successful_summaries += 1 # Increment here on successful parse + score
                        else:
                            log_to_file(f"Warning: Summary {i} ({item_source_id}) score '{parsed_score}' out of range (0-10). Using -1.")
                            score = -1 # Treat out-of-range score as invalid for threshold check later
                    except ValueError:
                        log_to_file(f"Warning: Could not parse summary {i} ({item_source_id}) score '{score_match.group(1)}'. Using -1.")
                        score = -1
                else:
                    log_msg = f"Warning: Could not find/parse <summaryScore> tag for summary {i} ({item_source_id}). Using -1."
                    print(f"\n{log_msg}") # Print warning to console as well
                    log_to_file(log_msg)
                    # Log the actual response when score parsing fails to help debug
                    log_to_file(f"--- AI Response Causing Score Parse Failure (Summary {i}) ---\n{cleaned_response}\n--- End Response ---")
                    score = -1
                break # Exit loop on successful summary parse (even if score failed)

        # --- End Retry Logic ---

        summary_details = {"type": item_type, "source_id": item_source_id, 'summary': summary, 'score': score} # Recreate dict with all details
        summaries_with_scores.append(summary_details)

        # Use the getter function for run_archive_dir
        run_archive_dir = get_run_archive_dir()
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