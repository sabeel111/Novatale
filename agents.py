# novel_mvp/agents.py (for Gemini branch)
import json
import sys
import os
import re # Import regex for parsing
from typing import List, Optional, Dict, Any

# Langchain/Pydantic imports
from langchain_core.prompts import ChatPromptTemplate
# Using v1 for compatibility with LangChain examples if needed
from langchain_core.pydantic_v1 import ValidationError, BaseModel
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.exceptions import OutputParserException

# Project imports
# Assumes data_models.py (v9) defines these models
from data_models import (
    GraphState, WorldDetails, CharacterProfile, AllCharacterStates,
    CharacterDynamicState, ChapterOutlineItem,
    SceneOutlineItem
)
# Imports llm instances from config.py (which is the Gemini version)
from config import llm_standard, llm_json_strict

# --- Constants ---
OUTPUT_DIR = "novel_output"

# --- Helper Functions ---
def _ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        try:
            os.makedirs(OUTPUT_DIR); print(f"Created output directory: {OUTPUT_DIR}")
        except OSError as e: print(f"Error creating output directory {OUTPUT_DIR}: {e}", file=sys.stderr)

# --- Phase 1 Agent Node Functions ---
# get_user_input, world_bible_agent_node, character_bible_agent_node (manual parse),
# overall_plot_agent_node (JSON extraction) remain the same
# (Code omitted for brevity - assume they are as in the previous correct version)
def get_user_input(state: GraphState) -> GraphState:
    """Initializes state with user input and Phase 2 defaults."""
    if state.get("user_world_concept") and state.get("user_character_concept") and state.get("user_story_premise"):
        print("--- User Input Node ---\nPhase 1 inputs already exist in state. Skipping user input.")
        state.setdefault("current_chapter_index", 0); state.setdefault("completed_chapter_prose", []); state.setdefault("current_scene_index", 0)
        return state
    if llm_standard is None or llm_json_strict is None: raise RuntimeError("LLMs not initialized.")
    print("--- User Input Node (Phase 1: Bible & Outline Setup) ---")
    world_concept = input("Describe the core concept/genre/rules of your world: ")
    char_concept = input("Describe your main character concept (traits, role): ")
    story_premise = input("What is the overall premise or goal of the story? ")
    print("------------------------------------------------------\n")
    initial_state_dict = {
        "user_world_concept": world_concept, "user_character_concept": char_concept,
        "user_story_premise": story_premise, "world_details": None, "character_profile": None,
        "overall_plot_outline": None, "current_chapter_index": 0, "current_chapter_summary": None,
        "chapter_scene_outline": None, "current_scene_index": 0, "current_scene_goal": None,
        "current_scene_prose": None, "completed_chapter_prose": [], "character_states": None,
        "consistency_notes": None, "error": None, "debug_llm_output": None,
    }
    return initial_state_dict # type: ignore

def world_bible_agent_node(state: GraphState) -> GraphState:
    """Generates WorldDetails using JSON mode LLM."""
    print("--- World Bible Agent Node ---")
    if state.get("world_details") is not None: print("World details already exist. Skipping."); return state
    world_concept = state.get("user_world_concept")
    if not world_concept: return {**state, "error": "User world concept missing."} # type: ignore
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """You are a world-building assistant... [Your detailed prompt with emphasis on ALL fields] ..."""),
        ("human", "User World Concept: {world_concept}\n\nGenerate the World Details JSON object.")
    ])
    parser = JsonOutputParser(pydantic_object=WorldDetails)
    chain = prompt_template | llm_json_strict | parser
    try:
        print(f"Generating World Bible based on concept: '{world_concept[:100]}...'")
        world_details_obj = chain.invoke({"world_concept": world_concept})
        if not isinstance(world_details_obj, WorldDetails):
            if isinstance(world_details_obj, dict): world_details_obj = WorldDetails(**world_details_obj)
            else: raise TypeError(f"Expected WorldDetails/dict, got {type(world_details_obj)}")
        print("World Bible Details Generated and Validated.")
        return {**state, "world_details": world_details_obj, "error": None} # type: ignore
    except (ValidationError, TypeError, json.JSONDecodeError, Exception) as e:
        error_msg = f"World Bible Agent Error ({type(e).__name__}): {e}"
        print(error_msg, file=sys.stderr); raw_output = None
        try:
            raw_output = (prompt_template | llm_json_strict | StrOutputParser()).invoke({"world_concept": world_concept})
            print(f"--- Raw LLM Output (Error Debug) ---\n{raw_output}\n---", file=sys.stderr)
        except Exception as raw_e: print(f"Could not retrieve raw output: {raw_e}", file=sys.stderr)
        return {**state, "error": error_msg, "world_details": None, "debug_llm_output": raw_output or state.get("debug_llm_output")} # type: ignore

