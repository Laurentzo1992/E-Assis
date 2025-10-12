import os
import yaml
import ast
from .tools.pdf_utils import extract_text_from_pdf
from crewai import Crew, Agent, Task

def load_yaml_config(filename):
    config_dir = os.path.join(os.path.dirname(__file__), 'config')
    with open(os.path.join(config_dir, filename), 'r') as f:
        return yaml.safe_load(f)

agents_yaml = load_yaml_config('agents.yaml')
tasks_yaml = load_yaml_config('tasks.yaml')

all_agents = {}
for agent_conf in agents_yaml['agents']:
    agent = Agent(
        name=agent_conf['name'],
        role=agent_conf.get('role', ''),
        goal=agent_conf.get('goal', ''),
        backstory=agent_conf.get('backstory', ''),
        verbose=agent_conf.get('verbose', True),
        allow_delegation=agent_conf.get('allow_delegation', False),
        max_retry_limit=agent_conf.get('max_retry_limit', 3),
        llm=agent_conf.get('llm'),
        prompt_template=agent_conf.get('prompt_template', None)
    )
    all_agents[agent_conf['name']] = agent

all_tasks = []
for task_conf in tasks_yaml['tasks']:
    agent_name = task_conf['agent']
    agent_instance = all_agents.get(agent_name)
    if not agent_instance:
        raise ValueError(f"Agent '{agent_name}' not found for task '{task_conf['name']}'")
    task = Task(
        name=task_conf['name'],
        description=task_conf['description'],
        agent=agent_instance,
        expected_output=task_conf['expected_output'],
    )
    all_tasks.append(task)

my_crew_instance = Crew(
    agents=list(all_agents.values()),
    tasks=all_tasks,
    verbose=True
)

def process_document(pdf_path):
    print(f"Traitement du document : {pdf_path}")
    page_text = extract_text_from_pdf(pdf_path, page_number=0)  # Page 0 pour un PDF d'une page
    structure_result = my_crew_instance.kickoff(inputs={'page_text': page_text})
    print(f"Structure extraite : {structure_result}")
    # Exemple de parsing si la sortie est du texte Python
    try:
        toc = ast.literal_eval(structure_result['section_map'])
        print("Table des matières structurée :", toc)
    except Exception as e:
        print("Erreur de parsing :", e)
