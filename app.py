from flask import Flask, render_template, request, jsonify, send_from_directory
import subprocess
import os
import threading
import queue
import json
import yaml
from dotenv import load_dotenv, set_key
from flask import Response # Import Response for SSE

# Load environment variables from .env file at the start
load_dotenv()

# Global queue to hold output from the subprocess
output_queue = queue.Queue()

# Global variable to store the process thread
process_thread = None

# Global variable to store the subprocess object
current_process = None

# Global variable to store the final report files
final_report_files = []

# Global variable to indicate if the process is running
process_running = False

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads' # Directory to save uploaded files

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Routes ---
@app.route('/')
def index():
    """Render the main report generation page."""
    llm_settings = load_llm_settings()
    available_models = list(llm_settings.keys()) if llm_settings else []
    return render_template('index.html', llm_models=available_models)
@app.route('/settings')
def settings():
    """Render the settings page."""
    api_keys = load_api_keys()
    llm_settings = load_llm_settings()
    return render_template('settings.html', api_keys=api_keys, llm_settings=llm_settings)
@app.route('/get_llm_models', methods=['GET'])
def get_llm_models():
    """Return the list of available LLM models."""
    llm_settings = load_llm_settings()
    available_models = list(llm_settings.keys()) if llm_settings else []
    return jsonify({"llm_models": available_models})
@app.route('/generate_report', methods=['POST'])
def generate_report():
    """Handle report generation requests and start the process."""
    global process_thread, process_running, final_report_files

    if process_running:
        return jsonify({"status": "error", "message": "A report generation process is already running."}), 409 # Conflict

    data = request.form
    uploaded_files = request.files

    # Construct the base command
    command = ['python', 'report_builder.py']

    # Map form fields to command-line arguments
    arg_map = {
        'topic': '--topic',
        'keywords': '--keywords',
        'guidance': '--guidance',
        'api': '--api',
        'llm-model': '--llm-model',
        'from_date': '--from_date',
        'to_date': '--to_date',
        'max-web-results': '--max-web-results',
        'max-reddit-results': '--max-reddit-results',
        'max-reddit-comments': '--max-reddit-comments',
        'per-keyword-results': '--per-keyword-results',
        'score-threshold': '--score-threshold',
    }

    for field, arg in arg_map.items():
        value = data.get(field)
        if value:
            command.extend([arg, value])

    # Handle boolean flags
    boolean_flags = {
        'combine-keywords': '--combine-keywords',
        'no-search': '--no-search',
        'reference-docs-summarize': '--reference-docs-summarize',
        'skip_refinement': '--skip_refinement',
        'no-reddit': '--no-reddit',
    }

    for field, arg in boolean_flags.items():
        if data.get(field) == 'on': # Checkbox value is 'on' when checked
            command.append(arg)
    
    # Always add --report flag since this is a report generation tool
    command.append('--report')

    # Handle uploaded files and folders
    uploaded_ref_docs_paths = []
    if 'reference-docs' in uploaded_files:
        for file in uploaded_files.getlist('reference-docs'):
            if file.filename:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(filepath)
                uploaded_ref_docs_paths.append(filepath)
    if uploaded_ref_docs_paths:
        command.extend(['--reference-docs', ','.join(uploaded_ref_docs_paths)])

    if 'direct-articles' in uploaded_files:
        file = uploaded_files['direct-articles']
        if file.filename:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            command.extend(['--direct-articles', filepath])



    print(f"Executing command: {' '.join(command)}")

    # Clear previous output and results
    while not output_queue.empty():
        try:
            output_queue.get_nowait()
        except queue.Empty:
            pass
    final_report_files = []

    # Execute the command in a separate thread for streaming
    process_running = True
    process_thread = threading.Thread(target=run_report_builder, args=(command,))
    process_thread.start()

    return jsonify({"status": "processing", "message": "Report generation started. Please wait for progress."})
@app.route('/stream_output')
def stream_output():
    """Streams output from the report generation subprocess using Server-Sent Events."""
    def generate():
        while process_running or not output_queue.empty():
            try:
                # Get output line from the queue with a timeout
                line = output_queue.get(timeout=1)
                if line is None: # Sentinel value to indicate end of process
                    break
                # Format as SSE data
                yield f"data: {json.dumps({'type': 'output', 'content': line})}\n\n"
            except queue.Empty:
                # No output in the last second, keep the connection alive
                yield "data: {}\n\n" # Send a keep-alive message (empty JSON)
            except Exception as e:
                 print(f"Error streaming output: {e}")
                 yield f"data: {json.dumps({'type': 'error', 'content': f'Streaming error: {e}'})}\n\n"
                 break

        # After the process finishes, send the final report file paths
        yield f"data: {json.dumps({'type': 'complete', 'report_files': final_report_files})}\n\n"


    # Set up the response for Server-Sent Events
    response = Response(generate(), mimetype='text/event-stream')
    response.headers['X-Accel-Buffering'] = 'no' # Disable buffering for Nginx
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    return response

@app.route('/reports/<filename>')
def serve_report(filename):
    """Serve generated report files from the outputs directory."""
    try:
        return send_from_directory('outputs', filename)
    except FileNotFoundError:
        return "Report file not found.", 404
    
@app.route('/save_settings', methods=['POST'])
def save_settings():
    """Handle saving API keys and LLM settings."""
    data = request.json
    api_keys_data = data.get('apiKeys', {})
    llm_settings_data = data.get('llmSettings', {})

    api_success, api_message = save_api_keys(api_keys_data)
    llm_success, llm_message = save_llm_settings(llm_settings_data)

    if api_success and llm_success:
        return jsonify({"status": "success", "message": "Settings saved successfully."})
    else:
        # Combine messages for partial failures
        error_message = ""
        if not api_success:
            error_message += f"API Keys Save Failed: {api_message} "
        if not llm_success:
            error_message += f"LLM Settings Save Failed: {llm_message}"
        return jsonify({"status": "error", "message": error_message.strip()}), 500
