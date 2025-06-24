import streamlit as st
import os
import json
import time
from typing import Optional, Dict, Any, List

# --- Backend Imports ---
# Ensure these imports work from your project structure
try:
    from graph import app
    from data_models import GraphState
    from agents import OUTPUT_DIR, _ensure_output_dir
    from config import llm_standard, llm_json_strict, GEMINI_API_KEY
    config_valid = True
    # Basic check to see if the placeholder key is still there
    if not GEMINI_API_KEY or "YOUR_API_KEY" in GEMINI_API_KEY or "AIza" not in GEMINI_API_KEY:
        config_valid = False
except (ImportError, NameError) as e:
    # This will catch errors if the files don't exist or have issues.
    st.error(f"Failed to import backend modules: {e}. Please ensure all required .py files (graph, data_models, agents, config) are in the same directory.")
    app = None
    config_valid = False


# --- UI Helper Functions ---
def get_generated_chapters() -> List[int]:
    """Scans the output directory for generated chapter prose files."""
    if not os.path.exists(OUTPUT_DIR):
        return []
    chapter_numbers = []
    for filename in os.listdir(OUTPUT_DIR):
        if filename.startswith("chapter_") and filename.endswith("_scenes.json"):
            try:
                # Extract chapter number from "chapter_1_scenes.json"
                num_str = filename.split('_')[1]
                chapter_numbers.append(int(num_str))
            except (ValueError, IndexError):
                continue # Skip malformed filenames
    return sorted(chapter_numbers)

# --- Streamlit App UI ---
st.set_page_config(page_title="Novel MVP Engine", layout="wide")
st.title("📖 Novel MVP Engine")
st.markdown("A tool to generate a complete story from concept to prose using a Gemini-powered agentic workflow.")

# --- Pre-flight Check for Backend ---
if not app or not config_valid:
    st.error("🔴 Critical Error: The backend application could not be loaded. Please check your console for import errors and ensure your `config.py` is correctly set up with a valid Gemini API key.")
    st.stop()


# --- Initialize Session State ---
if 'phase1_done' not in st.session_state:
    st.session_state['phase1_done'] = False
if 'phase1_data' not in st.session_state:
    st.session_state['phase1_data'] = None
if 'last_generated_chapter' not in st.session_state:
    # Check the output folder to resume state if Streamlit restarts
    existing_chapters = get_generated_chapters()
    st.session_state['last_generated_chapter'] = max(existing_chapters) if existing_chapters else 0


# --- Tabbed Interface ---
tab1, tab2 = st.tabs(["**✍️ Generate Story**", "**📚 Read Novel**"])

