📖 NovaTale: An AI-Powered Story Generation Engine
NovaTale is a sophisticated, agentic workflow designed to transform high-level creative concepts into fully written, multi-chapter novels. Using a multi-agent system powered by Google's Gemini-1.5-Flash and orchestrated by LangGraph, this engine can autonomously generate a detailed story bible, plot outline, and scene-by-scene prose.

The project includes an interactive web interface built with Streamlit, providing a user-friendly experience from concept to final manuscript.

✨ Core Features
Conceptual Generation: Starts from three simple user inputs: a world concept, a character concept, and a story premise.
Automated World-Building: Creates a detailed "Story Bible," including key locations, world rules, and character profiles.
Dynamic Plotting: Generates a complete, multi-chapter plot outline based on the initial concepts.
Scene-by-Scene Writing: Writes each chapter scene by scene, ensuring narrative cohesion and focus.
Interactive UI: A simple and intuitive Streamlit web app allows for easy interaction, generation control, and reading of the final output.
Resilient & Adaptable: The agent-based architecture is designed to be resilient to common LLM inconsistencies, with robust parsing and error handling.
🚀 Live Demo
(Here you can add a screenshot or a GIF of your Streamlit application in action. A screenshot of the two tabs would be perfect.)

🛠️ Technology Stack
AI/LLM: Google Gemini-1.5-Flash
Orchestration: LangGraph
Core Frameworks: LangChain, Pydantic
Frontend: Streamlit
Language: Python
📂 Project Structure
The project is organized into modular components, separating concerns for clarity and scalability.

nova-tale/
│
├── novel_output/             # Generated chapters and states are saved here
│   ├── chapter_1_scenes.json
│   └── chapter_1_state.json
│
├── app_ui.py                 # The Streamlit frontend application
├── main.py                   # Original command-line interface logic (optional to run)
├── graph.py                  # Defines the LangGraph agent workflow
├── agents.py                 # Contains all agent logic (world-building, plotting, scene writing)
├── data_models.py            # Pydantic models defining all data structures (outlines, profiles)
├── config.py                 # Gemini model configuration, API key, and safety settings
└── README.md                 # This file
⚙️ Setup and Installation
Follow these steps to get the NovaTale engine running on your local machine.

1. Prerequisites
Python 3.9 or higher.
A Google AI (Gemini) API Key. You can get one from Google AI Studio.

2. Clone the Repository

Bash

git clone https://github.com/sabeel111/Novatale.git
cd Novatale

3. Set Up a Virtual Environment (Recommended)
Bash

# For Windows
python -m venv venv
venv\Scripts\activate

# For macOS/Linux
python3 -m venv venv
source venv/bin/activate

4. Install Dependencies
Install all the required Python packages.

Bash

pip install streamlit langchain langgraph langchain-google-genai pydantic

5. Configure Your API Key
Open the config.py file and replace the placeholder with your actual Gemini API key.

Python

# nova-tale/config.py

# ...
# --- !!! Replace placeholder with your actual key for testing.   !!! ---
GEMINI_API_KEY = "YOUR_ACTUAL_GEMINI_API_KEY_HERE" # <<< PASTE YOUR KEY
# ...

▶️ How to Run
Once the setup is complete, you can start the interactive web application with a single command:

Bash

streamlit run app_ui.py
Your web browser will automatically open a new tab with the application running.

🔬 How It Works: The Agentic Workflow
The engine operates as a stateful graph where each node is a specialized "agent" responsible for a specific task.

UI (app_ui.py): Collects the initial high-level concepts from the user.
Graph Entry (graph.py): The UI invokes the LangGraph application, passing the concepts into the initial state.

Foundation Agents (agents.py):
world_bible_agent_node: Generates the world's tone, rules, and key locations.

character_bible_agent_node: Creates a detailed profile for the main character.

overall_plot_agent_node: Outlines the entire story, chapter by chapter. This node is built to be resilient to format changes from the LLM.

Chapter Generation Loop (graph.py): The graph then enters a chapter-by-chapter generation loop. For each chapter:

chapter_planner_agent_node: Takes the chapter summary and breaks it down into a detailed list of scenes. This node is also highly resilient to LLM inconsistencies.

Scene Loop: The graph iterates through the generated scenes. For each scene:

scene_generator_agent_node: Writes the full narrative prose for the scene based on its goal, the characters present, and the preceding context.

State Management: The graph state holds all the generated artifacts (world details, character profiles, prose) and is passed between nodes, ensuring consistency. At the end of each chapter, the final character states are saved to a file.

UI Control: The Streamlit UI manages the invocation of the graph, first for the foundation and Chapter 1, and then for each subsequent chapter at the user's command, providing a controlled, rate-limit-friendly workflow.

⚠️ Troubleshooting
LLM Returns an Empty String for a Scene: This is almost always caused by the API's safety filters blocking content, especially for scenes involving conflict or violence. The config.py file includes permissive safety_settings to prevent this. Ensure they are being passed to the ChatGoogleGenerativeAI instances.
Validation Errors (JSON format issues): The LLM can be inconsistent in its JSON output. The overall_plot_agent_node and chapter_planner_agent_node in agents.py have been specifically refactored to handle multiple possible key formats (e.g., description, plot_points, scene_goal) to prevent these errors.

🗺️ Future Roadmap
[ ] Multi-Character Support: Manage states and profiles for multiple characters.
[ ] In-UI Editing: Allow users to edit the generated outline or character profiles before proceeding to prose generation.
[ ] "Regenerate" Button: Add functionality to regenerate a specific scene or chapter.
[ ] Advanced Consistency: Implement a true vector-based memory/consistency checker agent.
[ ] Export Options: Add buttons to export the final novel to .txt, .md, or .epub formats
