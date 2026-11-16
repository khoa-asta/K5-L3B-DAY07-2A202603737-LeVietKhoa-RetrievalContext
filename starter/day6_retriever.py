"""Query Day 6's index using embedding weights and Chroma now stored in Day 7."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DAY6 = ROOT.parents[1] / 'Lab6/K5-L3B-Day06-2A202603737-DataIngestion'
DEFAULT_STORE = ROOT / 'starter/data/day6/chroma'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def prepare_store(day6_root, store_path):
    """Copy once or reuse a matching snapshot; never overwrite existing data."""
    source = day6_root / 'starter/.chroma'
    if store_path.resolve() == source.resolve():
        raise ValueError('Use a Day 7 snapshot to preserve the original Day 6 store.')
    if not (source / 'chroma.sqlite3').is_file():
        raise FileNotFoundError(f'Missing Day 6 store: {source}')
    if store_path.exists():
        required = ('chroma.sqlite3', 'run.json', 'strategy_stats.json')
        missing = [name for name in required if not (store_path / name).is_file()]
        if missing:
            raise ValueError(f'Incomplete snapshot at {store_path}: missing {", ".join(missing)}. '
                             'Use --store-path with a new directory to prepare a fresh snapshot.')
        saved = read_json(store_path / 'run.json')
        current = read_json(day6_root / 'results/baseline/run.json')
        identity = ('signature', 'model', 'revision', 'dimensions', 'collections',
                    'metric', 'normalization', 'status', 'selected_on_dev')
        if any(saved.get(key) != current.get(key) for key in identity):
            raise ValueError('Existing snapshot differs from the Day 6 run. '
                             'Use --store-path with a new directory to prepare a fresh snapshot.')
        # Day6Retriever subsequently checks the actual collection and embedding.
        return 'reused'
    # SQLite backup includes committed WAL data without opening Chroma on Day 6.
    shutil.copytree(source, store_path,
                    ignore=shutil.ignore_patterns('chroma.sqlite3*'))
    with closing(sqlite3.connect((source / 'chroma.sqlite3').as_uri() + '?mode=ro', uri=True)) as src:
        with closing(sqlite3.connect(store_path / 'chroma.sqlite3')) as dst:
            src.backup(dst)
    for name in ('run.json', 'strategy_stats.json'):
        shutil.copy2(day6_root / 'results/baseline' / name, store_path / name)
    return 'created'


class Day6Retriever:
    """Implements agentic.Retriever with the original cosine dense index."""

    def __init__(self, day6_root=None, store_path=DEFAULT_STORE, strategy=None):
        self.day6_root = Path(day6_root or os.environ.get('DAY6_ROOT', DEFAULT_DAY6)).resolve()
        self.store_path = Path(store_path).resolve()
        if not (self.store_path / 'chroma.sqlite3').is_file():
            raise FileNotFoundError('Missing snapshot. Run starter/day6_retriever.py --prepare first.')
        if self.store_path == self.day6_root / 'starter/.chroma':
            raise ValueError('Use a Day 7 snapshot to preserve the original Day 6 store.')
        self.run = read_json(self.store_path / 'run.json')
        stats = read_json(self.store_path / 'strategy_stats.json')
        if self.run['status'] != 'success' or self.run['metric'] != 'cosine':
            raise ValueError('Expected a successful Day 6 cosine index.')
        self.strategy = strategy or self.run['selected_on_dev']
        if self.strategy not in self.run['collections']:
            raise ValueError('Unknown Day 6 strategy.')

        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        os.environ['ANONYMIZED_TELEMETRY'] = 'False'
        # Model files and encoding implementation now live entirely in Day 7.
        from local_embeddings import LocalEmbedder
        self.embedder = LocalEmbedder()
        if (self.embedder.model_name != self.run['model']
                or self.embedder.revision != self.run['revision']
                or self.embedder.dimensions != self.run['dimensions']):
            raise ValueError('Day 6 embedding model/revision/dimensions do not match the snapshot.')

        import chromadb
        from chromadb.config import Settings
        self.client = chromadb.PersistentClient(path=str(self.store_path),
                                               settings=Settings(anonymized_telemetry=False))
        self.collection = self.client.get_collection(
            name=self.run['collections'][self.strategy], embedding_function=None)
        self.count = self.collection.count()
        if self.count != stats[self.strategy]['chunk_count'] or self.count < 1:
            raise ValueError('Snapshot chunk count does not match Day 6 run metadata.')
        sample = self.collection.get(limit=1, include=['embeddings'])
        if len(sample['embeddings'][0]) != self.embedder.dimensions:
            raise ValueError('Stored embedding dimension mismatch.')

    @staticmethod
    def _chunk(chunk_id, text, metadata):
        return {'id': chunk_id, 'text': text, 'source_id': metadata['document_id'],
                'source': metadata['source'], 'page': metadata['page'], 'metadata': metadata}

    def search(self, query, *, filters=None, top_k=3):
        if not isinstance(query, str) or not query.strip():
            raise ValueError('query must be non-empty text')
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise ValueError('top_k must be a positive integer')
        if filters and (set(filters) != {'category'} or
                        filters['category'] not in ('du_lieu', 'giao_dich_dien_tu')):
            raise ValueError('Supported filter: category = du_lieu or giao_dich_dien_tu')
        vector = self.embedder.embed_query(query.strip())
        result = self.collection.query(query_embeddings=[vector],
            n_results=min(top_k, self.count), where=filters or None,
            include=['documents', 'metadatas', 'distances'])
        return [{**self._chunk(cid, text, meta), 'score': 1 - distance, 'distance': distance}
                for cid, text, meta, distance in zip(result['ids'][0], result['documents'][0],
                    result['metadatas'][0], result['distances'][0])]

    def export_chunks(self):
        result = self.collection.get(include=['documents', 'metadatas'])
        return sorted([self._chunk(cid, text, meta) for cid, text, meta in
                       zip(result['ids'], result['documents'], result['metadatas'])],
                      key=lambda chunk: chunk['id'])


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Connect Day 7 to local Day 6 embeddings and Chroma')
    parser.add_argument('--day6-root', type=Path, default=Path(os.environ.get('DAY6_ROOT', DEFAULT_DAY6)))
    parser.add_argument('--store-path', type=Path, default=DEFAULT_STORE)
    parser.add_argument('--strategy', choices=['A', 'B', 'C'])
    parser.add_argument('--prepare', action='store_true', help='Copy Day 6 store or reuse a matching snapshot (stop ingestion before copying)')
    parser.add_argument('--query')
    parser.add_argument('--category', choices=['du_lieu', 'giao_dich_dien_tu'])
    parser.add_argument('--top-k', type=int, default=3)
    parser.add_argument('--export-chunks', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    preparation = None
    if args.prepare:
        preparation = prepare_store(args.day6_root.resolve(), args.store_path.resolve())
    retriever = Day6Retriever(args.day6_root, args.store_path, args.strategy)
    result = {'status': 'connected', 'day6_root': str(retriever.day6_root),
              'store_path': str(retriever.store_path), 'model': retriever.run['model'],
              'model_path': str(ROOT / 'starter/.models/paraphrase-multilingual-MiniLM-L12-v2'),
              'revision': retriever.run['revision'], 'dimensions': retriever.embedder.dimensions,
              'collection': retriever.collection.name, 'chunk_count': retriever.count,
              'strategy': retriever.strategy}
    if preparation:
        result['preparation'] = preparation
    if args.query:
        filters = {'category': args.category} if args.category else None
        result.update(query=args.query, filters=filters,
                      results=retriever.search(args.query, filters=filters, top_k=args.top_k))
    if args.export_chunks:
        write_json(args.export_chunks, retriever.export_chunks())
    if args.output:
        write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
