import pdfplumber

def extract_section(pdf_path, start, end):
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for i in range(start - 1, end):  # 0-based indexing
            text += pdf.pages[i].extract_text() or ""
        return text

def extract_all_sections(toc_structure, pdf_path):
    import json
    if isinstance(toc_structure, str):
        toc_structure = json.loads(toc_structure)
    sections = []
    for section in toc_structure:
        text = extract_section(pdf_path, section['page_debut'], section['page_fin'])
        sections.append({
            "titre": section['titre'],
            "text": text,
            "page_debut": section['page_debut'],
            "page_fin": section['page_fin'],
            "sous_sections": section.get('sous_sections', [])
        })
    return sections
