"""Install PDF inspection tools and explicitly download a local answering model."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = 'Qwen/Qwen3-0.6B'
MODEL_PATH = ROOT / 'starter/.models/Qwen3-0.6B'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-agent', action='store_true')
    parser.add_argument('--skip-install', action='store_true')
    args = parser.parse_args()
    if not args.skip_install:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--cache-dir',
                        str(ROOT / 'starter/.cache/pip'), 'PyMuPDF>=1.26,<1.28',
                        'Pillow>=12,<13', 'fonttools>=4.60'], check=True)
    if not args.skip_agent:
        os.environ['HF_HOME'] = str(ROOT / 'starter/.cache/huggingface')
        os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
        os.environ.pop('HF_HUB_OFFLINE', None)
        from huggingface_hub import HfApi, snapshot_download
        manifest_path = MODEL_PATH / 'artifact.json'
        revision = (json.loads(manifest_path.read_text(encoding='utf-8'))['revision']
                    if manifest_path.exists() else HfApi().model_info(MODEL_ID).sha)
        snapshot_download(MODEL_ID, revision=revision, local_dir=str(MODEL_PATH),
            allow_patterns=['config.json', 'generation_config.json', 'model.safetensors',
                            'tokenizer.json', 'tokenizer_config.json', 'vocab.json',
                            'merges.txt', 'README.md', 'LICENSE'], max_workers=3)
        hashes = {}
        for p in MODEL_PATH.iterdir():
            if p.is_file() and p.name != 'artifact.json':
                with p.open('rb') as stream:
                    hashes[p.name] = hashlib.file_digest(stream, 'sha256').hexdigest()
        manifest_path.write_text(json.dumps({'model': MODEL_ID, 'revision': revision,
                                             'sha256': hashes}, indent=2)+'\n', encoding='utf-8')
    versions = {name: importlib.metadata.version(name) for name in
                ('PyMuPDF','Pillow','fonttools','transformers','torch','sentence-transformers','chromadb')}
    (ROOT / 'advanced/environment.json').write_text(json.dumps(versions,indent=2)+'\n',encoding='utf-8')
    subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True)


if __name__ == '__main__':
    main()