def character_bible_agent_node(state: GraphState) -> GraphState:
    """Generates CharacterProfile using manual text parsing."""
    print("--- Character Bible Agent Node (Manual Parse Mode) ---")
    if state.get("character_profile") is not None:
        print("Character profile already exists. Skipping."); return state
    char_concept = state.get("user_character_concept"); world_details = state.get("world_details")
    if not char_concept: return {**state, "error": "User character concept missing."} # type: ignore
    world_context_str = "No world context available."
    if world_details:
        try: # Create concise text summary
            tone = world_details.overall_tone or 'N/A'; locs = ", ".join([l.name for l in world_details.key_locations]) if world_details.key_locations else 'N/A'
            rules = "; ".join(world_details.core_rules) if world_details.core_rules else 'N/A'; hist = world_details.history_snippet or 'N/A'
            world_context_str = f"Tone: {tone}. Key Locations: {locs}. Core Rules: {rules}. History Snippet: {hist}"
        except Exception as dump_e: print(f"Warning: Could not serialize world_details: {dump_e}", file=sys.stderr); world_context_str = "Error serializing world context."
    prompt_template = ChatPromptTemplate.from_messages([
         ("system", f"""You are a character creation assistant... Provide info using labels EXACTLY: Name:, Description:, Backstory:, Motivation:, Fears: ... World Context: {world_context_str}"""),
         ("human", "User Character Concept:\n```\n{character_concept}\n```\n\nGenerate the profile using labels.")
    ])
    parser = StrOutputParser()
    chain = prompt_template | llm_standard | parser
    llm_output_str = ""
    try:
        print(f"Generating Character Profile text based on concept: '{char_concept[:100]}...'")
        llm_output_str = chain.invoke({"character_concept": char_concept, "world_context": world_context_str})
        print(f"--- Raw LLM text output for Character Profile ---\n{llm_output_str}\n---")
        parsed_data = {}; labels = ["Name", "Description", "Backstory", "Motivation", "Fears"]
        for label in labels:
            match = re.search(rf"^\s*(?:\*\*)?{re.escape(label)}(?:\*\*)?\s*:\s*(.*)", llm_output_str, re.IGNORECASE | re.MULTILINE)
            if match: value = match.group(1).strip(); parsed_data[label.lower()] = None if label.lower() == 'fears' and value.lower() == 'none' else value
            else: print(f"Warning: Label '{label}:' not found.", file=sys.stderr); parsed_data[label.lower()] = None
        fears_str = parsed_data.get("fears")
        parsed_data["fears"] = [fear.strip() for fear in fears_str.split(';') if fear.strip()] if isinstance(fears_str, str) else None
        profile_data = {"name": parsed_data.get("name"), "description": parsed_data.get("description"), "backstory": parsed_data.get("backstory"), "core_motivation": parsed_data.get("motivation"), "fears": parsed_data.get("fears")}
        print(f"Attempting validation with parsed data: {profile_data}")
        char_profile_obj = CharacterProfile(**profile_data)
        print("Character Profile Parsed and Validated successfully.")
        initial_char_state: AllCharacterStates = { char_profile_obj.name: {"mood": "neutral", "location": "Unknown"} }
        print(f"Initialized character state for {char_profile_obj.name}")
        return {**state, "character_profile": char_profile_obj, "character_states": initial_char_state, "error": None} # type: ignore
    except (ValidationError, TypeError, ValueError, Exception) as e:
        error_msg = f"Character Bible Agent Error ({type(e).__name__}): Failed to generate/parse character profile text. {e}"
        print(error_msg, file=sys.stderr); raw_output = llm_output_str if llm_output_str else "Could not retrieve raw LLM output."
        print(f"--- Raw LLM Output (Error Debug) ---\n{raw_output}\n---", file=sys.stderr)
        return {**state, "error": error_msg, "character_profile": None, "character_states": None, "debug_llm_output": raw_output} # type: ignore

