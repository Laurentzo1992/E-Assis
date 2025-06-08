import os
from crewai_pipeline.toc_extractor import get_toc_structure
from crewai_pipeline.section_extractor import extract_all_sections
from crewai_pipeline.llm_extractor import extract_all_infos
from crewai_pipeline.data_integrator import integrate_data_to_django

PDF_PATH = "./revues/Quotidien N°4147(bis)_052521.pdf" # EDIT THIS LINE!

def run_pipeline(pdf_path):
    print(f"Processing: {pdf_path}")
    toc_structure = get_toc_structure(pdf_path)
    sections = extract_all_sections(toc_structure, pdf_path)
    infos = extract_all_infos(sections)
    integrate_data_to_django(infos)

if __name__ == "__main__":
    run_pipeline(PDF_PATH) # Pass pdf_path to run_pipeline
