# novel_mvp/config_gemini.py (Save as config.py in your gemini branch/folder)
import os
import sys

# Import necessary classes
# Ensure 'langchain-google-genai' is installed: pip install langchain-google-genai
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    # Required for safety settings definitions if you uncomment them
    # from google.generativeai.types import HarmCategory, HarmBlockThreshold
    google_genai_installed = True
except ImportError:
    print("ERROR: 'langchain-google-genai' not installed. Cannot use Gemini.", file=sys.stderr)
    print("Please run: pip install langchain-google-genai", file=sys.stderr)
    ChatGoogleGenerativeAI = None
    google_genai_installed = False

# --- Configuration ---

# Gemini Configuration
# Note: Check Google AI Studio for latest available model names
GEMINI_MODEL = "gemini-2.5-flash" # Or "gemini-1.5-pro-latest", etc.

# --- !!! WARNING: Hardcoding API keys is insecure for shared code !!! ---
# --- !!! Only use this method for temporary local testing.      !!! ---
# --- !!! Replace placeholder with your actual key for testing.   !!! ---
GEMINI_API_KEY = "" # <<< PASTE YOUR ACTUAL GOOGLE API KEY HERE

# --- LLM Initialization ---
llm_standard = None
llm_json_strict = None

print(f"Attempting to initialize Gemini LLM ({GEMINI_MODEL})...")

if not google_genai_installed:
    print("ERROR: Cannot initialize Gemini models because 'langchain-google-genai' is not installed.", file=sys.stderr)
    # Keep llm variables as None
else:
    try:
        # --- Check if API Key Variable is Set ---
        if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_API_KEY_HERE":
            raise ValueError("GEMINI_API_KEY variable is not set in config.py. Please paste your key.")
        # --- End Check ---

        print(f"Initializing Google Gemini model: {GEMINI_MODEL}")
        # Standard model for creative generation
        llm_standard = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=GEMINI_API_KEY, # Pass the variable here
            temperature=0.7,
            # Optional: Configure safety settings if needed
            # safety_settings={ ... }
        )

        # Model specifically configured for JSON output
        llm_json_strict = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=GEMINI_API_KEY, # Pass the variable here
            temperature=0.1, # Low temp for consistency
            # Configure for JSON Mode
            generation_config={"response_mime_type": "application/json"}
            # Optional: Configure safety settings if needed
            # safety_settings={ ... }
        )
        print("Successfully initialized Google Gemini models (strict JSON mode enabled).")

    except ValueError as ve: # Catch missing API key error
         print(f"ERROR: {ve}", file=sys.stderr)
         llm_standard = None
         llm_json_strict = None
    except Exception as e:
        # Catch other potential errors during Gemini initialization
        print(f"ERROR: Failed to initialize Google Gemini models: {e}", file=sys.stderr)
        llm_standard = None
        llm_json_strict = None

# --- Optional LangSmith Tracing ---
# os.environ["LANGCHAIN_TRACING_V2"] = "true"
# os.environ["LANGCHAIN_API_KEY"] = "YOUR_LANGSMITH_API_KEY" # Replace if using

# --- Final Check ---
if llm_standard is None or llm_json_strict is None:
    print("\nCRITICAL: LLM initialization failed. Exiting.", file=sys.stderr)
    # sys.exit(1) # Optionally exit
