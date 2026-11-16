"""Local multilingual CrossEncoder reranking of genuine retrieval candidates."""
import json
import math
from pathlib import Path

from lexical_retrieval import validate_search
from setup_retrieval import MODEL_ID, MODEL_PATH, MODEL_REVISION


class LocalReranker:
    def __init__(self, model_path=MODEL_PATH, batch_size=8, max_length=512):
        path = Path(model_path)
        if not (path / 'model.safetensors').is_file() or not (path / 'artifact.json').is_file():
            raise FileNotFoundError('Missing reranker. Run starter/setup_retrieval.py with Day 6 Python first.')
        self.artifact = json.loads((path / 'artifact.json').read_text(encoding='utf-8'))
        if self.artifact['model'] != MODEL_ID or self.artifact['revision'] != MODEL_REVISION:
            raise ValueError('Unexpected reranker model/revision')
        import torch
        from sentence_transformers import CrossEncoder
        torch.set_num_threads(2)
        self.model = CrossEncoder(str(path), device='cpu', local_files_only=True,
                                  trust_remote_code=False, max_length=max_length,
                                  activation_fn=torch.nn.Identity())
        self.batch_size, self.max_length = batch_size, max_length

    def rerank(self, query, candidates, *, top_k=9):
        validate_search(query, None, top_k)
        if not candidates:
            return [], {'truncated_pairs': 0}
        if len({c['id'] for c in candidates}) != len(candidates):
            raise ValueError('Reranker candidates must have unique IDs')
        pairs = [(query, c['text']) for c in candidates]
        tokenized = self.model.tokenizer([p[0] for p in pairs], [p[1] for p in pairs],
                                         truncation=False, verbose=False)['input_ids']
        truncated = sum(len(ids) > self.max_length for ids in tokenized)
        scores = self.model.predict(pairs, batch_size=self.batch_size, show_progress_bar=False)
        if len(scores) != len(candidates):
            raise ValueError('Reranker returned an incorrect number of scores')
        rows = []
        for rank, (candidate, raw_score) in enumerate(zip(candidates, scores), 1):
            score = float(raw_score)
            if not math.isfinite(score):
                raise ValueError('Non-finite CrossEncoder score')
            rows.append({**candidate, 'retrieval_score': candidate['score'],
                         'pre_rerank_rank': rank, 'score': score})
        rows.sort(key=lambda r: (-r['score'], r['id']))
        return rows[:top_k], {'model': self.artifact['model'], 'revision': self.artifact['revision'],
                             'score_type': 'cross_encoder_logit', 'max_length': self.max_length,
                             'truncation': 'model tokenizer longest_first', 'truncated_pairs': truncated,
                             'candidate_count': len(candidates)}
