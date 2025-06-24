# novel_mvp/main.py (for Gemini branch)
import sys
import os
import json
from typing import Optional, Dict, Any, List # Import List

# Import the compiled graph app and state definition
# Ensure graph.py provides the compiled 'app'
from graph import app
# Import specific types needed from the latest data_models artifact
# Assumes data_models.py defines these (like data_models_phase2_v6/v7)
from data_models import GraphState, AllCharacterStates, ChapterOutlineItem
# Import config stuff needed - assumes config.py is the Gemini version
from config import (
    GEMINI_MODEL, # Use Gemini model name
    llm_standard,
    llm_json_strict
)
# Import file saving directory and helper from agents artifact
# Assumes agents.py is in the same directory
from agents import OUTPUT_DIR, _ensure_output_dir

# --- Helper Functions ---
def load_previous_chapter_state(chapter_index: int) -> Optional[AllCharacterStates]:
    """
    Loads the final character state from the previous chapter's JSON file.
    Returns None if it's the first chapter or if the file doesn't exist/is invalid.
    """
    # No previous state for the first chapter (index 0)
    if chapter_index <= 0:
        print("DEBUG: No previous chapter state to load for Chapter 1.")
        return None

    # Construct the expected filename for the previous chapter's state
    # e.g., chapter_1_state.json for chapter_index 1 (when starting Chapter 2)
    state_filename = os.path.join(OUTPUT_DIR, f"chapter_{chapter_index}_state.json")

    if os.path.exists(state_filename):
        try:
            with open(state_filename, 'r', encoding='utf-8') as f:
                print(f"Loading character state from {state_filename}")
                loaded_data = json.load(f)
                # Basic validation: Check if it's a dictionary
                if isinstance(loaded_data, dict):
                    # TODO: Add more robust validation if using Pydantic models for state
                    return loaded_data # Should conform to AllCharacterStates structure
                else:
                    print(f"Warning: Invalid format in state file {state_filename}. Expected a dictionary.", file=sys.stderr)
                    return None
        except (IOError, json.JSONDecodeError) as e:
            print(f"Warning: Failed to load or parse previous chapter state from {state_filename}. {e}", file=sys.stderr)
            return None
    else:
        # It might be okay not to find the file if generation was interrupted,
        # but we should warn the user.
        print(f"Warning: Previous chapter state file not found: {state_filename}", file=sys.stderr)
        return None

