"""Check the published Day 7 split and absent-evidence label contract."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BenchmarkContractTests(unittest.TestCase):
    def setUp(self):
        self.questions = json.loads((ROOT / 'benchmark/questions.json').read_text(encoding='utf-8'))

    def test_requested_split_counts_and_unique_ids(self):
        self.assertEqual(len({q['id'] for q in self.questions}), 27)
        for split, answerable, count in [('dev',True,15),('dev',False,5),
                                         ('test',True,5),('test',False,2)]:
            self.assertEqual(sum(q['split']==split and q['answerable']==answerable for q in self.questions),count)

    def test_negative_labels_have_full_corpus_audits_and_no_gold(self):
        audits = json.loads((ROOT / 'benchmark/absence_review.json').read_text(encoding='utf-8'))
        reviews = {r['id']:r for r in audits['reviews']}
        for q in self.questions:
            if q['answerable']: continue
            self.assertEqual(q['expected_behavior'], 'search_and_abstain')
            self.assertTrue(q['absence_reason'])
            self.assertNotIn('gold', q)
            review = reviews[q['absence_review_id']]
            self.assertEqual(len(review['scope']),49)
            self.assertFalse(review['human_confirmed'])
            self.assertTrue(review['related_pages_reviewed'])

    def test_multi_fragment_context_preserves_original_ranking_gold(self):
        q = next(q for q in self.questions if q['id']=='Q07')
        self.assertEqual(len(q['gold']),1)
        self.assertEqual(len(q['context_gold_groups'][0]),2)
        for fragment in q['context_gold_groups'][0]:
            self.assertIn(fragment['evidence'],q['gold'][0]['evidence'])


if __name__ == '__main__':
    unittest.main()