def overall_plot_agent_node(state: GraphState) -> GraphState:
    """Generates overall plot outline as List[ChapterOutlineItem] objects using JSON extraction."""
    print("--- Overall Plot Agent Node (Extracting JSON) ---")
    if state.get("overall_plot_outline") is not None: print("Overall plot outline already exists. Skipping."); return state
    story_premise = state.get("user_story_premise"); world_details = state.get("world_details"); char_profile = state.get("character_profile")
    if not story_premise or not world_details or not char_profile: return {**state, "error": "Missing data for plot generation."} # type: ignore
    try: world_str = world_details.model_dump_json(indent=2) if hasattr(world_details, 'model_dump_json') else world_details.json(indent=2)
    except Exception as dump_e: world_str = f"Error serializing world details: {dump_e}"
    try: char_str = char_profile.model_dump_json(indent=2) if hasattr(char_profile, 'model_dump_json') else char_profile.json(indent=2)
    except Exception as dump_e: char_str = f"Error serializing character profile: {dump_e}"
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """You are a master storyteller outlining a novel... [Your detailed prompt expecting List[ChapterOutlineItem] JSON with a 'description' or 'plot_points' field for each chapter]..."""),
        ("human", "Story Premise:\n```\n{story_premise}\n```\nCharacter Profile:\n```json\n{character_profile}\n```\nWorld Details:\n```json\n{world_details}\n```\nGenerate the JSON list of chapter outline objects.")
    ])
    chain = prompt_template | llm_standard | StrOutputParser()
    parser = JsonOutputParser(pydantic_object=List[ChapterOutlineItem])
    llm_output_str = ""
    try:
        print(f"Generating Overall Plot Outline text based on premise: '{story_premise[:100]}...'")
        llm_output_str = chain.invoke({"story_premise": story_premise, "character_profile": char_str, "world_details": world_str})
        print(f"--- Raw LLM text output for Plot Outline ---\n{llm_output_str}\n---")
        json_str = None; start_index = llm_output_str.find('['); end_index = llm_output_str.rfind(']')
        if start_index != -1 and end_index != -1 and end_index > start_index:
            json_str = llm_output_str[start_index : end_index + 1]
            print("Extracted JSON string snippet:", json_str[:100] + "..." if len(json_str) > 100 else json_str)
        else: raise OutputParserException("Could not find JSON list structure (`[...]`) in LLM output.")
        
        # Parse the JSON string into a Python list of dictionaries
        parsed_output = json.loads(json_str)

        # ***** NEW: PRE-PROCESSING LOGIC TO HANDLE DIFFERENT LLM OUTPUT FORMATS *****
        if isinstance(parsed_output, list):
            for item in parsed_output:
                # If the item is a dict and is missing 'description' but has 'plot_points'
                if isinstance(item, dict) and 'description' not in item and 'plot_points' in item and isinstance(item.get('plot_points'), list):
                    # Synthesize the 'description' field by joining the plot points
                    item['description'] = " ".join(str(p) for p in item['plot_points'])
                    print(f"INFO: Synthesized 'description' from 'plot_points' for a chapter.")
        # ***** END OF NEW LOGIC *****

        # Now, validate the (potentially modified) list of dictionaries using the Pydantic parser
        validated_outline: List[ChapterOutlineItem] = [ChapterOutlineItem(**item) for item in parsed_output]

        if not validated_outline: raise ValueError("Outline generation resulted in empty list after validation.")
        print("Overall Plot Outline Extracted, Parsed, and Validated (as List[ChapterOutlineItem]).")
        return {**state, "overall_plot_outline": validated_outline, "error": None} # type: ignore
    except (OutputParserException, ValidationError, TypeError, ValueError, json.JSONDecodeError, Exception) as e:
        error_msg = f"Overall Plot Agent Error ({type(e).__name__}): Failed to extract/parse/validate List[ChapterOutlineItem]. {e}"
        print(error_msg, file=sys.stderr); raw_output = llm_output_str if llm_output_str else "Could not retrieve raw LLM output."
        print(f"--- Raw LLM Output (Error Debug) ---\n{raw_output}\n---", file=sys.stderr)
        return {**state, "error": error_msg, "overall_plot_outline": None, "debug_llm_output": raw_output} # type: ignore

