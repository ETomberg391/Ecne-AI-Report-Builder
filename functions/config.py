import os
import yaml
from dotenv import load_dotenv
import json # Needed for logging config

# Import log_to_file from utils
from .utils import log_to_file

def load_config(script_dir):
    """Loads configuration from .env file and ai_models.yml."""
    # Try loading .env from script directory first, then current working directory
    dotenv_path_script = os.path.join(script_dir, '.env')
    dotenv_path_cwd = os.path.join(os.getcwd(), '.env')

    if os.path.exists(dotenv_path_script):
        load_dotenv(dotenv_path=dotenv_path_script)
        print(f"Loaded .env from script directory: {dotenv_path_script}")
        log_to_file(f"Loaded .env from script directory: {dotenv_path_script}")
    elif os.path.exists(dotenv_path_cwd):
        load_dotenv(dotenv_path=dotenv_path_cwd)
        print(f"Loaded .env from current working directory: {dotenv_path_cwd}")
        log_to_file(f"Loaded .env from current working directory: {dotenv_path_cwd}")
    else:
        print("Warning: .env file not found in script directory or current working directory.")
        log_to_file("Warning: .env file not found.")


    config = {
        "google_api_key": os.getenv("GOOGLE_API_KEY"),
        "google_cse_id": os.getenv("GOOGLE_CSE_ID"),
        "brave_api_key": os.getenv("BRAVE_API_KEY"),
    }

    # --- Load Model Configurations ---
    # LLM_DIR is relative to the script_dir (project root in this case)
    llm_dir = os.path.abspath(os.path.join(script_dir, "settings/llm_settings"))
    models_config_path = os.path.join(llm_dir, 'ai_models.yml')
    models_config = {} # Initialize as empty dict
    try:
        with open(models_config_path, 'r', encoding='utf-8') as f:
            models_config = yaml.safe_load(f)
        if not models_config or not isinstance(models_config, dict):
             raise ValueError("ai_models.yml is empty or not a valid dictionary.")
        print(f"Loaded model configurations from {models_config_path}")
        log_to_file(f"Loaded model configurations from {models_config_path}")
    except FileNotFoundError:
        print(f"Error: Model configuration file not found at {models_config_path}")
        log_to_file(f"Error: Model configuration file not found at {models_config_path}")
        # Allow script to continue if models are not needed, but warn
        print("Warning: Proceeding without model configurations. LLM features will fail.")
        log_to_file("Warning: Proceeding without model configurations. LLM features will fail.")
    except (yaml.YAMLError, ValueError) as e:
        print(f"Error parsing model configuration file {models_config_path}: {e}")
        log_to_file(f"Error parsing model configuration file {models_config_path}: {e}")
        exit(1) # Exit if config is malformed

    # --- Basic Validation ---
    google_ok = config.get("google_api_key") and config.get("google_cse_id")
    brave_ok = config.get("brave_api_key")
    if not google_ok and not brave_ok:
         print("Warning: Neither Google (API Key + CSE ID) nor Brave API Key are set. Web search may fail.")
         log_to_file("Warning: Neither Google nor Brave API keys set. Web search may fail.")

    print("Configuration loading process complete.")
    log_to_file("Configuration loading process complete.")
    return config, models_config

def load_character_profile(profile_path):
    """Loads a character profile from a YAML file."""
    print(f"\nLoading character profile from: {profile_path}")
    log_to_file(f"Attempting to load character profile from {profile_path}")
    profile = None
    if not os.path.isfile(profile_path):
        print(f"Error: Character profile file not found or is not a file: {profile_path}")
        log_to_file(f"Error: Character profile not found/not a file: {profile_path}")
        return None

    try:
        with open(profile_path, 'r', encoding='utf-8') as f:
            profile = yaml.safe_load(f)
        if not profile or not isinstance(profile, dict):
            raise ValueError("Profile file is empty or not a valid dictionary.")
        print(f"Successfully loaded profile from {profile_path}")
        log_to_file(f"Successfully loaded profile from {profile_path}")
        # Optionally log profile content, but be mindful of sensitive info
        # log_to_file(f"Profile content: {json.dumps(profile, indent=2)}")
        return profile
    except FileNotFoundError:
        # This case is handled by the initial os.path.isfile check, but included for completeness
        print(f"Error: Character profile file not found: {profile_path}")
        log_to_file(f"Error: Character profile file not found: {profile_path}")
        return None
    except yaml.YAMLError as e:
        print(f"Error parsing character profile file {profile_path}: {e}")
        log_to_file(f"Error parsing character profile file {profile_path}: {e}")
        return None
    except ValueError as e:
        print(f"Error loading character profile {profile_path}: {e}")
        log_to_file(f"Error loading character profile {profile_path}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred loading profile {profile_path}: {e}")
        log_to_file(f"Unexpected error loading profile {profile_path}: {e}")
        return None