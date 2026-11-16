"""Create a local Day 7 environment and explicitly download reranker artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = 'cross-encoder/mmarco-mMiniLMv2-L12-H384-v1'
MODEL_REVISION = '1427fd652930e4ba29e8149678df786c240d8825'
MODEL_PATH = ROOT / 'starter/.models/mmarco-mMiniLMv2-L12-H384-v1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-model', action='store_true')
    parser.add_argument('--skip-install', action='store_true')
    args = parser.parse_args()
    env = ROOT / '.venv'
    python = env / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        venv.create(env, with_pip=True)
    # Dependencies are installed into Day 7; no Day 6 .pth path is created.
    if not args.skip_install:
        subprocess.run([str(python), '-m', 'pip', 'install', '--cache-dir',
                        str(ROOT / 'starter/.cache/pip'), '-r',
                        str(ROOT / 'starter/requirements-retrieval.txt')], check=True)
    if not args.skip_model:
        os.environ['HF_HOME'] = str(ROOT / 'starter/.cache/huggingface')
        os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
        os.environ.pop('HF_HUB_OFFLINE', None)
        from huggingface_hub import snapshot_download
        manifest_path = MODEL_PATH / 'artifact.json'
        revision = MODEL_REVISION
        snapshot_download(MODEL_ID, revision=revision, local_dir=str(MODEL_PATH),
                          allow_patterns=['config.json', 'model.safetensors', 'tokenizer.json',
                                          'tokenizer_config.json', 'special_tokens_map.json',
                                          'sentencepiece.bpe.model', 'README.md'], max_workers=3)
        hashes = {}
        for path in MODEL_PATH.iterdir():
            if path.is_file() and path.name != 'artifact.json':
                with path.open('rb') as stream:
                    hashes[path.name] = hashlib.file_digest(stream, 'sha256').hexdigest()
        manifest_path.write_text(json.dumps({'model': MODEL_ID, 'revision': revision,
                                            'sha256': hashes}, indent=2) + '\n', encoding='utf-8')
    subprocess.run([str(python), '-m', 'pip', 'check'], check=True)
    print(f'Day 7 Python: {python}')


if __name__ == '__main__':
    main()