# ==================================================================================
# --- TAB 1: GENERATE STORY ---
# ==================================================================================
with tab1:
    st.header("1. Define Your Story's Core Concepts")

    col1, col2, col3 = st.columns(3)
    with col1:
        world_concept = st.text_area("🌍 **World Concept**", height=200, placeholder="e.g., A cyberpunk city where memories can be bought and sold...", help="Describe the genre, rules, and overall feel of your world.")
    with col2:
        char_concept = st.text_area("👤 **Character Concept**", height=200, placeholder="e.g., An amnesiac private detective who specializes in recovering lost memories...", help="Describe the main character's core traits, profession, and role in the story.")
    with col3:
        story_premise = st.text_area("🗺️ **Story Premise**", height=200, placeholder="e.g., The detective takes on a case to find stolen memories...", help="What is the central conflict or goal of the story?")

    st.divider()

    # --- Step 1: Generate Story Foundation & Chapter 1 ---
    st.header("2. Generate Story Foundation & First Chapter")
    if not st.session_state['phase1_done']:
        if st.button("🚀 Generate Bible, Outline, and Chapter 1", type="primary", use_container_width=True):
            if not all([world_concept, char_concept, story_premise]):
                st.warning("Please fill out all three concept fields before generating.")
            else:
                with st.status("Building Story Foundation and Writing Chapter 1...", expanded=True) as status:
                    try:
                        _ensure_output_dir()
                        initial_state = {
                            "user_world_concept": world_concept,
                            "user_character_concept": char_concept,
                            "user_story_premise": story_premise,
                        }
                        # Standard invoke returns the final state dictionary directly
                        final_state = app.invoke(initial_state, config={"recursion_limit": 150})

                        if final_state.get("error"):
                            status.update(label=f"Generation Failed: {final_state.get('error')}", state="error")
                            st.json(final_state.get("debug_llm_output") or "No debug output available.")
                        else:
                            st.session_state['phase1_done'] = True
                            st.session_state['phase1_data'] = final_state
                            st.session_state['last_generated_chapter'] = 1 # Chapter 1 is generated by default
                            status.update(label="✅ Story Foundation & Chapter 1 Generated!", state="complete")
                            time.sleep(1) # Give a moment before rerunning
                            st.rerun() # Rerun to update the UI state
                    except Exception as e:
                        status.update(label=f"A critical error occurred: {e}", state="error")
    else:
        st.success("✅ Story Foundation and Chapter 1 have been generated.")
        if st.session_state.get('phase1_data'):
            with st.expander("View Generated Plot Outline"):
                 st.json(st.session_state['phase1_data'].get('overall_plot_outline', 'Outline not available'))


    st.divider()

    # --- Step 2: Generate Subsequent Chapters ---
    st.header("3. Generate Subsequent Chapters")
    if st.session_state['phase1_done']:
        phase1_data = st.session_state.get('phase1_data', {})
        total_chapters = len(phase1_data.get('overall_plot_outline', []))
        last_gen = st.session_state['last_generated_chapter']
        next_chapter_to_gen = last_gen + 1

        if next_chapter_to_gen <= total_chapters:
            if st.button(f"✍️ Generate Chapter {next_chapter_to_gen}", use_container_width=True):
                with st.status(f"Writing Chapter {next_chapter_to_gen}...", expanded=True) as status:
                    try:
                        # Load the state from the end of the previously generated chapter
                        state_filename = os.path.join(OUTPUT_DIR, f"chapter_{last_gen}_state.json")
                        with open(state_filename, 'r', encoding='utf-8') as f:
                            last_chapter_states = json.load(f)

                        #
                        # ***** THE FIX IS HERE *****
                        # Prepare the state for the new chapter run, ensuring original concepts are included
                        # to prevent the graph from re-running the initial input node.
                        #
                        chapter_initial_state = {
                            # --- CARRY OVER ORIGINAL CONCEPTS TO SKIP INPUT NODE ---
                            "user_world_concept": phase1_data.get("user_world_concept"),
                            "user_character_concept": phase1_data.get("user_character_concept"),
                            "user_story_premise": phase1_data.get("user_story_premise"),

                            # --- CARRY OVER BIBLE & OUTLINE ---
                            "world_details": phase1_data.get("world_details"),
                            "character_profile": phase1_data.get("character_profile"),
                            "overall_plot_outline": phase1_data.get("overall_plot_outline"),

                            # --- SET DYNAMIC STATE FOR THE NEW CHAPTER ---
                            "current_chapter_index": next_chapter_to_gen - 1, # Index is number - 1
                            "character_states": last_chapter_states,
                            "completed_chapter_prose": [], # Reset for the new chapter
                            "error": None, # Clear any previous errors
                        }

                        final_chapter_state = app.invoke(chapter_initial_state, config={"recursion_limit": 150})

                        if final_chapter_state.get("error"):
                            status.update(label=f"Chapter {next_chapter_to_gen} Failed: {final_chapter_state.get('error')}", state="error")
                        else:
                            st.session_state['last_generated_chapter'] = next_chapter_to_gen
                            status.update(label=f"✅ Chapter {next_chapter_to_gen} Written and Saved!", state="complete")
                            time.sleep(1)
                            st.rerun()
                    except FileNotFoundError:
                        st.error(f"Could not find state file for Chapter {last_gen} ('{state_filename}'). Cannot proceed.")
                    except Exception as e:
                        status.update(label=f"A critical error occurred: {e}", state="error")
        else:
            st.info("🎉 All chapters have been generated!")
    else:
        st.info("Please generate the story foundation first.")


# ==================================================================================
# --- TAB 2: READ NOVEL ---
# ==================================================================================
with tab2:
    st.header("Your Generated Novel")
    st.markdown("Use the dropdown to select and read the chapters you have generated.")

    chapters = get_generated_chapters()

    if not chapters:
        st.info("No chapters have been generated yet. Go to the '✍️ Generate Story' tab to start.", icon="👈")
    else:
        selected_chapter_num = st.selectbox(
            "Select a chapter to read:",
            options=chapters,
            format_func=lambda x: f"Chapter {x}"
        )
        st.divider()
        if selected_chapter_num:
            prose_filename = os.path.join(OUTPUT_DIR, f"chapter_{selected_chapter_num}_scenes.json")
            try:
                with open(prose_filename, 'r', encoding='utf-8') as f:
                    scenes_prose = json.load(f)
                st.subheader(f"Chapter {selected_chapter_num}")
                if isinstance(scenes_prose, list) and scenes_prose:
                    for i, scene_text in enumerate(scenes_prose):
                        st.markdown(f"**Scene {i+1}**")
                        st.markdown(scene_text)
                        st.markdown("---")
                else:
                    st.warning("This chapter file seems to be empty or in an incorrect format.")
            except Exception as e:
                st.error(f"Could not read chapter file. Error: {e}")