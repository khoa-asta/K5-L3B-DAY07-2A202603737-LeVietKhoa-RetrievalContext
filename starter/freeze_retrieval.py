"""Choose from dev and freeze a reviewable retrieval configuration before test."""
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path

from day6_retriever import ROOT, read_json, write_json


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dev-summary', type=Path, required=True)
    parser.add_argument('--questions', type=Path, default=ROOT / 'benchmark/questions.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'benchmark/frozen_retrieval.json')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Freeze exists; use a new output file for a genuinely new dev experiment.')
    protocol_path = ROOT / 'benchmark/protocol.json'
    protocol = read_json(protocol_path)
    dev = read_json(args.dev_summary)
    if dev['split'] != 'dev' or any(s['errors'] for s in dev['summaries']):
        raise ValueError('Need successful dev results before freezing')
    selected = max(dev['summaries'], key=lambda s: (s['hit3']['rate'], s['hit1']['rate'],
                                                   s['context_hit']['rate'], -s['mean_ms']))
    source_paths = sorted((ROOT / 'starter').glob('*.py'))
    freeze = {'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
        'selected_method': selected['method'], 'baseline': protocol['baseline'],
        'selection_rule': protocol['selection_rule'],
        'top_k': protocol['top_k'], 'candidate_k': protocol['candidate_k'],
        'rrf_constant': protocol['rrf_constant'], 'budget_chars': protocol['budget_chars'],
        'filter_policy': protocol['filter_policy'],
        'identity': dev['identity'], 'selected_dev_metrics': selected,
        'questions_sha256': digest(args.questions), 'protocol_sha256': digest(protocol_path),
        'dev_summary_sha256': digest(args.dev_summary),
        'source_sha256': {p.relative_to(ROOT).as_posix(): digest(p) for p in source_paths},
        'test_provenance': protocol['test_provenance'],
        'agent_model': None, 'agent_status': 'not_connected; freeze applies to retrieval only'}
    write_json(args.output, freeze)
    print(f"Frozen before test: {freeze['baseline']} + {freeze['selected_method']}")


if __name__ == '__main__':
    main()
