import os
import datetime
import time
import re
import traceback # For printing tracebacks
import random # For random delays (used in scraping, but import here for completeness)

# Import functions from the new modular structure
from functions.config import load_config
from functions.args import parse_arguments
from functions.search.discovery import discover_sources
from functions.scraping.content import scrape_content
from functions.scraping.documents import load_reference_documents
from functions.processing.summarization import summarize_content
from functions.processing.report_generation import generate_report, refine_report_presentation, convert_markdown_to_pdf
from functions.utils import log_to_file, set_run_archive_dir, get_run_archive_dir # Import run_archive_dir setter/getter

# --- Main Execution ---

def main():
    """Main function to orchestrate the AI report generation workflow."""
    print("--- Starting AI Report Generator (Refactored) ---")
    start_time = time.time()

    # --- Setup ---
    # script_dir is the directory of this script (project root)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Script directory: {script_dir}")
    print(f"Current working directory: {os.getcwd()}")

    # Load configuration and models
    env_config, models_config = load_config(script_dir) # Pass script_dir to load_config

    # Parse arguments (args.py handles loading model keys dynamically)
    args = parse_arguments(models_config) # Pass models_config to parse_arguments

    # --- Determine Final Model Configuration ---
    # Priority: Command Line (--llm-model) > Environment Variable (DEFAULT_MODEL_CONFIG) > Default ('default_model')
    final_model_key = "default_model" # Ultimate fallback
    env_model_key = os.getenv("DEFAULT_MODEL_CONFIG")

    if args.llm_model:
        final_model_key = args.llm_model
        print(f"Using LLM model specified via command line: '{final_model_key}'")
        # Store the finally chosen key in config for potential reference later (e.g., in call_ai_api error messages)
        env_config['final_model_key'] = final_model_key # Use env_config dict
        log_to_file(f"Model Selection: Using command line override: '{final_model_key}'")
    elif env_model_key:
        final_model_key = env_model_key
        print(f"Using LLM model specified via .env: '{final_model_key}'")
        env_config['final_model_key'] = final_model_key # Use env_config dict
        log_to_file(f"Model Selection: Using .env setting: '{final_model_key}'")
    else:
        print(f"Using default LLM model: '{final_model_key}' (Neither --llm-model nor DEFAULT_MODEL_CONFIG set)")
        env_config['final_model_key'] = final_model_key # Use env_config dict
        log_to_file(f"Model Selection: Using default: '{final_model_key}'")

    # Validate the final key and get the configuration from the already loaded models_config
    final_model_config = models_config.get(final_model_key)
    if not final_model_config or not isinstance(final_model_config, dict):
        print(f"Error: Final selected model key '{final_model_key}' configuration not found or invalid in ai_models.yml")
        print(f"Available configurations: {list(models_config.keys())}")
        log_to_file(f"Run Error: Invalid final model key selected: '{final_model_key}'")
        exit(1)
    if 'model' not in final_model_config:
        print(f"Error: 'model' name is missing in the configuration for '{final_model_key}' in ai_models.yml")
        log_to_file(f"Run Error: 'model' name missing for selected config key: '{final_model_key}'")
        exit(1)

    # Store the final selected config back into the main config dict for use by call_ai_api
    env_config["selected_model_config"] = final_model_config # Use env_config dict
    log_to_file(f"Final Model Config Used: {final_model_config}")
    # --- End Final Model Configuration Determination ---


    # Create Archive Directory for this run
    archive_base_dir = os.path.join(script_dir, "archive") # Store archive relative to script
    topic_slug = re.sub(r'\W+', '_', args.topic)[:50] # Sanitize topic for dir name
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_archive_dir_name = f"{timestamp}_{topic_slug}"
    run_archive_dir_path = os.path.join(archive_base_dir, run_archive_dir_name)

    # Set the global run_archive_dir in the utils module
    set_run_archive_dir(run_archive_dir_path)

    try:
        os.makedirs(run_archive_dir_path, exist_ok=True)
        print(f"Created archive directory: {run_archive_dir_path}")
        # Initialize log file for this run
        log_to_file(f"--- AI Report Generator Run Start ({timestamp}) ---")
        log_to_file(f"Run CWD: {os.getcwd()}")
        log_to_file(f"Args: {vars(args)}")
        log_to_file(f"Env Config Keys Loaded: {list(env_config.keys())}") # Log env_config keys
        log_to_file(f"Model Config Keys Loaded: {list(models_config.keys())}") # Log models_config keys
    except OSError as e:
        print(f"Error creating archive directory {run_archive_dir_path}: {e}")
        # Reset the global run_archive_dir if creation fails
        set_run_archive_dir(None)
        log_to_file("Error: Failed to create archive directory. Archiving disabled for this run.")


    # --- Workflow Steps ---
    try:
        # 1. Load Reference Documents
        # load_reference_documents now handles both --reference-docs and --reference-docs-folder
        reference_docs_content = load_reference_documents(args)
        if not reference_docs_content and (args.reference_docs or args.reference_docs_folder):
             print("Warning: No valid reference documents were loaded from specified paths or folder.")
             log_to_file("Warning: Reference docs/folder specified, but no content loaded.")

        # 2. Load Direct Articles (if specified)
        direct_article_urls = []
        if args.direct_articles:
            print(f"\nLoading direct articles from: {args.direct_articles}")
            log_to_file(f"Attempting to load direct articles from {args.direct_articles}")
            try:
                with open(args.direct_articles, 'r', encoding='utf-8') as f:
                    direct_article_urls = [line.strip() for line in f if line.strip() and line.strip().startswith(('http://', 'https://'))]
                if direct_article_urls:
                    print(f"Successfully loaded {len(direct_article_urls)} direct article URLs.")
                    log_to_file(f"Loaded {len(direct_article_urls)} direct URLs: {direct_article_urls}")
                else:
                    print(f"Warning: File {args.direct_articles} was empty or contained no valid URLs.")
                    log_to_file(f"Warning: Direct articles file {args.direct_articles} empty or invalid.")
            except FileNotFoundError:
                print(f"Error: Direct articles file not found: {args.direct_articles}")
                log_to_file(f"Error: Direct articles file not found: {args.direct_articles}")
                if args.no_search: # Critical if no search is allowed
                     raise FileNotFoundError(f"Direct articles file '{args.direct_articles}' not found, and --no-search was specified.")
                # If search is allowed, we can potentially continue without direct articles
            except Exception as e:
                print(f"Error reading direct articles file {args.direct_articles}: {e}")
                log_to_file(f"Error reading direct articles file {args.direct_articles}: {e}")
                if args.no_search: # Critical if no search is allowed
                     raise IOError(f"Failed to read direct articles file '{args.direct_articles}' due to error: {e}, and --no-search was specified.")

        # 3. Determine Sources/URLs to Scrape (and potentially discover sources)
        sources_for_scraping = [] # URLs/Subreddits to actually scrape
        if args.no_search:
            print("--no-search specified. Skipping source discovery and web search.")
            log_to_file("Source Determination: --no-search active. Skipping discovery/web search.")
            # Use only direct articles for scraping, if provided. Reference docs are handled separately.
            sources_for_scraping = direct_article_urls
            if sources_for_scraping:
                 print(f"Using {len(sources_for_scraping)} URLs from --direct-articles for scraping.")
                 log_to_file(f"Source Determination: Using {len(sources_for_scraping)} direct URLs for scraping.")
            else:
                 print("No direct articles provided via --direct-articles. Skipping scraping phase.")
                 log_to_file("Source Determination: No direct articles provided. Skipping scraping phase.")
            # Argument parser already ensures we have *some* offline content (direct_articles OR reference_docs OR reference_docs_folder)
        else:
            # Search is active, discover sources if needed
            print("Discovering sources via AI and combining with direct articles (if any)...")
            log_to_file("Source Determination: Discovering sources and combining with direct articles.")
            # Keywords are required here (validated by parser)
            discovered_sources = discover_sources(args.search_queries, env_config, args) # Pass env_config and args

            # Combine and deduplicate sources for scraping
            combined_sources = direct_article_urls + discovered_sources # Prioritize direct URLs
            seen_sources = set()
            unique_combined_sources = []
            for src in combined_sources:
                normalized_src = src # Keep original for now, simple exact match dedupe
                if normalized_src not in seen_sources:
                    unique_combined_sources.append(src)
                    seen_sources.add(normalized_src)

            sources_for_scraping = unique_combined_sources
            print(f"Combined sources for scraping: {len(sources_for_scraping)} unique sources/URLs.")
            log_to_file(f"Source Determination: Combined {len(discovered_sources)} discovered sources with {len(direct_article_urls)} direct URLs, resulting in {len(sources_for_scraping)} unique items for scraping.")

            if not sources_for_scraping and not reference_docs_content:
                 # If search was active but we found no sources AND have no reference docs, we can't proceed.
                 raise RuntimeError("No valid sources were discovered or provided directly, and no reference documents loaded. Cannot proceed.")
            elif not sources_for_scraping:
                 print("Warning: No sources discovered or provided for scraping, but proceeding with reference documents.")
                 log_to_file("Warning: No sources found for scraping, using only reference docs.")


        # 4. Scrape Content (only if sources_for_scraping is not empty)
        scraped_content = []
        if sources_for_scraping:
            # Pass direct_article_urls to scrape_content
            scraped_content = scrape_content(sources_for_scraping, direct_article_urls, args, env_config)
            if not scraped_content and not reference_docs_content:
                 # If scraping failed AND we have no reference docs, we can't proceed.
                 raise RuntimeError("Failed to scrape any content from the provided/discovered sources, and no reference documents loaded.")
            elif not scraped_content:
                  print("Warning: Failed to scrape any content, but proceeding with reference documents.")
                  log_to_file("Warning: Scraping failed, using only reference docs.")
        else:
             print("Skipping content scraping as no sources were provided/discovered for it.")
             # We proceed here because reference_docs_content might still exist

        # Check if we have ANY content (scraped or reference) before summarizing
        if not scraped_content and not reference_docs_content:
             raise RuntimeError("No content available from scraping or reference documents. Cannot proceed.")

        # 5. Summarize Content (scraped and/or reference docs if --reference-docs-summarize)
        # Pass both scraped_content and reference_docs_content to summarize_content
        summaries = summarize_content(scraped_content, reference_docs_content, args.topic, env_config, args)
        # Summarize_content now handles logic for reference docs internally based on args.reference_docs_summarize
        # Check if ANY summaries were successfully generated (score >= 0) OR if we have non-summarized reference docs to use
        have_valid_summaries = any(s['score'] >= 0 for s in summaries)
        have_nonsummarized_ref_docs = reference_docs_content and not args.reference_docs_summarize

        if not have_valid_summaries and not have_nonsummarized_ref_docs:
             raise RuntimeError(f"No summaries met the threshold ({args.score_threshold}) and no reference documents available for direct use. Cannot generate report.")
        elif not have_valid_summaries:
             print(f"\nWarning: No summaries met the threshold ({args.score_threshold}). Report will rely solely on reference documents.")
             log_to_file(f"Warning: No summaries met threshold {args.score_threshold}. Using only reference docs for report.")


        # 6. Generate Initial Report
        # Call generate_report and check the return value before unpacking
        report_generation_result = generate_report(summaries, reference_docs_content, args.topic, env_config, args)

        # Check if report generation was successful (returned 3 values)
        if report_generation_result and len(report_generation_result) == 3:
            initial_report_filepath, initial_report_content, top_summaries_for_refinement = report_generation_result
            if not initial_report_filepath or not initial_report_content:
                 # This condition might be redundant now but kept for safety
                 raise RuntimeError("generate_report returned success status but file path or content is missing.")
            print(f"\nSuccessfully generated initial report (content length: {len(initial_report_content)} chars)")
            final_report_path_to_show = initial_report_filepath # Default to initial if refinement skipped/fails
        else:
            # Handle the case where generate_report failed (returned None, None or None, None, None)
            raise RuntimeError("Failed to generate the initial research report. Check logs for details from generate_report function.")
            # Note: top_summaries_for_refinement will not be defined in this case,
            # so refinement step below will be skipped or needs adjustment if it relies on it.

        # 7. Refine Report Presentation (Conditional)
        if args.skip_refinement:
            print("\nSkipping report refinement step as requested by --skip-refinement.")
            log_to_file("Skipping report refinement step (--skip-refinement=True).")
        elif 'initial_report_content' not in locals() or not initial_report_content:
            # This case should only be hit if generate_report succeeded but returned empty content,
            # which is unlikely given the checks, but handled defensively.
            print("\nSkipping report refinement because initial report content is missing or empty.")
            log_to_file("Refinement Skipped: Initial report content missing or empty.")
        elif 'top_summaries_for_refinement' not in locals():
             # This case implies generate_report succeeded but somehow didn't return the summaries list.
             print("\nWarning: Cannot refine report because 'top_summaries_for_refinement' is missing. Skipping refinement.")
             log_to_file("Refinement Skipped: 'top_summaries_for_refinement' not available.")
        else:
            # Proceed with refinement attempt as initial report exists and summaries are available
            print("\nAttempting report refinement...")
            refined_report_filepath = refine_report_presentation(
                initial_report_content,
                top_summaries_for_refinement,
                reference_docs_content, # Pass the list of reference docs
                args,                   # Pass the args object
                args.topic,
                env_config,
                timestamp,              # Pass timestamp
                topic_slug              # Pass topic_slug
            )
            if refined_report_filepath:
                print(f"\nSuccessfully refined report presentation.")
                final_report_path_to_show = refined_report_filepath # Update path
            else:
                print("\nWarning: Report refinement failed. The initial (unrefined) report is available.")
                log_to_file("Warning: Report refinement failed.")
                # Keep final_report_path_to_show as the initial path (already set in step 5)

        # --- Completion ---
        # Safety check before printing the final path
        if 'final_report_path_to_show' not in locals():
             # This case should ideally not be reachable due to the RuntimeError in step 5
             # if initial generation fails.
             print("\n--- FATAL ERROR ---")
             print("Error: Could not determine the final report path. Workflow halted.")
             log_to_file("Completion Error: final_report_path_to_show was not defined.")
             raise RuntimeError("Internal error: Final report path could not be determined before completion.")

        end_time = time.time()
        duration = end_time - start_time
        print("\n--- AI Report Generation Workflow Complete ---")
        # Check if final_report_path_to_show is a list (for markdown and PDF)
        if isinstance(final_report_path_to_show, list):
            print("Final Report Outputs:")
            for path in final_report_path_to_show:
                print(f"- {path}")
        else:
            print(f"Final Report Output: {final_report_path_to_show}") # Show path to refined or initial

        # Check if run_archive_dir was successfully created before printing
        final_archive_dir = get_run_archive_dir()
        if final_archive_dir:
             print(f"Run Archive/Logs: {final_archive_dir}")
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
    # Ensure necessary libraries are installed
    try:
        import newspaper # newspaper4k
        import selenium
        from webdriver_manager.chrome import ChromeDriverManager
        import PyPDF2
        import docx
        import requests
        import yaml
        import dotenv
        import bs4
        import markdown
        import pdfkit
    except ImportError as e:
        print(f"\nImport Error: {e}. One or more required libraries are missing.")
        print("Please ensure all dependencies are installed. You might need to run:")
        print("pip install newspaper4k selenium webdriver-manager python-dotenv PyYAML requests beautifulsoup4 pypdf python-docx markdown pdfkit")
        print("\nAlternatively, check your Python environment and interpreter.")
        exit(1)

    main()