# --- Main Execution Logic ---
if __name__ == "__main__":
    print(f"\nStarting Novel MVP (Gemini Version)...") # Modified print
    _ensure_output_dir() # Make sure output dir exists before any saving attempts

    # --- Check Prerequisites ---
    # 1. Check LLM Initialization (using the imported instances)
    if llm_standard is None or llm_json_strict is None:
         print("\nERROR: LLM instances failed to initialize in config.py.", file=sys.stderr)
         # Updated message for Gemini
         print("Please check Gemini configuration and API key in config.py.", file=sys.stderr)
         sys.exit(1) # Exit if LLMs are not ready
    else:
        # Updated message for Gemini
        print(f"Using Google Gemini Model: '{GEMINI_MODEL}'.")

    # 2. Check Graph Compilation
    if app is None:
        print("\nERROR: Graph application failed to compile in graph.py.", file=sys.stderr)
        print("Check graph.py for compilation errors.", file=sys.stderr)
        sys.exit(1) # Exit if graph is not ready

    # --- Define Recursion Limit Config ---
    # Set the desired recursion limit here
    runtime_config = {"recursion_limit": 100} # Increased limit
    print(f"Using runtime recursion limit: {runtime_config['recursion_limit']}")

    # --- Phase 1: Generate Bible & Outline (Run Once) ---
    print("\n--- Running Phase 1: Bible & Outline Generation ---")
    phase1_initial_state = {} # Start empty for user input node
    phase1_final_state: Optional[GraphState] = None # Use Optional hint
    try:
        print("Invoking graph for Phase 1 setup...")
        # Pass the runtime config here as well
        phase1_result_state = app.invoke(phase1_initial_state, config=runtime_config)

        # Check for errors during this initial run
        if phase1_result_state.get("error"):
             print("\nERROR during Phase 1 / Initial Setup execution:", phase1_result_state.get("error"), file=sys.stderr)
             debug_output = phase1_result_state.get("debug_llm_output")
             if debug_output: print(f"Debug LLM Output:\n{debug_output}", file=sys.stderr)
             sys.exit(1)

        # Extract necessary components generated during Phase 1 for subsequent Phase 2 runs
        world_details = phase1_result_state.get("world_details")
        character_profile = phase1_result_state.get("character_profile") # Single profile
        # Outline is List[ChapterOutlineItem] based on latest data_models
        overall_plot_outline: Optional[List[ChapterOutlineItem]] = phase1_result_state.get("overall_plot_outline")
        # Get the initial character state set after profile generation
        initial_character_states = phase1_result_state.get("character_states")

        # Ensure all required outputs were generated and outline is a non-empty list
        if not world_details or not character_profile or not initial_character_states \
           or not isinstance(overall_plot_outline, list) or not overall_plot_outline:
            print("\nERROR: Phase 1 did not generate required outputs (World, Character, Outline, Initial State).", file=sys.stderr)
            print("Final state from initial run:", phase1_result_state, file=sys.stderr)
            sys.exit(1)

        print("--- Phase 1 Setup Completed Successfully ---")
        # Keep necessary outputs for Phase 2 loop
        phase1_user_inputs = {
             "user_world_concept": phase1_result_state.get("user_world_concept"),
             "user_character_concept": phase1_result_state.get("user_character_concept"),
             "user_story_premise": phase1_result_state.get("user_story_premise"),
        }

    except Exception as e:
        # Catch potential GraphRecursionError if limit is still too low or other errors
        print(f"\n--- CRITICAL ERROR DURING PHASE 1 / INITIAL INVOCATION ---", file=sys.stderr)
        print(f"{type(e).__name__}: {e}", file=sys.stderr); sys.exit(1)

    # --- Phase 2: Chapter-by-Chapter Generation ---
    num_chapters = len(overall_plot_outline)
    print(f"\n--- Starting Phase 2: Generating {num_chapters} Chapters ---")

    # Start generation from Chapter 0
    current_chapter_idx = 0
    # Use the initial state derived right after character profile generation as starting point
    last_chapter_states = initial_character_states

    # Loop through chapters until all are generated or user stops
    while current_chapter_idx < num_chapters:
        current_chapter_number = current_chapter_idx + 1
        print(f"\n--- Preparing Chapter {current_chapter_number}/{num_chapters} ---")

        # Load state from the *end* of the previous chapter if it exists (for index > 0)
        if current_chapter_idx > 0:
            # Pass the index of the *previous* chapter to load its state
            loaded_states = load_previous_chapter_state(current_chapter_idx)
            if loaded_states is not None:
                last_chapter_states = loaded_states # Use state saved from previous chapter
                print("Successfully loaded state from previous chapter.")
            else:
                print(f"Warning: Could not load state from Chapter {current_chapter_idx}. Using state from end of previous chapter.", file=sys.stderr)
                # Fallback to 'last_chapter_states' which holds state from end of chapter N-1

        # Construct the specific initial state required for invoking the graph for *this* chapter
        # Ensure all keys defined in GraphState TypedDict are present
        chapter_initial_state: GraphState = {
            # Static elements (needed by agents within the graph)
            "world_details": world_details,
            "character_profile": character_profile,
            "overall_plot_outline": overall_plot_outline,

            # Dynamic/Control elements for this chapter run
            "current_chapter_index": current_chapter_idx,
            "character_states": last_chapter_states, # Starting state for the chapter

            # Fields to be populated by the graph run for this chapter (reset)
            "current_chapter_summary": None, # Will be set by prepareChapter node
            "chapter_scene_outline": None,   # Will be set by chapterPlanner node
            "current_scene_index": 0,        # Start at scene 0
            "current_scene_goal": None,
            "current_scene_prose": None,
            "completed_chapter_prose": [],   # Start with empty list for this chapter
            "consistency_notes": None,
            "error": None,                   # Clear errors for new chapter run
            "debug_llm_output": None,

            # Phase 1 inputs might not be strictly needed but included for completeness
            **phase1_user_inputs
        }

        # --- Invoke Graph for Current Chapter ---
        try:
            print(f"Invoking graph for Chapter {current_chapter_number}...")
            # Pass the runtime config here as well
            final_chapter_state: GraphState = app.invoke(chapter_initial_state, config=runtime_config)

            # Check if the graph run for this chapter resulted in an error
            if final_chapter_state.get("error"):
                print(f"\nERROR during Chapter {current_chapter_number} generation:", final_chapter_state.get("error"), file=sys.stderr)
                print("Stopping generation due to error in chapter.")
                break # Exit the while loop

            else:
                print(f"--- Chapter {current_chapter_number} Generation Completed and Saved ---")
                # Update 'last_chapter_states' with the final state from *this* chapter,
                # ready for the *next* iteration's loading step (or if loading fails).
                last_chapter_states = final_chapter_state.get("character_states")

        except Exception as exec_error:
             # Catch potential GraphRecursionError if limit is still too low or other errors
            print(f"\n--- CRITICAL ERROR DURING Chapter {current_chapter_number} INVOCATION ---", file=sys.stderr)
            print(f"{type(exec_error).__name__}: {exec_error}", file=sys.stderr)
            print("Stopping generation due to critical error.")
            break # Exit the while loop

        # --- User Interaction Point ---
        current_chapter_idx += 1 # Move to the next chapter index
        if current_chapter_idx < num_chapters:
            # Ask user if they want to proceed
            try:
                user_continue = input(f"Generate Chapter {current_chapter_idx + 1}? (y/n): ").lower().strip()
                if user_continue != 'y':
                    print("Stopping generation as requested.")
                    break # Exit the while loop
            except EOFError: # Handle case where input stream is closed
                 print("Input stream closed, stopping generation.", file=sys.stderr)
                 break
        else:
            # All chapters generated
            print("\nAll chapters outlined in Phase 1 have been processed!")

    # --- End of Application ---
    print("\nApplication finished.")