def chapter_planner_agent_node(state: GraphState) -> GraphState:
    """Generates scene outline as List[SceneOutlineItem] using JSON extraction."""
    print("--- Chapter Planner Agent Node (Extracting JSON) ---")
    if state.get("chapter_scene_outline") is not None: print("Chapter scene outline already exists. Skipping."); return state
    chapter_summary = state.get("current_chapter_summary"); world_details = state.get("world_details"); char_profile = state.get("character_profile")
    if not chapter_summary or not world_details or not char_profile: return {**state, "error": "Missing data for chapter planning."} # type: ignore
    try: world_str = world_details.model_dump_json(indent=2) if hasattr(world_details, 'model_dump_json') else world_details.json(indent=2)
    except Exception as dump_e: world_str = f"Error serializing world details: {dump_e}"
    try: char_str = char_profile.model_dump_json(indent=2) if hasattr(char_profile, 'model_dump_json') else char_profile.json(indent=2)
    except Exception as dump_e: char_str = f"Error serializing character profile: {dump_e}"
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """You are a detailed novel plotter. Break the given chapter summary down into a series of distinct scenes. For each scene, provide a title, a specific goal or summary, characters, setting, and key plot points. Output a JSON list of scene objects."""),
        ("human", "Overall Chapter Goal/Summary:\n```\n{chapter_summary}\n```\nCharacter Profile:\n```json\n{character_profile}\n```\nWorld Details:\n```json\n{world_details}\n```\nGenerate the JSON list of scene outline objects.")
    ])
    chain = prompt_template | llm_standard | StrOutputParser()
    llm_output_str = ""
    try:
        print(f"Generating Scene Outline text for Chapter {state.get('current_chapter_index', 0)+1}...")
        llm_output_str = chain.invoke({"chapter_summary": chapter_summary, "character_profile": char_str, "world_details": world_str})
        print(f"--- Raw LLM text output for Scene Outline ---\n{llm_output_str}\n---")
        json_str = None; start_index = llm_output_str.find('['); end_index = llm_output_str.rfind(']')
        if start_index != -1 and end_index != -1 and end_index > start_index:
            json_str = llm_output_str[start_index : end_index + 1]
            print("Extracted JSON string snippet:", json_str[:100] + "..." if len(json_str) > 100 else json_str)
        else: raise OutputParserException("Could not find JSON list structure (`[...]`) in LLM output for scene outline.")
        
        # More robust parsing starts here
        parsed_output = json.loads(json_str)
        
        # Pre-process the data to handle LLM inconsistencies
        if isinstance(parsed_output, list):
            for item in parsed_output:
                if not isinstance(item, dict): continue
                
                # Check for various possible keys for the summary/goal and map them
                # to 'scene_summary', which is the alias for our 'summary' field.
                if 'scene_summary' not in item:
                    if 'scene_goal' in item:
                        item['scene_summary'] = item['scene_goal']
                        print("INFO: Mapped 'scene_goal' to 'scene_summary'.")
                    elif 'description' in item:
                        item['scene_summary'] = item['description']
                        print("INFO: Mapped 'description' to 'scene_summary'.")
                    elif 'plot_points' in item and isinstance(item.get('plot_points'), list):
                        item['scene_summary'] = " ".join(str(p) for p in item['plot_points'])
                        print("INFO: Synthesized 'scene_summary' from 'plot_points'.")

                # Map variations of title
                if 'scene_title' not in item and 'title' in item:
                    item['scene_title'] = item['title']

        # Validate the cleaned-up data
        validated_scene_outline = [SceneOutlineItem(**item) for item in parsed_output]

        if not validated_scene_outline: raise ValueError("Scene outline generation resulted in empty list after validation.")
        print(f"Scene Outline Extracted, Parsed, and Validated ({len(validated_scene_outline)} scenes).")
        return {**state, "chapter_scene_outline": validated_scene_outline, "error": None} # type: ignore
    except (OutputParserException, ValidationError, TypeError, ValueError, json.JSONDecodeError, Exception) as e:
        error_msg = f"Chapter Planner Agent Error ({type(e).__name__}): Failed to extract/parse/validate scene outline. {e}"
        print(error_msg, file=sys.stderr)
        raw_output = llm_output_str if llm_output_str else "Could not retrieve raw LLM output."
        print(f"--- Raw LLM Output (Error Debug) ---\n{raw_output}\n---", file=sys.stderr)
        return {**state, "error": error_msg, "chapter_scene_outline": None, "debug_llm_output": raw_output} # type: ignore


# --- Phase 2 Agents ---

