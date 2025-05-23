import os
import PyPDF2 # Renamed from pypdf - assuming PyPDF2 is intended or needs update
import docx
import platform # For OS-specific checks

# Import log_to_file from utils
from ..utils import log_to_file

def load_document(doc_path):
    """Helper to load content from a single document path."""

    if not os.path.isfile(doc_path):
        print(f"  - Error: Reference document file not found or is not a file: {doc_path}")
        log_to_file(f"Error: Reference document not found/not a file: {doc_path}")
        return None

    content = None
    file_ext = os.path.splitext(doc_path)[1].lower()
    print(f"  - Processing reference document: {doc_path}")
    log_to_file(f"Processing reference document: {doc_path}")
    try:
        if file_ext == '.pdf':
            text_content = []
            try:
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
                log_to_file(f"Extracted text from PDF: {doc_path}")
            except PyPDF2.errors.PdfReadError as pdf_err:
                 print(f"  - Error reading PDF file {doc_path}: {pdf_err}")
                 log_to_file(f"Error reading PDF file {doc_path}: {pdf_err}")
                 return None

        elif file_ext == '.docx':
            try:
                doc = docx.Document(doc_path)
                text_content = [para.text for para in doc.paragraphs if para.text]
                content = "\n".join(text_content)
                print(f"    - Extracted text from DOCX.")
                log_to_file(f"Extracted text from DOCX: {doc_path}")
            except Exception as docx_e:
                 print(f"  - Error reading DOCX file {doc_path}: {docx_e}")
                 log_to_file(f"Error reading DOCX file {doc_path}: {docx_e}")
                 return None

        elif file_ext == '.txt':
            # Try common encodings
            encodings_to_try = ['utf-8', 'latin-1', 'windows-1252']
            for enc in encodings_to_try:
                try:
                    with open(doc_path, 'r', encoding=enc) as f:
                        content = f.read()
                    print(f"    - Read as plain text ({enc}).")
                    log_to_file(f"Read as plain text ({enc}): {doc_path}")
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
            return {"path": doc_path, "content": content.strip()}
        else:
            print(f"    - Warning: No text content extracted or file is empty.")
            log_to_file(f"Warning: Reference document {doc_path} empty or no text extracted.")
            return None

    except Exception as e:
        print(f"  - Error processing reference document {doc_path}: {e}")
        log_to_file(f"Error processing reference document {doc_path}: {e} (Type: {type(e).__name__})")
        return None

def load_reference_documents(args):
    """Loads reference documents from specified paths or a folder."""
    reference_docs_content = []
    loaded_ref_paths = set() # Keep track of loaded paths to avoid duplicates

    # Load from --reference-docs
    if args.reference_docs:
        print("\nLoading specified reference documents...")
        log_to_file(f"Loading specified reference documents from: {args.reference_docs}")
        ref_doc_paths = [p.strip() for p in args.reference_docs.split(',') if p.strip()]
        for doc_path in ref_doc_paths:
            # Check if already loaded before attempting to load
            if doc_path in loaded_ref_paths:
                print(f"  - Skipping duplicate document path: {doc_path}")
                log_to_file(f"Skipping duplicate reference doc path: {doc_path}")
                continue

            doc_content = load_document(doc_path)
            if doc_content:
                reference_docs_content.append(doc_content)
                loaded_ref_paths.add(doc_path) # Mark as loaded

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
                # Check if it's a file and not already loaded before processing
                if os.path.isfile(doc_path) and doc_path not in loaded_ref_paths:
                    doc_content = load_document(doc_path) # Use helper function
                    if doc_content:
                        reference_docs_content.append(doc_content)
                        loaded_ref_paths.add(doc_path) # Mark as loaded
                elif os.path.isfile(doc_path) and doc_path in loaded_ref_paths:
                     print(f"  - Skipping already loaded document from folder: {doc_path}")
                     log_to_file(f"Skipping duplicate reference doc from folder: {doc_path}")


            log_to_file(f"Finished processing reference documents folder. Total loaded: {len(reference_docs_content)}")

    if not reference_docs_content and (args.reference_docs or args.reference_docs_folder):
        print("Warning: No valid reference documents were loaded despite flags being set.")
        log_to_file("Warning: Reference doc flags set, but no content loaded.")

    return reference_docs_content
