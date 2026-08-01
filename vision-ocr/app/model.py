"""Chargement et inference DeepSeek-OCR (fallback vision pour pages scannees/images).

attention "eager" (pas flash-attn) : evite une compilation de flash-attn longue et fragile
(necessite nvcc + versions torch/cuda/python exactement alignees), sans impact constate sur la
qualite du resultat - pattern repris tel quel du service vision-ocr de fasofoodalert-core, deja
valide en conditions reelles.
"""

import tempfile
from pathlib import Path
from threading import Lock

import torch
from transformers import AutoModel, AutoTokenizer

MODEL_NAME = "deepseek-ai/DeepSeek-OCR"
DEFAULT_PROMPT = "<image>\n<|grounding|>Convert the document to markdown. "

_model = None
_tokenizer = None
_load_lock = Lock()


def _ensure_model_loaded() -> None:
    global _model, _tokenizer
    if _model is not None:
        return

    with _load_lock:
        if _model is not None:  # un autre thread a pu charger pendant l'attente du verrou
            return

        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
        model = AutoModel.from_pretrained(
            MODEL_NAME,
            _attn_implementation="eager",
            trust_remote_code=True,
            use_safetensors=True,
        )
        model = model.eval().cuda().to(torch.bfloat16)

        _tokenizer = tokenizer
        _model = model


def is_model_loaded() -> bool:
    return _model is not None


def ocr_image(image_path: str, prompt: str = DEFAULT_PROMPT) -> str:
    """Convertit une image de page en texte structure (markdown). Charge le modele au premier appel."""
    _ensure_model_loaded()

    with tempfile.TemporaryDirectory() as output_dir:
        _model.infer(
            _tokenizer,
            prompt=prompt,
            image_file=image_path,
            output_path=output_dir,
            base_size=1024,
            image_size=640,
            crop_mode=True,
            save_results=True,
        )
        result_path = Path(output_dir) / "result.mmd"
        return result_path.read_text(encoding="utf-8") if result_path.exists() else ""
