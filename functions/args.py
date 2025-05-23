import argparse
import os
import yaml
import datetime
import re

from .config import load_config # Assuming load_config is in functions.config

def parse_arguments():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate an AI research report.")

    # --- Load model keys dynamically for choices ---
    available_model_keys = []

    # --- Define Arguments ---
    parser.add_argument("--keywords", type=str, default=None, help="Comma-separated keywords/phrases for searching (required unless --no-search is used).")
    parser.add_argument("--topic", type=str, required=True, help="The main topic phrase for the research report.")
    # The choices for --llm-model will come from the passed models_config
    # parser.add_argument("--llm-model", type=str, default=None, choices=available_model_keys if available_model_keys else None,
    #                     help="Specify the LLM configuration key from ai_models.yml to use (overrides .env setting).")
    parser.add_argument("--api", choices=['google', 'brave'], default='google', help="Preferred search API ('google' or 'brave').")
    parser.add_argument("--from_date", type=str, default=None, help="Start date for search (YYYY-MM-DD).")
    parser.add_date = validate_date(args.from_date)
    args.to_date = validate_date(args.to_date)

    args.search_queries = search_queries
    print(f"Parsed Args: {vars(args)}")

    if args.no_search and not args.direct_articles and not args.reference_docs and not args.reference_docs_folder:
        parser.error("--no-search requires at least one of --direct-articles, --reference-docs, or --reference-docs-folder.")

    return args

# Need to adjust the function signature to accept models_config
def parse_arguments(models_config):
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate an AI research report.")

    # --- Load model keys dynamically for choices ---
    available_model_keys = list(models_config.keys()) if models_config and isinstance(models_config, dict) else []
    if not available_model_keys:
        print("Warning: No LLM model configurations found in ai_models.yml. --llm-model choices will be unavailable.")
        # Allow the script to proceed, but the --llm-model argument won't have choices.
        # The check for a valid selected model will happen in main.

    # --- Define Arguments ---
    parser.add_argument("--keywords", type=str, default=None, help="Comma-separated keywords/phrases for searching (required unless --no-search is used).")
    parser.add_argument("--topic", type=str, required=True, help="The main topic phrase for the research report.")
    # Use the available_model_keys for choices
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
    parser.add_argument("--skip_refinement", action="store_true", help="Skip the final report refinement step.")

    parser.add_argument("--no-reddit", action="store_true", help="Exclude Reddit sources from discovery and scraping.")
    # Add --report argument from new_script_builder.py
    parser.add_argument("--report", action="store_true", help="Generate a research report in addition to the script.")

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

    # Add check from new_script_builder.py for --no-search without offline content
    if args.no_search and not args.direct_articles and not args.reference_docs and not args.reference_docs_folder:
         parser.error("--no-search requires at least one of --direct-articles, --reference-docs, or --reference-docs-folder.")


    return args