import os
import yaml

# Use relative imports for tools (works with both module and script execution)
from .tools.pdf_utils import extract_text_from_pdf
from .tools.django_mapper import save_extracted_data

# Import CrewAI core classes (adjust if your package is different)
from crewai import Crew, Agent, Task

# --- Load YAML Configs ---
def load_yaml_config(filename):
    config_dir = os.path.join(os.path.dirname(__file__), 'config')
    with open(os.path.join(config_dir, filename), 'r') as f:
        return yaml.safe_load(f)

agents_yaml = load_yaml_config('agents.yaml')
tasks_yaml = load_yaml_config('tasks.yaml')

# --- Build Agents ---
all_agents = {}
for agent_conf in agents_yaml['agents']:
    agent = Agent(
        name=agent_conf['name'],
        role=agent_conf.get('role', ''),
        goal=agent_conf.get('goal', ''),
        backstory=agent_conf.get('backstory', ''),
        verbose=True,
        allow_delegation=True,
         llm=agent_conf.get('llm')  
    )
    all_agents[agent_conf['name']] = agent

# --- Build Tasks (ensure 'name' attribute is set!) ---
all_tasks = []
for task_conf in tasks_yaml['tasks']:
    agent_name = task_conf['agent']
    agent_instance = all_agents.get(agent_name)
    if not agent_instance:
        raise ValueError(f"Agent '{agent_name}' not found for task '{task_conf['name']}'")
    task = Task(
        name=task_conf['name'],  # This is crucial!
        description=task_conf['description'],
        agent=agent_instance,
        expected_output=task_conf['expected_output'],
        # Optionally add inputs/outputs if your Task class supports them
        # inputs=task_conf.get('inputs', []),
        # outputs=task_conf.get('outputs', []),
    )
    all_tasks.append(task)

# --- Create Crew ---
my_crew_instance = Crew(
    agents=list(all_agents.values()),
    tasks=all_tasks,
    verbose=True
)

# --- Document Processing Function ---
def process_document(pdf_path):
    print(f"Starting document processing for: {pdf_path}")
    page_text = extract_text_from_pdf(pdf_path, page_number=0)
    # CrewAI v0.20+ uses .kickoff(), not .run()
    structure_result = my_crew_instance.kickoff(inputs={'page_text': page_text})
    print(f"Structure extracted: {structure_result}")
    # You can save or further process the result here
    # save_extracted_data(structure_result)