# --- IMPLEMENTED scene_generator_agent_node ---
def scene_generator_agent_node(state: GraphState) -> GraphState:
    """Generates narrative prose for the current scene."""
    print(f"--- Scene Generator Agent Node ---")
    # Retrieve necessary info from state
    scene_goal = state.get("current_scene_goal")
    chapter_index = state.get("current_chapter_index", 0)
    scene_index = state.get("current_scene_index", 0)
    world_details = state.get("world_details")
    char_profile = state.get("character_profile") # Assuming single character
    char_states = state.get("character_states")
    completed_prose = state.get("completed_chapter_prose", [])
    chapter_summary = state.get("current_chapter_summary") # Broader chapter context

    # Basic check for essential inputs
    if not scene_goal or not world_details or not char_profile or not char_states:
        error_msg = "Missing required context (scene goal, world, character profile/state) for scene generation."
        print(error_msg, file=sys.stderr)
        return {**state, "error": error_msg} # type: ignore

    # --- Prepare Context for Prompt ---
    try:
        # Get current dynamic state for the main character
        char_name = char_profile.name
        current_char_dynamic_state = char_states.get(char_name, {"mood": "neutral", "location": "Unknown"})
        char_mood = current_char_dynamic_state.get("mood", "neutral")
        char_location = current_char_dynamic_state.get("location", "Unknown")

        # Get context from the previous scene (if it exists)
        previous_scene_context = ""
        if scene_index > 0 and completed_prose: # Check index > 0
            # Get the last few sentences of the previous scene
            last_scene = completed_prose[-1]
            # Simple sentence split, might need refinement
            sentences = [s for s in last_scene.split('.') if s]
            context_sentences = sentences[-3:] # Take last 3 sentences approx
            previous_scene_context = ". ".join(context_sentences).strip()
            if previous_scene_context:
                 previous_scene_context += "." # Add punctuation back if needed
        else:
            previous_scene_context = "This is the first scene of the chapter."

        # Serialize necessary context details (summarize if needed)
        world_tone = world_details.overall_tone or "neutral"
        # Example: Summarize rules if too long
        world_rules_summary = "; ".join(world_details.core_rules[:2]) if world_details.core_rules else "Standard world rules apply."
        if len(world_details.core_rules) > 2: world_rules_summary += "..."
        # Example: Summarize description
        char_desc_summary = char_profile.description[:150] + ("..." if len(char_profile.description) > 150 else "")
        char_motivation = char_profile.core_motivation
    except Exception as context_err:
        error_msg = f"Error preparing context for scene generation: {context_err}"
        print(error_msg, file=sys.stderr)
        return {**state, "error": error_msg} # type: ignore

    # --- Prompt Engineering ---
    # Construct the detailed prompt using an f-string
    system_prompt = f"""You are a skilled novelist writing a scene for a political thriller with action and romance elements.

**Overall World Context:**
- Tone: {world_tone}
- Key Rules: {world_rules_summary}

**Character Profile ({char_name}):**
- Description: {char_desc_summary}
- Core Motivation: {char_motivation}
- Current State: Mood is {char_mood}, Location is {char_location}.

**Chapter Context:**
- Overall Goal: {chapter_summary}

**Scene Context:**
- Previous Scene Ending: {previous_scene_context}
- **This Scene's Goal:** {scene_goal}

**Your Task:** Write the narrative prose for this specific scene.
- Aim for approximately 3-5 substantial paragraphs.
- Focus on fulfilling the Scene Goal.
- Incorporate the character's current state (mood, location) and personality traits.
- Reflect the character's core motivation in their actions, thoughts, or dialogue.
- Maintain the established world tone (political thriller, action, romance).
- Ensure smooth continuity from the previous scene ending.
- Use vivid descriptions and actions. Include dialogue naturally where it serves the scene's goal and reveals character or advances the plot.
- Show, don't just tell.
- Output ONLY the raw narrative prose for the scene, with proper paragraph breaks. Do not include any introductory text, labels, summaries, or markdown formatting.
"""
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Write the scene based on the provided goal and context.") # Simple trigger
    ])

    # Use standard LLM for creative writing
    chain = prompt_template | llm_standard | StrOutputParser()

    try:
        print(f"Generating prose for: Chapter {chapter_index+1}, Scene {scene_index+1}")
        print(f"Scene Goal: {scene_goal}")
        # Invoke the chain (no extra variables needed in invoke dict if embedded in f-string)
        generated_prose = chain.invoke({})

        # Basic cleaning (remove leading/trailing whitespace)
        generated_prose = generated_prose.strip()

        if not generated_prose:
            # Handle empty output from LLM
            raise ValueError("LLM returned empty string for scene prose.")

        print(f"--- Generated Prose Snippet ---\n{generated_prose[:300]}...\n---") # Show a bit more
        # Update state with the successfully generated prose
        return {**state, "current_scene_prose": generated_prose, "error": None} # type: ignore

    except Exception as e:
        # Catch errors during LLM call or processing
        error_msg = f"Scene Generator Agent Error ({type(e).__name__}): {e}"
        print(error_msg, file=sys.stderr)
        # Try to store the error and potentially debug info (like the prompt itself)
        raw_output = f"Failed during generation. Prompt System:\n{system_prompt}" # Save prompt on error
        return {**state, "error": error_msg, "current_scene_prose": None, "debug_llm_output": raw_output} # type: ignore


