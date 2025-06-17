import sys
import os

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(PROJECT_ROOT)

# Set Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

# Import CrewAI pipeline
from collect.src.collect.crew import my_crew_instance, process_document

# Define your data directory
PROCESSED_PDF_DIR = os.path.join(PROJECT_ROOT, "collect", "src", "collect", "data", "processed")

if __name__ == "__main__":
    print("Django setup complete.")
    print("Attempting to initialize CrewAI crew...")
    print("CrewAI crew initialized.")

    # Example: Process one document
    sample_doc_path = os.path.join(
        PROCESSED_PDF_DIR, "Quotidien%20N%C2%B04149-4150", "page_1.pdf"
    )
    if os.path.exists(sample_doc_path):
        process_document(sample_doc_path)
    else:
        print(f"Sample document not found: {sample_doc_path}")
        print("Please ensure your 'data/processed' directory contains valid PDF subfolders.")

    print("Main execution finished.")
