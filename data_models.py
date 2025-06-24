# novel_mvp/data_models.py (for Gemini branch)
from typing import TypedDict, List, Optional, Dict, Any
# Using v1 for compatibility with LangChain examples if needed
from langchain_core.pydantic_v1 import BaseModel, Field, Extra

# --- Data Structures for Phase 1 ---
class Location(BaseModel):
    name: str = Field(description="The name of the location.")
    description: str = Field(description="A brief atmospheric description of the location.")

class WorldDetails(BaseModel):
    overall_tone: Optional[str] = Field(default=None, description="The overall tone and atmosphere of the world.")
    key_locations: List[Location] = Field(default=[])
    core_rules: List[str] = Field(default=[])
    history_snippet: str = Field(default="")

class CharacterProfile(BaseModel):
    name: str = Field(description="The character's full name.")
    description: str = Field(description="Physical appearance and key personality traits.")
    backstory: str = Field(description="A concise summary of the character's origin and relevant past experiences.")
    core_motivation: str = Field(description="The character's primary driving goal or desire in life.")
    fears: Optional[List[str]] = Field(default=None, description="List of significant fears or weaknesses.")

# --- Structure for Overall Plot Outline Items ---
class ChapterOutlineItem(BaseModel):
    title: Optional[str] = Field(default=None)
    summary: str = Field(alias='description', description="The summary of the chapter's main events or focus.")
    class Config:
        extra = Extra.allow

# --- Structure for Scene Outline Items ---
class SceneOutlineItem(BaseModel):
    """Represents details for a single scene within a chapter outline."""
    # Use aliases to map keys LLM actually used in the last run
    title: Optional[str] = Field(default=None)
    # ***** ADDED ALIAS: Allow 'scene_summary' key from LLM input *****
    summary: Optional[str] = Field(default=None, alias='scene_summary', description="Concise summary outlining key event/interaction.")
    # ***** ADDED ALIAS: Allow 'location' key from LLM input *****
    scene_setting: Optional[str] = Field(default=None, alias='location', description="Description of the scene's setting.")
    # Keep other optional fields
    characters: Optional[List[str]] = Field(default=None)
    plot_points: Optional[List[str]] = Field(default=None)
    # Add other fields if needed, mark Optional
    # scene_number: Optional[int] = Field(default=None) # Example if LLM provides it

    class Config:
        # Allow Pydantic to populate fields using aliases
        allow_population_by_field_name = True
        # Allow extra fields from LLM
        extra = Extra.allow

# --- Graph State Definition ---
CharacterDynamicState = Dict[str, str]
AllCharacterStates = Dict[str, CharacterDynamicState]

class GraphState(TypedDict):
    # Phase 1
    user_world_concept: Optional[str]
    user_character_concept: Optional[str]
    user_story_premise: Optional[str]
    world_details: Optional[WorldDetails]
    character_profile: Optional[CharacterProfile]
    overall_plot_outline: Optional[List[ChapterOutlineItem]]
    # Phase 2
    current_chapter_index: int
    current_chapter_summary: Optional[str]
    chapter_scene_outline: Optional[List[SceneOutlineItem]] # Expects list of scene objects
    current_scene_index: int
    current_scene_goal: Optional[str] # Stores the derived goal string
    current_scene_prose: Optional[str]
    completed_chapter_prose: List[str]
    character_states: Optional[AllCharacterStates]
    consistency_notes: Optional[List[str]]
    # General
    error: Optional[str]
    debug_llm_output: Optional[str]
