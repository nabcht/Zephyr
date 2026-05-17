"""Download the configured sentence-transformer model into the app-managed local cache.

Run once before starting μZephyr:
    python download_vector_model.py
"""

import config
from core.embedding_model import cache_embedding_model

MODEL_NAME = config.EMBEDDING_MODEL_NAME
SAVE_DIR = config.EMBEDDING_MODEL_DIR

def main() -> None:
    print(f"Downloading '{MODEL_NAME}' from Hugging Face Hub …")
    cache_embedding_model()
    print(f"Model saved to: {SAVE_DIR}")
    print("Done. You can now start μZephyr — it will load the model from disk.")

if __name__ == "__main__":
    main()