# --- Placeholder Phase 2 Agents ---
def consistency_checker_agent_node(state: GraphState) -> GraphState:
    """[PLACEHOLDER] Checks the generated scene for consistency. Non-blocking."""
    print(f"--- Consistency Checker Agent Node (Placeholder) ---")
    # ... (placeholder logic remains the same) ...
    scene_prose = state.get("current_scene_prose"); chapter_index = state.get("current_chapter_index", 0); scene_index = state.get("current_scene_index", 0)
    notes = []
    if scene_prose:
        print(f"Checking consistency for: Chapter {chapter_index+1}, Scene {scene_index+1}")
        # TODO: Implement actual consistency checks
        if "placeholder contradiction" in scene_prose.lower(): notes.append(f"Placeholder contradiction noted in Scene {scene_index+1}.")
    if notes: print(f"Consistency Notes Found: {notes}")
    return {**state, "consistency_notes": notes} # type: ignore

def character_state_update_agent_node(state: GraphState) -> GraphState:
    """[PLACEHOLDER] Updates dynamic character states based on the generated scene."""
    print(f"--- Character State Update Agent Node (Placeholder) ---")
    # ... (placeholder logic remains the same) ...
    scene_prose = state.get("current_scene_prose"); current_states: AllCharacterStates = state.get("character_states") or {}; char_profile = state.get("character_profile")
    if not scene_prose or not char_profile or not current_states: print("Skipping character state update (missing data)."); return state # type: ignore
    char_name = char_profile.name
    print(f"Updating character states for {char_name} based on Scene {state.get('current_scene_index', 0)+1}...")
    # TODO: Implement actual state update logic (LLM call or rules)
    updated_states = current_states.copy()
    current_mood = updated_states.get(char_name, {}).get("mood", "neutral")
    print(f"{char_name} mood remains '{current_mood}'. (Placeholder)")
    return {**state, "character_states": updated_states, "error": None} # type: ignore

# --- Phase 2 Utility Node Functions ---
def save_chapter_output(state: GraphState) -> GraphState:
    """Saves the completed chapter prose and final character states to files."""
    print("--- Save Chapter Output Node ---")
    # ... (save logic remains the same) ...
    _ensure_output_dir(); chapter_index = state.get("current_chapter_index", 0); prose_list = state.get("completed_chapter_prose", []); final_char_states = state.get("character_states", {})
    prose_filename = os.path.join(OUTPUT_DIR, f"chapter_{chapter_index + 1}_scenes.json"); state_filename = os.path.join(OUTPUT_DIR, f"chapter_{chapter_index + 1}_state.json")
    try:
        print(f"Saving chapter {chapter_index + 1} prose ({len(prose_list)} scenes) to {prose_filename}...")
        with open(prose_filename, 'w', encoding='utf-8') as f: json.dump(prose_list, f, indent=2, ensure_ascii=False)
        print("Prose saved successfully.")
    except (IOError, TypeError) as e: print(f"Save Chapter Output Error: Failed to write prose file. {e}", file=sys.stderr)
    try:
        print(f"Saving chapter {chapter_index + 1} final character states to {state_filename}...")
        with open(state_filename, 'w', encoding='utf-8') as f: json.dump(final_char_states, f, indent=2, ensure_ascii=False)
        print("Character states saved successfully.")
    except (IOError, TypeError) as e: print(f"Save Chapter Output Error: Failed to write state file. {e}", file=sys.stderr)
    return state # type: ignore

# --- Final Output Node (Phase 1 / Error Handling) ---
def final_output_node(state: GraphState) -> GraphState:
    """Displays errors if generation stopped early."""
    print("\n" + "="*20 + " Final Output / State Summary " + "="*20)
    # ... (same as previous version) ...
    error = state.get("error")
    if error: print(f"\nWorkflow stopped due to error:\nError: {error}")
    else: print("\nRun finished. Check output files for generated chapters.")
    title_str = " Final Output / State Summary "; separator_len = 42 + len(title_str)
    print("\n" + "=" * separator_len)
    return state # type: ignore
