import sys
import os

# Add the project root (~/E-Assis) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()



from collect.src.collect.tools.pdf_utils import extract_text_from_pdf

from src.collect.crew import process_page_with_crewai
from src.collect.tools.django_mapper import save_extracted_data

# Path to a sample processed PDF page
sample_page = "src/collect/data/processed/Quotidien%204157/page_10.pdf"

# 1. Extract text
page_text = extract_text_from_pdf(sample_page)

# 2. Process with CrewAI agent
informations = process_page_with_crewai(page_text)
print("Extracted info:", informations)

# 3. Save to Django models
result = save_extracted_data(informations)
print("Saved result:", result)
