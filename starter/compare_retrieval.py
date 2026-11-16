"""Compare retrieval and Vietnamese segmentation using one explicitly selected split."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import time
import unicodedata

from day6_retriever import read_json, write_json
from retrieval import METHODS, add_common_arguments, build_suite


def load_questions(path, split):
    raw = read_json(path)
    # Select before normalizing/validating; held-out evidence is never scored on dev.
    selected = [q for q in raw if q.get('split') == split]
    if not selected:
        raise ValueError(f'No questions for split {split}')
    questions = []
    for row in selected:
        q = dict(row)
        if q.get('answerable', True):
            gold = q.get('gold') or [{'source_id': q.get('gold_source_id'),
                    'page': q.get('gold_page'), 'evidence_quote': q.get('evidence_quote')}]
            q['gold'] = [dict(g, evidence=g.get('evidence', g.get('evidence_quote'))) for g in gold]
        questions.append(q)
    if len({q['id'] for q in questions}) != len(questions):
        raise ValueError('Question IDs must be unique')
    return questions


def metric(n, total):
    return {'n': n, 'N': total, 'rate': n / total if total else None}


def canonical(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', text)).strip()


def hit(chunk, gold):
    # Preserve the strict Day 6 single-chunk metric and its NFC/whitespace rule.
    return any(chunk['source_id'] == g['source_id'] and chunk['page'] == g['page']
               and canonical(g['evidence']) in canonical(chunk['text']) for g in gold)


def context_hit(chunks, question):
    groups = question.get('context_gold_groups')
    if groups is None:
        return any(hit(c, question['gold']) for c in chunks)
    return any(all(any(hit(c, [fragment]) for c in chunks) for fragment in group)
               for group in groups)


def validate_questions(chunks, questions):
    missing = []
    for q in questions:
        if not isinstance(q.get('answerable', True), bool):
            raise ValueError(f"answerable must be boolean for {q['id']}")
        if not isinstance(q.get('question'), str) or not q['question'].strip():
            raise ValueError(f"Invalid question {q['id']}")
        if not q.get('answerable', True):
            if not q.get('absence_reason') or q.get('expected_behavior') != 'search_and_abstain':
                raise ValueError(f"Missing unanswerable-case rationale for {q['id']}")
            continue
        if not isinstance(q.get('gold'), list) or not q['gold']:
            raise ValueError(f"Missing gold for {q['id']}")
        for g in q['gold']:
            if not isinstance(g.get('evidence'), str) or not g['evidence'].strip():
                raise ValueError(f"Missing evidence for {q['id']}")
            if not any(c['source_id'] == g.get('source_id') and c['page'] == g.get('page') for c in chunks):
                raise ValueError(f"Unknown source/page for {q['id']}")
        if not any(hit(c, q['gold']) for c in chunks):
            missing.append(q['id'])
        if 'context_gold_groups' in q:
            groups = q['context_gold_groups']
            if not isinstance(groups, list) or not groups or any(not group for group in groups):
                raise ValueError(f"Invalid context evidence groups for {q['id']}")
            if not context_hit(chunks, q):
                raise ValueError(f"Context evidence groups cannot be found in corpus for {q['id']}")
    return missing


def evaluate_method(suite, method, questions, *, top_k, budget, use_filters=False):
    traces = []
    for q in questions:
        filters = q.get('filter') if use_filters else None
        # Pass only the question and provided filter to retrieval; never gold/answer.
        try:
            t = suite.run(method, q['question'], filters=filters, top_k=top_k, budget=budget)
        except Exception as exc:
            traces.append({'query_id': q['id'], 'status': 'error', 'method': method,
                           'query': q['question'], 'error_type': type(exc).__name__, 'error': str(exc)})
            continue
        t.update(query_id=q['id'], split=q['split'], answerable=q.get('answerable', True))
        if t['answerable']:
            gold = q['gold']
            t['evaluation'] = {'hit1': any(hit(c, gold) for c in t['results'][:1]),
                               'hit3': any(hit(c, gold) for c in t['results'][:3]),
                               'hitk': any(hit(c, gold) for c in t['results']),
                               'context_hit': context_hit([c for c in t['results']
                                                  if c['id'] in t['context_ids']], q)}
        traces.append(t)
    successful = [t for t in traces if t['status'] == 'ok']
    answerable = [t for t in successful if t['answerable']]
    summary = {'method': method, 'requested': len(questions), 'successful': len(successful),
               'errors': len(traces) - len(successful),
               'answerable_requested': sum(q.get('answerable', True) for q in questions),
               'unanswerable_successful': sum(not t['answerable'] for t in successful),
               'unanswerable_requested': sum(not q.get('answerable', True) for q in questions),
               'abstention': {'status': 'not_evaluated',
                              'reason': 'Retrieval returns chunks, not agent answers. A real agent/model and reviewed refusal labels are required.'},
               'top_k': top_k, 'budget_chars': budget,
               'mean_ms': statistics.mean(t['elapsed_seconds'] * 1000 for t in successful) if successful else None,
               'service_cost_usd': 0}
    for name in ('hit1', 'hit3', 'hitk', 'context_hit'):
        summary[name] = metric(sum(t['evaluation'][name] for t in answerable), len(answerable))
    return traces, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_arguments(parser)
    parser.add_argument('--questions', type=Path, required=True)
    parser.add_argument('--split', choices=['dev', 'test'], required=True)
    parser.add_argument('--methods', nargs='+', choices=METHODS, default=list(METHODS))
    parser.add_argument('--use-question-filters', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--freeze', type=Path, help='Required for test: config/source hashes frozen after dev')
    args = parser.parse_args()
    if args.top_k < 3:
        parser.error('--top-k must be >= 3 to compare Evidence Hit@3')
    frozen = None
    if args.split == 'test':
        if not args.freeze:
            parser.error('--freeze is required before evaluating test')
        frozen = read_json(args.freeze)
        if hashlib.sha256(args.questions.read_bytes()).hexdigest() != frozen['questions_sha256']:
            raise ValueError('Questions differ from the frozen benchmark')
        for name, value in [('top_k', args.top_k), ('candidate_k', args.candidate_k),
                            ('rrf_constant', args.rrf_constant), ('budget_chars', args.budget)]:
            if frozen[name] != value:
                raise ValueError(f'{name} differs from frozen configuration')
        if args.use_question_filters:
            raise ValueError('Frozen comparison uses no filters')
        if set(args.methods) != {frozen['baseline'], frozen['selected_method']}:
            raise ValueError('Test must evaluate only baseline and the method selected on dev')
        from day6_retriever import ROOT
        if hashlib.sha256((ROOT / 'benchmark/protocol.json').read_bytes()).hexdigest() != frozen['protocol_sha256']:
            raise ValueError('Benchmark protocol changed after freeze')
        for filename, expected in frozen['source_sha256'].items():
            if hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() != expected:
                raise ValueError(f'Source changed after freeze: {filename}')
    questions = load_questions(args.questions, args.split)
    started = time.perf_counter()
    suite = build_suite(args, args.methods)
    if frozen and any(suite.identity.get(k) != v for k, v in frozen['identity'].items()):
        raise ValueError('Corpus, model or index changed after freeze')
    load_seconds = time.perf_counter() - started
    answerable = [q for q in questions if q.get('answerable', True)]
    missing_single_chunk = validate_questions(suite.chunks, questions)
    summaries = []
    all_traces = {}
    for method in args.methods:
        traces, summary = evaluate_method(suite, method, questions, top_k=args.top_k,
            budget=args.budget, use_filters=args.use_question_filters)
        write_json(args.output / f'{method}-traces.json', traces)
        summaries.append(summary)
        all_traces[method] = traces
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    segmentation = None
    if 'tfidf-syllable' in all_traces and 'tfidf-word' in all_traces:
        a = {t['query_id']: t for t in all_traces['tfidf-syllable'] if t['status'] == 'ok'}
        b = {t['query_id']: t for t in all_traces['tfidf-word'] if t['status'] == 'ok'}
        segmentation = []
        for qid in a.keys() & b.keys():
            x, y = a[qid], b[qid]
            segmentation.append({'query_id': qid, 'question': x['query'],
                'syllable_terms': x['stages']['query_terms'], 'word_terms': y['stages']['query_terms'],
                'syllable_top3': x['top3_ids'], 'word_top3': y['top3_ids'],
                'syllable_evaluation': x.get('evaluation'), 'word_evaluation': y.get('evaluation')})
        segmentation.sort(key=lambda r: r['query_id'])
        write_json(args.output / 'segmentation-comparison.json', segmentation)
    # Fingerprint selected questions only; held-out labels do not affect this report.
    fingerprint = hashlib.sha256(json.dumps(questions, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    report = {'split': args.split, 'selected_questions_sha256': fingerprint,
              'identity': suite.identity, 'load_seconds': load_seconds,
              'filter_policy': 'provided question filter' if args.use_question_filters else 'none for all methods',
              'candidate_k': args.candidate_k, 'rrf_constant': args.rrf_constant,
              'context_policy': 'ranked whole chunks, deduplicated, character budget',
              'metrics_scope': 'ranking: strict single-chunk NFC/whitespace evidence; context: all required fragments in one alternative group when provided; successful answerable questions only; negatives excluded and errors separate',
              'single_chunk_gold_coverage': metric(len(answerable) - len(missing_single_chunk), len(answerable)),
              'gold_not_wholly_in_one_chunk': missing_single_chunk,
              'coverage_policy': 'retain questions without single-chunk gold in ranking denominators as strict misses; context can satisfy explicit multi-fragment groups',
              'summaries': summaries}
    if frozen:
        report['freeze_sha256'] = hashlib.sha256(args.freeze.read_bytes()).hexdigest()
        report['test_provenance'] = frozen['test_provenance']
        report['selected_method'] = frozen['selected_method']
    write_json(args.output / 'summary.json', report)
    if any(s['errors'] for s in summaries):
        raise SystemExit('Some queries failed; inspect error traces separately.')


if __name__ == '__main__':
    main()
