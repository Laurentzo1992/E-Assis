import os
from PyPDF2 import PdfReader

class PDFExtractor:
    def __init__(self, folder, output_folder='./extracts/extracted_text'):
        self.folder = folder
        self.output_folder = output_folder
        os.makedirs(self.output_folder, exist_ok=True)

    def extract_text_from_file(self, file_path):
        reader = PdfReader(file_path)
        text = ''
        for page in reader.pages:
            text += page.extract_text() or ''
        return text

    def extract_all(self):
        files = [f for f in os.listdir(self.folder) if f.endswith('.pdf')]
        for file in files:
            file_path = os.path.join(self.folder, file)
            print(f"Extraction du texte de : {file_path}")
            text = self.extract_text_from_file(file_path)
            
            # Sauvegarder dans un fichier .txt
            output_file = os.path.join(self.output_folder, file.replace('.pdf', '.txt'))
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(text)
            
            print(f"Texte sauvegardé dans : {output_file}")

