"""Copy Day 6 assets/dependencies into Day 7 without changing the Day 6 project."""
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil

from day6_retriever import DEFAULT_DAY6, DEFAULT_STORE, ROOT, prepare_store, read_json, write_json


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def copy_verified(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and digest(target) != digest(source):
        raise ValueError(f'Existing file differs; preserved: {target}')
    if not target.exists():
        shutil.copy2(source, target)
    if digest(target) != digest(source):
        raise ValueError(f'Copy hash mismatch: {target}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--day6-root', type=Path, default=DEFAULT_DAY6)
    parser.add_argument('--copy-dependencies', action='store_true',
                        help='Copy installed libraries into the Day 7 venv, then remove its Day 6 path link')
    args = parser.parse_args()
    source_root = args.day6_root.resolve()
    source_model = source_root / 'starter/.models/paraphrase-multilingual-MiniLM-L12-v2'
    target_model = ROOT / 'starter/.models' / source_model.name
    copied = {}
    for source in source_model.rglob('*'):
        if source.is_file() and '.cache' not in source.parts:
            relative = source.relative_to(source_model)
            target = target_model / relative
            copy_verified(source, target)
            copied[str(relative).replace('\\', '/')] = digest(target)
    if 'model.safetensors' not in copied:
        raise FileNotFoundError('Source Day 6 embedding weights are missing')
    store_status = prepare_store(source_root, DEFAULT_STORE)
    # Carry source material for local verification; preserve source paths in chunk metadata.
    manifest = read_json(source_root / 'data/manifest.json')
    for document in manifest['documents']:
        source = source_root / document['source_path']
        target = ROOT / document['source_path']
        copy_verified(source, target)
    copy_verified(source_root / 'data/manifest.json', ROOT / 'data/day6_manifest.json')
    for name in ('pages.jsonl',):
        copy_verified(source_root / 'results/baseline' / name, ROOT / 'starter/data/day6' / name)
    copy_verified(source_root / 'benchmark/questions.json', ROOT / 'starter/data/day6/original_questions.json')
    package_count = 0
    if args.copy_dependencies:
        source_sites = source_root / 'starter/.venv/Lib/site-packages'
        target_sites = (ROOT / '.venv/Lib/site-packages').resolve()
        if not target_sites.is_dir() or not target_sites.is_relative_to(ROOT.resolve()):
            raise ValueError('Expected an existing Day 7 venv inside the workspace')
        for source in source_sites.iterdir():
            if source.name == '__pycache__':
                continue
            target = target_sites / source.name
            # Preserve packages already installed in Day 7 (including Underthesea).
            if target.exists():
                continue
            if source.is_dir():
                shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            else:
                shutil.copy2(source, target)
            package_count += 1
        link = target_sites / 'day6_dependencies.pth'
        if link.exists():
            link.unlink()
    report = {'imported_at_utc': datetime.now(timezone.utc).isoformat(),
              'source': str(source_root), 'embedding_model_path': str(target_model),
              'store_path': str(DEFAULT_STORE), 'store_status': store_status,
              'embedding_sha256': copied, 'dependency_entries_copied': package_count,
              'day6_path_link_removed': not (ROOT / '.venv/Lib/site-packages/day6_dependencies.pth').exists(),
              'source_documents': [{'path': d['source_path'], 'sha256': d['sha256']} for d in manifest['documents']]}
    write_json(ROOT / 'starter/results/local-assets-import.json', report)
    print(f'Embedding copied and verified: {target_model}', flush=True)
    print(f'Chroma snapshot: {store_status}; dependency entries copied: {package_count}', flush=True)


if __name__ == '__main__':
    main()
