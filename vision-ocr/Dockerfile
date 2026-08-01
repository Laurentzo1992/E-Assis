# Pas besoin d'une image de base nvidia/cuda : le wheel torch+cu124 embarque les bibliotheques
# CUDA necessaires, et Docker Desktop (GPU passthrough) suffit pour les exposer au conteneur.
FROM python:3.11-slim

WORKDIR /app

# torch/torchvision installes a part (index CUDA dedie, pas sur PyPI standard)
RUN pip install --no-cache-dir torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
