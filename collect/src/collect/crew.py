import yaml
import os
from crewai import Crew, Agent, Task
from .tools.pdf_utils import extract_text_from_pdf


from collect.src.collect.tools.django_mapper import save_extracted_data
# Function to load YAML configuration
def load_config(config_type):
    # This path is relative to the location of crew.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, 'config', f'{config_type}.yaml')
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Config file not found at {config_path}")
        return None

# Load agents configuration
agents_data = load_config('agents')
if agents_data is None:
    exit(1) # Exit if config not found
agents_config = agents_data.get('agents', [])

# Create Agent objects and store them in a dictionary for easy lookup by name
all_agents = {}
for agent_item in agents_config:
    agent_name = agent_item.get('name')
    if agent_name:
        all_agents[agent_name] = Agent(
            role=agent_item.get('role'),
            goal=agent_item.get('goal'),
            backstory=agent_item.get('backstory'),
            verbose=True, # Added for better debugging output
            allow_delegation=True # Common for complex crews
        )

# Load tasks configuration
tasks_data = load_config('tasks')
if tasks_data is None:
    exit(1) # Exit if config not found
tasks_config = tasks_data.get('tasks', [])

# Create Task objects
all_tasks = []
for task_item in tasks_config:
    task_agent_name = task_item.get('agent')
    agent_instance = all_agents.get(task_agent_name)
    if not agent_instance:
        raise ValueError(f"Agent '{task_agent_name}' not found for task '{task_item.get('name')}' in tasks.yaml. Check agent names in agents.yaml.")

    all_tasks.append(Task(
        description=task_item.get('description'),
        agent=agent_instance,
        expected_output=task_item.get('expected_output'),  # <-- REQUIRED
        # inputs and outputs are typically handled by agent reasoning or explicitly
        # passed during task execution, not defined as fixed Task attributes in this way.
        # For simplicity, we omit them here, but you can add them back if your CrewAI version
        # or specific task setup requires it directly in the Task constructor.
        # For example: inputs=task_item.get('inputs', []), etc.
    ))

# Initialize the Crew
my_crew_instance = Crew(
    agents=list(all_agents.values()), # Pass all created agent objects
    tasks=all_tasks,
    verbose=True # General verbose for the crew
)

def process_document(pdf_path):
    print(f"Starting document processing for: {pdf_path}")
    # 1. Extract text from the first page
    page_text = extract_text_from_pdf(pdf_path)
    # 2. Run the CrewAI structure extraction task
    structure_task = next((t for t in all_tasks if t.name == "extract_structure"), None)
    if structure_task:
        structure_result = my_crew_instance.run(structure_task, inputs={'page_text': page_text})
        print(f"Structure extracted: {structure_result}")
        # Continue with section extraction, entity extraction, tagging, saving, etc.
    else:
        print("No extract_structure task found in CrewAI tasks.")