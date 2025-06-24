# novel_mvp/graph.py (for Gemini branch)
import sys
from typing import List, Optional # Import List and Optional if needed for hints
from langgraph.graph import StateGraph, END

# Import state definition and agent functions
# Import Pydantic models used in helper functions
# Based on data_models_phase2_v8 context
from data_models import GraphState, ChapterOutlineItem, SceneOutlineItem
# Assumes agents.py is in the same directory
from agents import (
    # Phase 1 Agents
    get_user_input,
    world_bible_agent_node,
    character_bible_agent_node,
    overall_plot_agent_node,
    # Phase 2 Agents
    chapter_planner_agent_node,
    scene_generator_agent_node,      # Placeholder
    consistency_checker_agent_node,  # Placeholder (non-blocking)
    character_state_update_agent_node,# Placeholder
    save_chapter_output,             # Utility
    # Final Output/Error Node
    final_output_node
)

# --- Helper Function for Conditional Edges ---
def check_agent_error(state: GraphState) -> str:
    """Generic check for error state after an agent node."""
    if state.get("error"):
        print(f"DEBUG: Error detected ('{state.get('error')}'), routing to finalOutput.")
        return "finalOutput"
    else:
        # print("DEBUG: No error detected, continuing flow.") # Optional debug print
        return "continue" # Represents the normal next step

# --- Scene Loop Condition Function ---
# This function decides whether to generate the next scene or finish the chapter
def scene_loop_condition(state: GraphState) -> str:
    """Determines if there are more scenes to generate in the current chapter."""
    print("--- Scene Loop Condition Check ---")
    # Check for errors from the *previous* scene generation cycle first
    if state.get("error"):
        print("Error detected from previous scene cycle, exiting loop to save.")
        return "saveChapterOutput" # Save what we have accumulated so far

    scene_idx = state.get("current_scene_index", 0)
    scene_outline = state.get("chapter_scene_outline") # Now List[SceneOutlineItem]

    # Check if outline exists and index is within bounds
    if scene_outline is not None and isinstance(scene_outline, list) and scene_idx < len(scene_outline):
        print(f"Continue scene loop (Scene {scene_idx + 1}/{len(scene_outline)}).")
        return "prepareScene" # Go prepare and generate the next scene
    elif scene_outline is None:
         print("Error: Scene outline is missing, cannot continue loop. Finishing chapter.", file=sys.stderr)
         # Optionally set an error state here
         # state["error"] = "Scene outline missing during loop condition."
         return "saveChapterOutput" # Finish chapter, saving potentially empty prose
    else:
        # Index is out of bounds (or outline is empty), chapter finished
        print("Scene loop finished for chapter.")
        return "saveChapterOutput" # Chapter finished, save output

# --- Build the Graph ---
print("Building graph workflow (Phase 1 + Phase 2 Chapter Structure)...")
workflow = StateGraph(GraphState)

# --- Add Nodes ---
# Phase 1 Nodes
workflow.add_node("userInput", get_user_input)
workflow.add_node("worldBibleAgent", world_bible_agent_node)
workflow.add_node("characterBibleAgent", character_bible_agent_node)
workflow.add_node("overallPlotAgent", overall_plot_agent_node)

# Phase 2 Nodes
workflow.add_node("chapterPlanner", chapter_planner_agent_node)
# Scene Loop Nodes (Placeholders)
workflow.add_node("sceneGenerator", scene_generator_agent_node)
workflow.add_node("consistencyChecker", consistency_checker_agent_node)
workflow.add_node("characterStateUpdater", character_state_update_agent_node)
# Utility Nodes
workflow.add_node("saveChapterOutput", save_chapter_output)
workflow.add_node("finalOutput", final_output_node) # Handles errors or final summary

