"""Retrieval contracts and evaluation isolation; mocks are unit tests only."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'starter'))
from compare_retrieval import evaluate_method, load_questions, validate_questions, hit, context_hit
from hybrid_retrieval import HybridRetriever, reciprocal_rank_fusion
from lexical_retrieval import LexicalRetriever, vietnamese_words
from rerank_retrieval import LocalReranker


def chunk(cid, text, category='du_lieu', score=0.5):
    return {'id': cid, 'text': text, 'source_id': 'doc', 'source': 'doc.pdf',
            'page': 1, 'metadata': {'category': category}, 'score': score}


class LexicalTests(unittest.TestCase):
    def test_filter_before_cutoff_and_unknown_terms(self):
        index = LexicalRetriever([chunk('a', 'alpha'),
                                  chunk('b', 'alpha beta', 'giao_dich_dien_tu')])
        self.assertEqual(index.search('alpha', top_k=1)[0]['id'], 'a')
        filtered = index.search('alpha', top_k=1, filters={'category': 'giao_dich_dien_tu'})
        self.assertEqual([c['id'] for c in filtered], ['b'])
        self.assertEqual(index.search('zzzz_unknown'), [])

    def test_corpus_unicode_normalization(self):
        index = LexicalRetriever([chunk('a', 'dữ liệu')])
        import unicodedata
        self.assertEqual(index.search(unicodedata.normalize('NFD', 'dữ liệu'))[0]['id'], 'a')

    @unittest.skipUnless(importlib.util.find_spec('underthesea'), 'requires Day 7 environment')
    def test_actual_vietnamese_segmenter_joins_words(self):
        words = vietnamese_words('giao dịch điện tử và dữ liệu')
        self.assertIn('giao_dịch', words)
        self.assertIn('dữ_liệu', words)
        index = LexicalRetriever([chunk('a', 'giao dịch điện tử và dữ liệu')], 'word')
        self.assertEqual(index.search('dữ liệu')[0]['id'], 'a')


class FusionTests(unittest.TestCase):
    def test_rrf_ignores_score_scales_and_counts_each_branch_once(self):
        a, b = chunk('a', 'a', score=100), chunk('b', 'b', score=0.001)
        rows = reciprocal_rank_fusion({'dense': [a, b, a], 'lexical': [b, a]})
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0]['score'], 1/61 + 1/62)
        changed = reciprocal_rank_fusion({'dense': [dict(a, score=-1000), b], 'lexical': [b, a]})
        self.assertEqual([(r['id'], r['score']) for r in rows], [(r['id'], r['score']) for r in changed])

    def test_identical_filters_reach_both_branches(self):
        class Spy:
            def __init__(self): self.calls = []
            def search(self, query, **kwargs): self.calls.append((query, kwargs)); return []
        dense, lexical = Spy(), Spy()
        hybrid = HybridRetriever(dense, lexical, candidate_k=12)
        self.assertEqual(hybrid.search('query', filters={'category':'du_lieu'}, top_k=9), [])
        self.assertEqual(dense.calls, lexical.calls)
        self.assertEqual(dense.calls[0][1]['top_k'], 12)
        with self.assertRaises(ValueError): hybrid.search('query', top_k=13)


class RerankTests(unittest.TestCase):
    def test_rerank_changes_order_preserves_source_and_original_rank(self):
        class Model:
            def tokenizer(self, *args, **kwargs): return {'input_ids': [[1], [1,2,3,4]]}
            def predict(self, pairs, **kwargs): return [-1.0, 2.0]
        reranker = LocalReranker.__new__(LocalReranker)
        reranker.model, reranker.batch_size, reranker.max_length = Model(), 2, 3
        reranker.artifact = {'model': 'unit-test-only', 'revision': 'unit-test-only'}
        candidates = [chunk('a', 'alpha', score=.9), chunk('b', 'beta', score=.2)]
        rows, info = reranker.rerank('query', candidates, top_k=1)
        self.assertEqual(rows[0]['id'], 'b')
        self.assertEqual(rows[0]['retrieval_score'], .2)
        self.assertEqual(rows[0]['pre_rerank_rank'], 2)
        self.assertEqual(rows[0]['source'], 'doc.pdf')
        self.assertEqual(info['truncated_pairs'], 1)
        self.assertEqual(candidates[0]['score'], .9)


class EvaluationTests(unittest.TestCase):
    def test_context_requires_every_fragment_in_group(self):
        rows = [chunk('a', 'first'), chunk('b', 'second')]
        q = {'gold':[{'source_id':'doc','page':1,'evidence':'first second'}],
             'context_gold_groups': [[{'source_id':'doc','page':1,'evidence':'first'},
                                      {'source_id':'doc','page':1,'evidence':'second'}]]}
        self.assertFalse(context_hit(rows[:1], q))
        self.assertTrue(context_hit(rows, q))
        self.assertFalse(context_hit([dict(rows[0],page=2),rows[1]], q))

    def test_cross_chunk_gold_is_reported_without_dropping_question(self):
        chunks = [chunk('a', 'first'), chunk('b', 'second')]
        questions = [{'id':'q1', 'question':'q', 'gold':[
            {'source_id':'doc','page':1,'evidence':'first second'}]}]
        self.assertEqual(validate_questions(chunks, questions), ['q1'])
        self.assertFalse(any(hit(c, questions[0]['gold']) for c in chunks))
        self.assertTrue(hit(chunk('c', 'first\n\nsecond'), questions[0]['gold']))

    def test_unanswerable_and_errors_are_separate_from_quality(self):
        class Suite:
            def run(self, method, query, **kwargs):
                if query == 'error': raise RuntimeError('connection failure')
                return {'status':'ok', 'results':[chunk('a','evidence')],
                        'context_ids':['a'], 'elapsed_seconds':.001}
        cases = [{'id':'q1','split':'dev','question':'normal',
                  'gold':[{'source_id':'doc','page':1,'evidence':'evidence'}]},
                 {'id':'q2','split':'dev','question':'unknown','answerable':False},
                 {'id':'q3','split':'dev','question':'error'}]
        traces, summary = evaluate_method(Suite(), 'dense', cases, top_k=9, budget=1000)
        self.assertEqual(summary['hit3'], {'n':1,'N':1,'rate':1.0})
        self.assertEqual(summary['errors'], 1)
        self.assertEqual(summary['unanswerable_successful'], 1)
        self.assertNotIn('evaluation', traces[1])

    def test_only_selected_split_gold_is_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'questions.json'
            path.write_text(json.dumps([
                {'id':'dev','split':'dev','gold':[{'evidence_quote':'abc'}]},
                {'id':'test','split':'test','gold':'do not inspect'}]), encoding='utf-8')
            selected = load_questions(path, 'dev')
            self.assertEqual(len(selected), 1)
            self.assertEqual(selected[0]['gold'][0]['evidence'], 'abc')


if __name__ == '__main__':
    unittest.main()