# --- Helper Functions ---

def load_api_keys():
    """Loads API keys from environment variables (loaded from .env)."""
    # load_dotenv() is called at the app startup, so env vars should be available
    return {
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", ""),
        "GOOGLE_CSE_ID": os.getenv("GOOGLE_CSE_ID", ""),
        "BRAVE_API_KEY": os.getenv("BRAVE_API_KEY", ""),
        "REDDIT_CLIENT_ID": os.getenv("REDDIT_CLIENT_ID", ""),
        "REDDIT_CLIENT_SECRET": os.getenv("REDDIT_CLIENT_SECRET", ""),
        "REDDIT_USER_AGENT": os.getenv("REDDIT_USER_AGENT", ""),
    }

def load_llm_settings():
    """Loads LLM model configurations from settings/llm_settings/ai_models.yml."""
    llm_config_path = os.path.join('settings', 'llm_settings', 'ai_models.yml')
    if not os.path.exists(llm_config_path):
        print(f"Warning: LLM configuration file not found at {llm_config_path}")
        return {}
    try:
        with open(llm_config_path, 'r', encoding='utf-8') as f:
            settings = yaml.safe_load(f)
            return settings if isinstance(settings, dict) else {}
    except yaml.YAMLError as e:
        print(f"Error parsing LLM configuration file {llm_config_path}: {e}")
        return {}
    except Exception as e:
        print(f"An unexpected error occurred loading LLM settings: {e}")
        return {}
def save_api_keys(api_keys_data):
    """Saves API keys to the .env file."""
    dotenv_path = '.env'
    # Ensure the .env file exists
    if not os.path.exists(dotenv_path):
        with open(dotenv_path, 'w') as f:
            pass # Create empty file

    try:
        for key, value in api_keys_data.items():
            # set_key handles adding/updating keys
            set_key(dotenv_path, key, value)
        print("API keys saved to .env")
        return True, "API keys saved successfully."
    except Exception as e:
        print(f"Error saving API keys to .env: {e}")
        return False, f"Error saving API keys: {e}"

def save_llm_settings(llm_settings_data):
    """Saves LLM model configurations to settings/llm_settings/ai_models.yml."""
    llm_config_dir = os.path.join('settings', 'llm_settings')
    llm_config_path = os.path.join(llm_config_dir, 'ai_models.yml')

    # Ensure the directory exists
    os.makedirs(llm_config_dir, exist_ok=True)

    try:
        with open(llm_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(llm_settings_data, f, default_flow_style=False, sort_keys=False)
        print(f"LLM settings saved to {llm_config_path}")
        return True, "LLM settings saved successfully."
    except Exception as e:
        print(f"Error saving LLM settings to {llm_config_path}: {e}")
        return False, f"Error saving LLM settings: {e}"

def run_report_builder(command):
    """Runs the report_builder.py script as a subprocess and streams output to a queue."""
    global process_running, final_report_files, current_process
    process = None
    try:
        process = subprocess.Popen(command, cwd='.', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        current_process = process # Store the process object globally

        # Read output line by line and put it in the queue
        for line in iter(process.stdout.readline, ''):
            output_queue.put(line)

        # Wait for the process to finish
        process.wait()

        if process.returncode == 0:
            output_queue.put("--- Report Generation Complete ---")
            # Find generated report files
            final_report_files = find_report_files()
            output_queue.put(f"Generated files: {', '.join(final_report_files)}")
        else:
            output_queue.put(f"--- Report Generation Failed (Exit Code {process.returncode}) ---")
            # Optionally put stderr content if not already streamed
            # output_queue.put(process.stderr.read()) # If stderr was not merged

    except FileNotFoundError:
        output_queue.put("Error: python or report_builder.py not found. Ensure Python is in your PATH and report_builder.py exists.")
    except Exception as e:
        output_queue.put(f"An unexpected error occurred during subprocess execution: {e}")
        import traceback
        output_queue.put(traceback.format_exc())
    finally:
        # Signal the end of the process
        output_queue.put(None)
        process_running = False
        current_process = None # Clear the process object


def find_report_files():
    """Finds the most recently generated report files in the outputs/ directory."""
    output_dir = 'outputs'
    if not os.path.exists(output_dir):
        return []

    # List all files in the outputs directory
    files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, f))]

    # Filter for .md and .pdf files
    report_files = [f for f in files if f.endswith('.md') or f.endswith('.pdf')]

    # Sort files by modification time (most recent first)
    report_files.sort(key=os.path.getmtime, reverse=True)
    # This is a simplification and might need refinement.
    return report_files[:2]


# TODO: Implement streaming output using Server-Sent Events (SSE) or WebSockets

@app.route('/stop_report', methods=['POST'])
def stop_report():
    """Stops the currently running report generation process."""
    global current_process, process_running
    if current_process and process_running:
        try:
            current_process.terminate() # or .kill() for a more forceful stop
            # Wait a short time for termination
            current_process.wait(timeout=5)
            process_running = False
            current_process = None
            return jsonify({"status": "success", "message": "Report generation process stopped."})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error stopping process: {e}"}), 500
    else:
        return jsonify({"status": "info", "message": "No report generation process is currently running."})

if __name__ == '__main__':
    # In a production environment, use a production-ready WSGI server like Gunicorn or uWSGI
    # For development, debug=True is fine.
    app.run(debug=True)