"""Common interface for dense, lexical, hybrid RRF and hybrid + rerank."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time

from baseline import pack_context
from day6_retriever import DEFAULT_DAY6, DEFAULT_STORE, ROOT, Day6Retriever, read_json, write_json
from hybrid_retrieval import HybridRetriever
from lexical_retrieval import LexicalRetriever, validate_search
from rerank_retrieval import LocalReranker
from setup_retrieval import MODEL_PATH

METHODS = ('dense', 'tfidf-syllable', 'tfidf-word', 'hybrid', 'rerank')
DEFAULT_CHUNKS = ROOT / 'starter/data/day6/chunks.json'


class RetrievalSuite:
    def __init__(self, *, methods=METHODS, chunks_path=DEFAULT_CHUNKS,
                 day6_root=None, store_path=DEFAULT_STORE, candidate_k=30,
                 rrf_constant=60, reranker_path=MODEL_PATH):
        if not methods or any(m not in METHODS for m in methods):
            raise ValueError('Unknown or empty retrieval methods')
        validate_search('check', None, candidate_k)
        self.methods, self.candidate_k, self.rrf_constant = tuple(methods), candidate_k, rrf_constant
        chunk_bytes = Path(chunks_path).read_bytes()
        self.chunks = json.loads(chunk_bytes.decode('utf-8'))
        if not self.chunks or len({c['id'] for c in self.chunks}) != len(self.chunks):
            raise ValueError('Corpus must be non-empty with unique IDs')
        self.identity = {'corpus_sha256': hashlib.sha256(chunk_bytes).hexdigest(),
                         'chunk_count': len(self.chunks)}
        self.dense = self.hybrid = self.reranker = None
        self.lexical = {}
        if set(methods) & {'dense', 'hybrid', 'rerank'}:
            self.dense = Day6Retriever(day6_root, store_path)
            if sorted(self.chunks, key=lambda c: c['id']) != self.dense.export_chunks():
                raise ValueError('Lexical corpus differs from the Day 6 vector index; export chunks again.')
            self.identity.update(embedding_model=self.dense.run['model'],
                                 embedding_revision=self.dense.run['revision'],
                                 dimensions=self.dense.run['dimensions'],
                                 collection=self.dense.collection.name,
                                 index_signature=self.dense.run['signature'])
        for mode in ('syllable', 'word'):
            if f'tfidf-{mode}' in methods or (mode == 'word' and set(methods) & {'hybrid', 'rerank'}):
                self.lexical[mode] = LexicalRetriever(self.chunks, mode)
        if 'word' in self.lexical:
            self.identity['underthesea_version'] = importlib.metadata.version('underthesea')
        if set(methods) & {'hybrid', 'rerank'}:
            self.hybrid = HybridRetriever(self.dense, self.lexical['word'], candidate_k, rrf_constant)
        if 'rerank' in methods:
            self.reranker = LocalReranker(reranker_path)

    def run(self, method, query, *, filters=None, top_k=9, budget=4000):
        if method not in self.methods:
            raise ValueError('Method was not initialized')
        validate_search(query, filters, top_k)
        if not isinstance(budget, int) or budget < 1:
            raise ValueError('budget must be positive')
        if method in ('hybrid', 'rerank') and top_k > self.candidate_k:
            raise ValueError('top_k must not exceed candidate_k')
        started = time.perf_counter()
        stages = {}
        query = query.strip()
        if method == 'dense':
            results = self.dense.search(query, filters=filters, top_k=top_k)
        elif method.startswith('tfidf-'):
            mode = method.split('-')[1]
            index = self.lexical[mode]
            results = index.search(query, filters=filters, top_k=top_k)
            stages = {'query_terms': index.tokenizer(query), 'vocabulary_size': len(index.idf),
                      'segmentation': mode}
        else:
            retrieve_k = self.candidate_k if method == 'rerank' else top_k
            results, stages = self.hybrid.retrieve(query, filters=filters, top_k=retrieve_k)
            if method == 'rerank':
                stages['pre_rerank_candidates'] = results
                rerank_start = time.perf_counter()
                results, info = self.reranker.rerank(query, results, top_k=top_k)
                stages['reranker'] = dict(info, elapsed_seconds=time.perf_counter() - rerank_start)
        context, ids = pack_context(results, budget=budget)
        return {'status': 'ok', 'method': method, 'query': query, 'top_k': top_k,
                'filters': filters or None, 'filter_origin': 'provided' if filters else None,
                'identity': self.identity, 'returned_count': len(results),
                'results': [{'rank': rank, **r} for rank, r in enumerate(results, 1)],
                'top3_ids': [r['id'] for r in results[:3]], 'stages': stages,
                'context': context, 'context_ids': ids, 'context_chars': len(context),
                'budget_chars': budget, 'elapsed_seconds': time.perf_counter() - started,
                'created_at_utc': datetime.now(timezone.utc).isoformat()}


def add_common_arguments(parser):
    parser.add_argument('--chunks', type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument('--day6-root', type=Path, default=Path(os.environ.get('DAY6_ROOT', DEFAULT_DAY6)))
    parser.add_argument('--store-path', type=Path, default=DEFAULT_STORE)
    parser.add_argument('--top-k', type=int, default=9)
    parser.add_argument('--candidate-k', type=int, default=30)
    parser.add_argument('--rrf-constant', type=int, default=60)
    parser.add_argument('--budget', type=int, default=4000)
    parser.add_argument('--reranker-path', type=Path, default=MODEL_PATH)


def build_suite(args, methods):
    return RetrievalSuite(methods=methods, chunks_path=args.chunks, day6_root=args.day6_root,
                          store_path=args.store_path, candidate_k=args.candidate_k,
                          rrf_constant=args.rrf_constant, reranker_path=args.reranker_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_arguments(parser)
    parser.add_argument('--method', required=True, choices=METHODS)
    parser.add_argument('--query', required=True)
    parser.add_argument('--category', choices=['du_lieu', 'giao_dich_dien_tu'])
    parser.add_argument('--output', type=Path, default=ROOT / 'starter/results/retrieval/latest.json')
    args = parser.parse_args()
    filters = {'category': args.category} if args.category else None
    validate_search(args.query, filters, args.top_k)
    started = time.perf_counter()
    suite = build_suite(args, [args.method])
    load_seconds = time.perf_counter() - started
    trace = suite.run(args.method, args.query, filters=filters, top_k=args.top_k, budget=args.budget)
    trace['load_seconds'] = load_seconds
    write_json(args.output, trace)
    print(json.dumps(trace, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
