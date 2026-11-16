"""Day 7 offline embedder, preserving the Day 6 model/revision/encoding policy."""
from pathlib import Path

import torch
from sentence_transformers import SentenceTransformer

MODEL_NAME = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
MODEL_REVISION = 'e8f8c211226b894fcb81acc59f3b34ba3efd5f42'
MODEL_PATH = Path(__file__).resolve().parent / '.models' / MODEL_NAME.split('/')[-1]


class LocalEmbedder:
    model_name = MODEL_NAME
    revision = MODEL_REVISION

    def __init__(self, model_path=MODEL_PATH, batch_size=8, cpu_threads=2):
        if batch_size < 1 or cpu_threads < 1:
            raise ValueError('batch_size and cpu_threads must be positive')
        path = Path(model_path)
        if not (path / 'model.safetensors').is_file():
            raise FileNotFoundError('Missing Day 7 embedding model. Run starter/import_day6_assets.py first.')
        torch.set_num_threads(cpu_threads)
        self.batch_size = batch_size
        self.model = SentenceTransformer(str(path), device='cpu', local_files_only=True,
                                         trust_remote_code=False)
        self.dimensions = self.model.get_embedding_dimension()
        self.max_tokens = self.model.max_seq_length

    def embed_documents(self, texts):
        if not texts:
            return []
        for index, text in enumerate(texts):
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f'Input {index} must be non-empty text')
            tokens = self.model.tokenizer(text, truncation=False, add_special_tokens=True,
                                          verbose=False)['input_ids']
            if len(tokens) > self.max_tokens:
                raise ValueError(f'Input {index}: {len(tokens)} tokens exceeds {self.max_tokens}; '
                                 'split into smaller chunks before embedding.')
        return self.model.encode(texts, batch_size=self.batch_size,
                                 normalize_embeddings=True, convert_to_numpy=True,
                                 show_progress_bar=False).tolist()

    def embed_query(self, question):
        return self.embed_documents([question])[0]
