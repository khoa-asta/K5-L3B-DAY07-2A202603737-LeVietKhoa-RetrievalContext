"""TF-IDF ablation: identical weighting, syllables versus Vietnamese words."""
import re
import unicodedata

from baseline import TfidfIndex, tokenize


def validate_search(query, filters, top_k):
    if not isinstance(query, str) or not query.strip():
        raise ValueError('query must be non-empty text')
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise ValueError('top_k must be a positive integer')
    if filters is not None and (not isinstance(filters, dict) or
        (filters and (set(filters) != {'category'} or
                      filters['category'] not in ('du_lieu', 'giao_dich_dien_tu')))):
        raise ValueError('Supported filter: category = du_lieu or giao_dich_dien_tu')


def vietnamese_words(text):
    # Keep the segmenter's original case input; normalize output for retrieval.
    from underthesea import word_tokenize
    normalized = unicodedata.normalize('NFC', text)
    segmented = word_tokenize(normalized, format='text')
    return re.findall(r'\w+', segmented.casefold())


class LexicalRetriever(TfidfIndex):
    def __init__(self, chunks, segmentation='syllable'):
        if segmentation not in ('syllable', 'word'):
            raise ValueError('segmentation must be syllable or word')
        if not chunks or len({c['id'] for c in chunks}) != len(chunks):
            raise ValueError('chunks must be non-empty with unique IDs')
        self.segmentation = segmentation
        super().__init__(chunks, tokenizer=tokenize if segmentation == 'syllable' else vietnamese_words)

    def search(self, query, *, filters=None, top_k=9):
        validate_search(query, filters, top_k)
        # Fit IDF on the same full corpus for both modes, then rank eligible rows.
        rows = super().search(query, top_k=len(self.chunks))
        if filters:
            rows = [r for r in rows if r['metadata'].get('category') == filters['category']]
        return [{**r, 'strategy': f'tfidf-{self.segmentation}'} for r in rows[:top_k]]
