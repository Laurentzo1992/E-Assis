import tempfile

from fastapi import FastAPI, File, UploadFile

from app import model

app = FastAPI(title="vision-ocr")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": model.is_model_loaded()}


@app.post("/ocr")
async def ocr(file: UploadFile = File(...)) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp_file:
        tmp_file.write(await file.read())
        tmp_file.flush()
        markdown = model.ocr_image(tmp_file.name)

    return {"markdown": markdown}
