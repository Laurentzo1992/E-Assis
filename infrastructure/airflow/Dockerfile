FROM apache/airflow:2.9.3

COPY infrastructure/airflow/requirements-airflow.txt /requirements-airflow.txt
RUN pip install --no-cache-dir -r /requirements-airflow.txt

# Provider Docker : permet au DAG de lancer kbbot-ingest via DockerOperator dans son propre
# conteneur (poids ML - torch/sentence-transformers/pymupdf - qu'on ne veut pas dans cette image
# Airflow, risque de conflit de dependances avec Airflow lui-meme).
RUN pip install --no-cache-dir apache-airflow-providers-docker==3.12.2 \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.9.3/constraints-3.12.txt"
