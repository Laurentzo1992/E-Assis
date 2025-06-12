import sys
import os

# Add the project root (~/E-Assis) to sys.path
# This is crucial for absolute imports like 'backend.settings' and 'collect.src.collect.crew'
# os.path.dirname(__file__) is /home/ye/E-Assis/collect/src/collect
# '../../../..' moves up four levels to /home/ye/E-Assis
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

# Set the correct Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

# Now import the crew instance or the processing function from crew.py
# (assuming crew.py defines 'my_crew_instance' or 'process_document')
from collect.src.collect.crew import my_crew_instance, process_document

# Define your data directory (adjust if necessary)
PROCESSED_PDF_DIR = "collect/src/collect/data/processed"

if __name__ == "__main__":
    print("Django setup complete.")
    print("Attempting to initialize CrewAI crew...")
    # The crew is already initialized when my_crew_instance is imported
    print("CrewAI crew initialized.")

    # Example: Process one document (replace with your actual document loop)
    sample_doc_path = os.path.join(PROCESSED_PDF_DIR, "Quotidien%204157", "page_1.pdf")
    if os.path.exists(sample_doc_path):
        # Call the processing function defined in crew.py
        process_document(sample_doc_path)
    else:
        print(f"Sample document not found: {sample_doc_path}")
        print("Please ensure your 'data/processed' directory contains valid PDF subfolders.")

    print("Main execution finished.")

