import os
import datetime
import json
import re
import time
import markdown # For converting markdown to HTML
import pdfkit # For converting HTML to PDF
import platform # For OS-specific checks
import traceback # For printing tracebacks

# Import necessary functions from utils and ai
from ..utils import log_to_file, clean_thinking_tags, parse_ai_tool_response, get_run_archive_dir
from ..ai import call_ai_api

def generate_report(summaries_with_scores, reference_docs_content, topic, config, args):
    """Uses AI to generate the initial research report."""
    print("\n--- Starting Initial Report Generation ---")
    log_to_file(f"Starting initial report generation. Topic: {topic}")

    # --- Prepare Context ---
    valid_summaries = [s for s in summaries_with_scores if s['score'] >= args.score_threshold and not s['summary'].startswith("Error:")]
    combined_summaries_text = f"No valid summaries met the score threshold ({args.score_threshold}) or were generated without errors."
    num_summaries_used = len(valid_summaries)
    top_summaries = [] # Initialize top_summaries to ensure it's always defined

    if valid_summaries:
        top_summaries = sorted(valid_summaries, key=lambda x: x['score'], reverse=True) # Assign here if summaries exist
        print(f"Using {num_summaries_used} summaries (score >= {args.score_threshold}) for report generation.")
        log_to_file(f"Report Gen: Using {num_summaries_used} summaries meeting score threshold {args.score_threshold}.")
        combined_summaries_text = "\n\n".join([
            # Use source_id which now correctly holds URL for scraped items or path for reference docs
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
         return None, None, None # Return None for path, content, and summaries list

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
    run_archive_dir = get_run_archive_dir()
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
        return None, None, None
    # --- Parse and Save Initial Report ---
    report_text = None
    max_retries = 3
    retry_delay = 5

    for attempt in range(max_retries):
        report_text = parse_ai_tool_response(cleaned_response, "reportContent")

        # Check if parsing failed or returned nothing *or* returned the full response
        if not report_text or report_text == clean_thinking_tags(cleaned_response):
            if attempt < max_retries - 1:  # If we still have retries left
                print(f"\nWarning: Could not parse <reportContent> tag (Attempt {attempt + 1}/{max_retries})")
                print(f"Waiting {retry_delay} seconds before retry...")
                log_to_file(f"Report Gen Warning: Parse attempt {attempt + 1} failed, retrying in {retry_delay}s")
                time.sleep(retry_delay)

                # Try generating the report again
                raw_response, cleaned_response = call_ai_api(prompt, config, tool_name=f"ReportGeneration_Retry_{attempt + 1}", timeout=3000)

                if not cleaned_response:
                    print(f"\nError: Failed to get API response on retry {attempt + 1}")
                    log_to_file(f"Report Gen Error: API call failed on retry {attempt + 1}")
                    continue
            else:  # Last attempt failed
                print("\nError: Could not parse valid <reportContent> after all retry attempts.")
                log_to_file(f"Report Gen Error: Failed to parse <reportContent> tag after {max_retries} attempts.\nLast Response:\n{clean_thinking_tags(cleaned_response)}")
                if run_archive_dir:
                    failed_report_path = os.path.join(run_archive_dir, "report_INITIAL_FAILED_PARSE.txt")
                    try:
                        with open(failed_report_path, 'w', encoding='utf-8') as frf: frf.write(clean_thinking_tags(cleaned_response) or "Original cleaned response was empty.")
                    except IOError: pass
                return None, None, None  # Return None for path, content, and summaries list
        else:  # Successfully parsed content
            print(f"\nSuccessfully parsed report content{' on retry ' + str(attempt) if attempt > 0 else ''}.")
            break

    # --- Build References String ---
    references_string = "References:\n"
    # Use top_summaries as it's the sorted list used for context and meets the score threshold
    if 'top_summaries' in locals() and top_summaries:
         for i, s in enumerate(top_summaries):
             source_id = s.get('source_id')
             if source_id:
                 references_string += f"Summary_{i+1} = {source_id}\n"
             else:
                 # Log a warning if a summary used in the report context is missing a source_id
                 log_to_file(f"Warning: Summary {i+1} used in report context is missing 'source_id'. Cannot add to references.")
    else:
        # This case handles when valid_summaries (and thus top_summaries) was empty
        references_string += "(No summaries met the score threshold to be included in the report)\n"
    # --- End Build References String ---

    # Save the initial, unrefined report to the archive
    initial_report_filename = "research_report_initial_raw.txt" # Name indicating it's the raw version
    initial_report_filepath = os.path.join(run_archive_dir, initial_report_filename) if run_archive_dir else initial_report_filename

    try:
        with open(initial_report_filepath, 'w', encoding='utf-8') as ef:
            ef.write(report_text)
            ef.write("\n\n") # Add separation
            ef.write(references_string) # Append references

        print(f"Saved initial (unrefined) report with references to archive: {initial_report_filepath}")
        log_to_file(f"Initial research report with references saved to archive: {initial_report_filepath}")
        # Return path, content, and the list of summaries used for context
        return initial_report_filepath, report_text, top_summaries
    except IOError as e:
        print(f"\nError: Could not save initial research report to {initial_report_filepath}: {e}")
        log_to_file(f"Report Saving Error: Failed to save initial report to {initial_report_filepath}: {e}")
        # Try CWD fallback ONLY if archive failed
        if run_archive_dir: # Only attempt fallback if archive was intended
            try:
                cwd_filename = initial_report_filename
                # Write content + references to fallback file as well
                with open(cwd_filename, 'w', encoding='utf-8') as ef_cwd:
                    ef_cwd.write(report_text)
                    ef_cwd.write("\n\n")
                    ef_cwd.write(references_string)
                print(f"Saved initial report with references to {cwd_filename} (CWD fallback)")
                log_to_file(f"Initial report with references saved to CWD fallback: {cwd_filename}")
                # Return path, content, and summaries used from fallback save
                return cwd_filename, report_text, top_summaries
            except IOError as e_cwd:
                print(f"\nError: Could not save initial report to CWD fallback path either: {e_cwd}")
                log_to_file(f"Report Saving Error: Failed to save initial report to CWD fallback: {e_cwd}")
                # Return None for all if fallback fails
                return None, None, None # Failed completely
        else: # No archive dir was set, fail saving
             # Return None for all if initial save fails without archive
             return None, None, None


def convert_markdown_to_pdf(markdown_content, pdf_path):
    """Convert markdown content to PDF using pdfkit/wkhtmltopdf."""
    print(f"\nAttempting to convert markdown to PDF: {pdf_path}")
    log_to_file(f"Attempting to convert markdown to PDF: {pdf_path}")
    try:
        # Convert markdown to HTML with extensions for better formatting
        html_content = markdown.markdown(markdown_content, extensions=[
            'extra',      # Includes tables, fenced code blocks, etc.
            'codehilite', # Syntax highlighting for code blocks
            'toc',        # Table of contents
            'nl2br'       # Convert newlines to <br> tags
        ])

        # Use BeautifulSoup to parse HTML and add spaces before strong tags if needed
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        for strong_tag in soup.find_all('strong'):
            # Check the previous sibling, which could be a text node or another tag
            previous_sibling = strong_tag.previous_sibling

            # If the previous sibling is a text node and ends without a space, add a space
            if previous_sibling and previous_sibling.name is None and previous_sibling.strip() and not previous_sibling.endswith((' ', '\n', '\r', '\t')):
                 # Create a new text node with a space and insert it before the strong tag
                 space_node = soup.new_string(" ")
                 strong_tag.insert_before(space_node)

        # Get the modified HTML back
        modified_html_content = str(soup)

        # Add improved styling for better PDF formatting
        styled_html = f'''
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 100%;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
            font-size: 12px;
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: #2c3e50;
            margin-top: 24px;
            margin-bottom: 12px;
            page-break-after: avoid;
        }}
        h1 {{
            border-bottom: 2px solid #2c3e50;
            padding-bottom: 10px;
            font-size: 20px;
        }}
        h2 {{ font-size: 18px; }}
        h3 {{ font-size: 16px; }}
        h4 {{ font-size: 14px; }}
        ul, ol {{
            margin-left: 20px;
            margin-bottom: 16px;
            padding-left: 0;
        }}
        li {{
            margin-bottom: 6px;
            line-height: 1.5;
            page-break-inside: avoid;
        }}
        ul li {{ list-style-type: disc; }}
        ul ul li {{ list-style-type: circle; }}
        ul ul ul li {{ list-style-type: square; }}
        p {{
            margin-bottom: 12px;
            line-height: 1.6;
        }}
        code {{
            background: #f8f9fa;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            color: #e83e8c;
            word-wrap: break-word;
        }}
        pre {{
            background: #f8f9fa;
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            margin-bottom: 16px;
        }}
        blockquote {{
            border-left: 4px solid #2c3e50;
            margin-left: 0;
            padding-left: 20px;
            margin-bottom: 16px;
            font-style: italic;
        }}
        strong {{
            font-weight: bold;
            color: #2c3e50;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 16px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: bold;
        }}
        .page-break {{ page-break-before: always; }}
    </style>
</head>
<body>
    {modified_html_content}
</body>
</html>
'''

        # PDF conversion options with improved formatting
        options = {
            'page-size': 'Letter',
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'encoding': 'UTF-8',
            'no-outline': None,
            'enable-local-file-access': None,
            'print-media-type': None,
            'disable-smart-shrinking': None,
            'zoom': '1.0'
        }

        try:
            # Try with installed wkhtmltopdf first
            pdfkit.from_string(styled_html, pdf_path, options=options)
            print("  - PDF conversion successful using default wkhtmltopdf path.")
            log_to_file("PDF Conversion: Successful using default wkhtmltopdf path.")
            return True
        except OSError as e_initial:
            # If wkhtmltopdf is not in PATH, try explicit Windows path ONLY if on Windows
            if platform.system() == "Windows":
                try:
                    print("  - wkhtmltopdf not found in PATH, attempting default Windows path...")
                    log_to_file("PDF Conversion: wkhtmltopdf not in PATH, trying C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe")
                    config = pdfkit.configuration(wkhtmltopdf='C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe')
                    pdfkit.from_string(styled_html, pdf_path, options=options, configuration=config)
                    print("  - Successfully used wkhtmltopdf from default Windows path.")
                    log_to_file("PDF Conversion: Success using default Windows path.")
                    return True # Success using fallback
                except OSError as e_fallback:
                    # Fallback also failed
                    print(f"  - Default Windows path for wkhtmltopdf also failed: {e_fallback}")
                    log_to_file(f"PDF Conversion Error: Default Windows path failed: {e_fallback}")
                    # Fall through to the general exception handling below
                    raise e_fallback # Re-raise the error from the fallback attempt
            else:
                # Not on Windows, so the initial OSError means it's not installed/in PATH
                print(f"  - wkhtmltopdf not found in PATH (OS: {platform.system()}).")
                log_to_file(f"PDF Conversion Error: wkhtmltopdf not found in PATH (OS: {platform.system()}). Initial error: {e_initial}")
                raise e_initial # Re-raise the original error

        # This line should technically not be reached if exceptions are raised correctly
        return True # Should be unreachable if exception occurs, but needed for structure
    except Exception as e:
        # Catch any exception during conversion (including re-raised OSErrors)
        print(f"PDF conversion failed: {e}")
        log_to_file(f"PDF Conversion Failed: {e}")
        print("Please ensure wkhtmltopdf is installed and accessible in your system's PATH.")
        print("Download from: https://wkhtmltopdf.org/downloads.html")
        return False


def refine_report_presentation(initial_report_content, top_summaries, reference_docs_content, args, topic, config, timestamp, topic_slug):
    """Uses AI to refine the presentation of the generated report."""
    print("\n--- Starting Report Refinement Phase ---")
    log_to_file("Starting report refinement phase.")

    if not initial_report_content:
        print("Error: No initial report content provided for refinement.")
        log_to_file("Refinement Error: Initial report content was empty.")
        return None # Cannot refine nothing

    # --- Build References String for Refinement Prompt ---
    references_section_for_prompt = "## References\n"
    ref_counter = 1

    # Add references from summaries (if any)
    if top_summaries:
         for s in top_summaries:
              source_id = s.get('source_id')
              if source_id:
                  references_section_for_prompt += f"{ref_counter}. {source_id}\n"
                  ref_counter += 1
              else:
                  log_to_file(f"Refinement Warning: Summary missing 'source_id'. Cannot add to references section.")

    # Add references from non-summarized documents (if any)
    if reference_docs_content and not args.reference_docs_summarize:
        for doc in reference_docs_content:
            doc_path = doc.get('path')
            if doc_path:
                # Use basename for cleaner reference
                references_section_for_prompt += f"{ref_counter}. {os.path.basename(doc_path)}\n"
                ref_counter += 1
            else:
                log_to_file(f"Refinement Warning: Reference document missing 'path'. Cannot add to references section.")

    # Handle case where no references were added at all
    if ref_counter == 1:
        references_section_for_prompt += "(No summaries met the score threshold and no non-summarized reference documents were used)\n"

    # --- End Build References String ---

    # --- Construct Refinement Prompt ---
    refinement_prompt = (
        f"You are an AI assistant specializing in document presentation and formatting.\n"
        f"**Task:** Refine the following research report text to significantly improve its presentation for a supervisor. Focus on enhancing readability, structure, scannability, and visual appeal using standard text formatting. The topic is '{topic}'.\n\n"
        f"**Refinement Instructions:**\n"
        f"1.  **Executive Summary:** Add a concise (2-4 sentence) 'Executive Summary' or 'Key Takeaways' section at the very beginning, summarizing the report's core findings.\n"
        f"2.  **Headings/Subheadings:** Ensure clear, descriptive headings (e.g., using markdown-style `#`, `##`, `###`) for sections like Introduction, different Body themes, Conclusion, and the References section.\n"
        f"3.  **Lists:** Convert dense paragraph descriptions of items, steps, pros/cons, or methods into bulleted (`*` or `-`) or numbered lists. Ensure each list item is on its own line, preceded by a blank line if it follows a paragraph.\n"
        f"4.  **Tables (Optional but Recommended):** If the text compares multiple methods, items, or data points (e.g., different acquisition methods with costs/limits), try to structure this into a simple markdown table for easy comparison. If a table is not feasible, use parallel bullet points under clear subheadings.\n"
        f"5.  **Paragraphs:** Break down long paragraphs into shorter, more focused ones, each addressing a single idea.\n"
        f"6.  **Bolding:** Use bold text (`**text**`) strategically and sparingly for key terms or crucial conclusions within sentences, not entire sentences.\n"
        f"7.  **Clarity & Flow:** Ensure smooth transitions and logical flow between sections.\n"
        f"8.  **Remove Inline Citations:** CRITICAL - Remove all inline parenthetical citations like `(Summary X)` or `(Summary X, Y)` from the body of the report.\n"
        f"9.  **Add References Section:** Append the following 'References' section exactly as provided at the VERY END of the report, after the conclusion.\n"
        f"10. **No New Content:** Do NOT add information not present in the original text. Focus *only* on restructuring, formatting, removing inline citations, and adding the provided References section.\n\n"
        f"**Original Report Text to Refine:**\n"
        f"--- START ORIGINAL REPORT ---\n"
        f"{initial_report_content}\n"
        f"--- END ORIGINAL REPORT ---\n\n"
        f"**References Section to Add at the End:**\n"
        f"--- START REFERENCES ---\n"
        f"{references_section_for_prompt}"
        f"--- END REFERENCES ---\n\n"
        f"**CRITICAL OUTPUT FORMAT:** Enclose the *entire* refined report (including the added References section) within a single pair of `<refinedReport>` tags. ONLY include the refined report text inside these tags. NO other text, remarks, or explanations outside the tags.\n"
        f"<refinedReport>" # Start the tag
    )
    refinement_prompt += "\n</refinedReport>" # End the tag

    # Save refinement prompt
    run_archive_dir = get_run_archive_dir()
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
    refined_report_text = None
    max_retries = 3
    retry_delay = 5

    for attempt in range(max_retries):
        refined_report_text = parse_ai_tool_response(cleaned_response, "refinedReport")

        # Check if parsing failed or returned nothing *or* returned the full response
        if not refined_report_text or refined_report_text == clean_thinking_tags(cleaned_response):
            if attempt < max_retries - 1:  # If we still have retries left
                print(f"\nWarning: Could not parse <refinedReport> tag (Attempt {attempt + 1}/{max_retries})")
                print(f"Waiting {retry_delay} seconds before retry...")
                log_to_file(f"Refinement Warning: Parse attempt {attempt + 1} failed, retrying in {retry_delay}s")
                time.sleep(retry_delay)

                # Try refining the report again
                raw_response, cleaned_response = call_ai_api(refinement_prompt, config, tool_name=f"ReportRefinement_Retry_{attempt + 1}", timeout=1200)

                if not cleaned_response:
                    print(f"\nError: Failed to get API response on refinement retry {attempt + 1}")
                    log_to_file(f"Refinement Error: API call failed on retry {attempt + 1}")
                    continue
            else:  # Last attempt failed
                print("\nWarning: Could not parse valid <refinedReport> content after all retry attempts. Skipping refinement.")
                log_to_file(f"Refinement Warning: Failed to parse <refinedReport> tag after {max_retries} attempts.\nLast Response:\n{clean_thinking_tags(cleaned_response)}")
                if run_archive_dir:
                    failed_ref_report_path = os.path.join(run_archive_dir, "report_REFINED_FAILED_PARSE.txt")
                    try:
                        with open(failed_ref_report_path, 'w', encoding='utf-8') as frf: frf.write(clean_thinking_tags(cleaned_response) or "Original cleaned response was empty.")
                    except IOError: pass
                return None  # Indicate refinement failed
        else:  # Successfully parsed content
            print(f"\nSuccessfully parsed refined report{' on retry ' + str(attempt) if attempt > 0 else ''}.")
            break

    # --- Save Refined Report to Designated Folder ---
    # Directory: <script_run_directory>/outputs/
    # Filename: <timestamp>_<topic_slug>_report.[md|pdf]
    try:
        # Define the main output directory name
        output_dir_name = "outputs"
        # Create the full path to the output directory in the CWD
        final_output_dir = os.path.join(os.getcwd(), output_dir_name)
        # Create the directory if it doesn't exist
        os.makedirs(final_output_dir, exist_ok=True)
        print(f"Ensured output directory exists: {final_output_dir}")
        log_to_file(f"Ensured output directory exists: {final_output_dir}")

        # Construct the base filename using timestamp and topic_slug
        base_filename = f"{timestamp}_{topic_slug}_report"
        # Create paths for both markdown and PDF versions
        markdown_filepath = os.path.join(final_output_dir, f"{base_filename}.md")
        pdf_filepath = os.path.join(final_output_dir, f"{base_filename}.pdf")

        # Save markdown version
        with open(markdown_filepath, 'w', encoding='utf-8') as ff:
            ff.write(refined_report_text)
        log_to_file(f"Saved refined report markdown to: {markdown_filepath}")

        # Convert to PDF
        try:
            pdf_success = convert_markdown_to_pdf(refined_report_text, pdf_filepath)
            if pdf_success:
                print(f"Successfully saved refined report as:\nMarkdown: {markdown_filepath}\nPDF: {pdf_filepath}")
                log_to_file(f"Refined report saved successfully as markdown and PDF:\n{markdown_filepath}\n{pdf_filepath}")
                return [markdown_filepath, pdf_filepath]  # Return both paths when successful
            else:
                 print(f"Warning: PDF conversion failed. Markdown report saved to: {markdown_filepath}")
                 log_to_file(f"Warning: PDF conversion failed. Markdown report saved to: {markdown_filepath}")
                 return markdown_filepath # Return markdown path if PDF fails

        except Exception as pdf_e:
            print(f"Warning: PDF conversion failed: {pdf_e}")
            log_to_file(f"PDF conversion failed: {pdf_e}")
            return markdown_filepath  # Return markdown path if PDF fails

    except IOError as e:
        print(f"\nError: Could not save refined report to output directory: {e}")
        log_to_file(f"Refinement Saving Error: Failed to save refined report to output directory: {e}")
        # Also save to archive as fallback if possible
        run_archive_dir = get_run_archive_dir()
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