# --- Helper Nodes (Functions called by graph nodes) ---
# These functions manipulate state and are called by nodes added below.
def prepare_chapter_node(state: GraphState) -> GraphState:
    """Sets up state before starting chapter planning and scene loop."""
    print("--- Prepare Chapter Node ---")
    chapter_idx = state.get("current_chapter_index", 0)
    # Overall outline is now List[ChapterOutlineItem]
    outline: Optional[List[ChapterOutlineItem]] = state.get("overall_plot_outline")

    # Check if outline exists, is a list, index is valid, and item has 'summary'
    if (outline is None or not isinstance(outline, list) or chapter_idx >= len(outline)
        or not hasattr(outline[chapter_idx], 'summary') or not outline[chapter_idx].summary): # Check summary exists and is not empty
        error_msg = f"Cannot prepare chapter: Invalid index ({chapter_idx}) or missing/invalid outline structure/summary."
        print(error_msg, file=sys.stderr)
        # Set error state and return immediately
        # Returning dict directly is often safer with TypedDict updates
        return {**state, "error": error_msg} # type: ignore

    # Accessing .summary FROM ChapterOutlineItem
    chapter_summary = outline[chapter_idx].summary
    chapter_title = outline[chapter_idx].title # Get title too, might be useful

    print(f"Preparing Chapter {chapter_idx + 1}" + (f": {chapter_title}" if chapter_title else "") + f" - {chapter_summary[:100]}...")
    # Reset scene-specific state for the new chapter
    new_state = {
        **state,
        "current_chapter_summary": chapter_summary, # Store the summary string
        "chapter_scene_outline": None, # To be generated by planner
        "current_scene_index": 0,
        "current_scene_goal": None,
        "current_scene_prose": None,
        "completed_chapter_prose": [], # Reset for new chapter
        "consistency_notes": None,
        "error": None # Clear previous errors when starting a new chapter successfully
    }
    return new_state # type: ignore

# --- MODIFIED prepare_scene_node (from previous fix) ---
def prepare_scene_node(state: GraphState) -> GraphState:
    """Sets the current_scene_goal based on available fields in SceneOutlineItem."""
    print("--- Prepare Scene Node ---")
    scene_idx = state.get("current_scene_index", 0)
    # Scene outline is now List[SceneOutlineItem]
    scene_outline: Optional[List[SceneOutlineItem]] = state.get("chapter_scene_outline")

    # Check if outline exists, is a list, and index is valid
    if (scene_outline is None or not isinstance(scene_outline, list) or scene_idx >= len(scene_outline)):
        error_msg = f"Cannot prepare scene: Invalid index ({scene_idx}) or missing/invalid scene outline."
        print(error_msg, file=sys.stderr)
        return {**state, "error": error_msg} # type: ignore

    scene_item = scene_outline[scene_idx]
    scene_goal = None

    # ***** Deriving scene_goal more robustly *****
    # Try to use summary first (it's optional in the model now)
    if scene_item.summary:
        scene_goal = scene_item.summary
    # Fallback: Combine title and plot points if summary is missing/empty
    elif scene_item.plot_points and isinstance(scene_item.plot_points, list):
        goal_parts = []
        if scene_item.title:
            goal_parts.append(f"{scene_item.title}:")
        # Join plot points, ensuring they are strings
        goal_parts.extend([str(p) for p in scene_item.plot_points])
        scene_goal = " ".join(goal_parts)
    # Fallback: Use title only
    elif scene_item.title:
        scene_goal = scene_item.title
    # Fallback: Use setting if all else fails
    elif scene_item.scene_setting:
         scene_goal = f"Scene set in: {scene_item.scene_setting}"
    else:
        # If no usable field is found
        error_msg = f"Cannot determine scene goal for Scene {scene_idx + 1}. Missing usable fields (summary/plot_points/title/setting) in outline item: {scene_item}"
        print(error_msg, file=sys.stderr)
        return {**state, "error": error_msg} # type: ignore
    # ***** END Goal Derivation *****

    print(f"Preparing Scene {scene_idx + 1}" + (f": {scene_item.title}" if scene_item.title else "") + f" - Goal: {scene_goal[:100]}...")
    # Store the derived goal string
    return {**state, "current_scene_goal": scene_goal, "current_scene_prose": None} # type: ignore

