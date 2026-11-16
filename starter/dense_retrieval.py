"""Day 7 dense retrieval: local query embedding, cosine search, metadata filter."""
import argparse
import json
import os
from pathlib import Path
import time

from day6_retriever import DEFAULT_DAY6, DEFAULT_STORE, ROOT, Day6Retriever, write_json

DEFAULT_TOP_K = 9


def run_dense(retriever, query, *, top_k=DEFAULT_TOP_K, category=None):
    """Return a ranked retrieval trace; category comes explicitly from the user."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError('query must be non-empty text')
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise ValueError('top_k must be a positive integer')
    if category is not None and category not in ('du_lieu', 'giao_dich_dien_tu'):
        raise ValueError('category must be du_lieu or giao_dich_dien_tu')
    filters = {'category': category} if category is not None else None
    started = time.perf_counter()
    hits = retriever.search(query.strip(), filters=filters, top_k=top_k)
    elapsed = time.perf_counter() - started
    return {
        'method': 'dense', 'query': query.strip(), 'top_k': top_k,
        'filters': filters, 'filter_origin': 'user' if filters else None,
        'day6_strategy': retriever.strategy,
        'model': retriever.run['model'], 'revision': retriever.run['revision'],
        'dimensions': retriever.embedder.dimensions,
        'normalization': retriever.run['normalization'],
        'metric': retriever.run['metric'], 'index_signature': retriever.run['signature'],
        'collection': retriever.collection.name, 'store_path': str(retriever.store_path),
        'index_chunk_count': retriever.count,
        'retrieval_seconds': elapsed, 'returned_count': len(hits),
        'top3_ids': [hit['id'] for hit in hits[:3]],
        'results': [{'rank': rank, **hit} for rank, hit in enumerate(hits, 1)],
    }


def main():
    parser = argparse.ArgumentParser(description='Day 7 dense retrieval, default top-k=9')
    parser.add_argument('--query', required=True)
    parser.add_argument('--top-k', type=int, default=DEFAULT_TOP_K)
    parser.add_argument('--category', choices=['du_lieu', 'giao_dich_dien_tu'])
    parser.add_argument('--day6-root', type=Path, default=Path(os.environ.get('DAY6_ROOT', DEFAULT_DAY6)))
    parser.add_argument('--store-path', type=Path, default=DEFAULT_STORE)
    parser.add_argument('--strategy', choices=['A', 'B', 'C'])
    parser.add_argument('--output', type=Path, default=ROOT / 'starter/results/dense/latest.json')
    args = parser.parse_args()
    if not args.query.strip() or args.top_k < 1:
        parser.error('--query must be non-empty and --top-k must be positive')
    started = time.perf_counter()
    retriever = Day6Retriever(args.day6_root, args.store_path, args.strategy)
    model_and_index_load_seconds = time.perf_counter() - started
    trace = run_dense(retriever, args.query, top_k=args.top_k, category=args.category)
    trace['model_and_index_load_seconds'] = model_and_index_load_seconds
    write_json(args.output, trace)
    print(json.dumps(trace, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