def accumulate_scene_node(state: GraphState) -> GraphState:
    """Appends completed scene prose and increments scene index."""
    print("--- Accumulate Scene Node ---")
    current_prose = state.get("current_scene_prose")
    # Ensure completed_prose is a list, default to empty list if not found/None
    completed_prose = state.get("completed_chapter_prose") or []
    scene_idx = state.get("current_scene_index", 0)

    if current_prose:
        # Make sure it's a list before appending
        if not isinstance(completed_prose, list):
            print("Warning: completed_chapter_prose was not a list, resetting.", file=sys.stderr)
            completed_prose = []
        completed_prose.append(current_prose)
        print(f"Accumulated Scene {scene_idx + 1} prose.")
    else:
        # Log if no prose was generated (might indicate issue in sceneGenerator)
        print(f"Warning: No prose generated for Scene {scene_idx + 1} to accumulate.")

    # Increment scene index for the next loop check
    next_scene_idx = scene_idx + 1
    # Return updated state
    return {**state,
            "completed_chapter_prose": completed_prose,
            "current_scene_index": next_scene_idx,
            "current_scene_prose": None # Clear current scene prose after accumulation
            } # type: ignore

# Add helper nodes to the graph
workflow.add_node("prepareChapter", prepare_chapter_node)
workflow.add_node("prepareScene", prepare_scene_node)
workflow.add_node("accumulateScene", accumulate_scene_node)


# --- Define Edges ---
# Phase 1 Flow
workflow.set_entry_point("userInput")
workflow.add_edge("userInput", "worldBibleAgent")
workflow.add_conditional_edges("worldBibleAgent", check_agent_error, {"continue": "characterBibleAgent", "finalOutput": "finalOutput"})
workflow.add_conditional_edges("characterBibleAgent", check_agent_error, {"continue": "overallPlotAgent", "finalOutput": "finalOutput"})
workflow.add_conditional_edges(
    "overallPlotAgent", check_agent_error,
    {"continue": "prepareChapter", "finalOutput": "finalOutput"} # Start Phase 2
)

# Phase 2 Chapter Flow
workflow.add_conditional_edges(
    "prepareChapter", check_agent_error, # Check if prepareChapter had error
    {"continue": "chapterPlanner", "finalOutput": "finalOutput"}
)

# After Chapter Planner -> Check Scene Loop Condition
workflow.add_conditional_edges(
    "chapterPlanner",
    # Check for error first, if no error, proceed to check scene loop condition
    lambda state: "finalOutput" if state.get("error") else scene_loop_condition(state),
    {
        "prepareScene": "prepareScene",           # Start the first scene if condition met
        "saveChapterOutput": "saveChapterOutput", # Skip scenes if outline empty/error/condition not met
        "finalOutput": "finalOutput"              # Error occurred in chapterPlanner
    }
)

# After Accumulate Scene -> Check Scene Loop Condition
workflow.add_conditional_edges(
    "accumulateScene",
    scene_loop_condition, # Function to decide next step
    {
        "prepareScene": "prepareScene",           # Loop back to generate next scene
        "saveChapterOutput": "saveChapterOutput", # Exit loop, save chapter
    }
)

# Scene Generation Sequence (within the loop)
workflow.add_conditional_edges("prepareScene", check_agent_error, {"continue": "sceneGenerator", "finalOutput": "finalOutput"})
workflow.add_conditional_edges("sceneGenerator", check_agent_error, {"continue": "consistencyChecker", "finalOutput": "finalOutput"})
workflow.add_conditional_edges("consistencyChecker", check_agent_error, {"continue": "characterStateUpdater", "finalOutput": "finalOutput"})
workflow.add_conditional_edges("characterStateUpdater", check_agent_error, {"continue": "accumulateScene", "finalOutput": "finalOutput"})
# accumulateScene loops back via its conditional edge defined above

# End of Chapter Flow
workflow.add_conditional_edges(
    "saveChapterOutput", check_agent_error, # Check if saving caused an error
    {"continue": END, "finalOutput": "finalOutput"} # End graph execution for this chapter
)

# Error/Final Output Node
workflow.add_edge("finalOutput", END) # End graph after displaying final/error output

# --- Compile the graph ---
print("Compiling graph...")
app = None
try:
    # Compile the graph object - No recursion limit needed in compile
    app = workflow.compile()
    print("Graph compiled successfully.")
except Exception as e:
    # Print any errors during compilation
    print(f"ERROR: Failed to compile graph: {e}", file=sys.stderr)
    # Ensure app is None if compilation fails, so main.py can check
