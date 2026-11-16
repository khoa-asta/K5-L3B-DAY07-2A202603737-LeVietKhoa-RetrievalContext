"""Dense + lexical reciprocal rank fusion (RRF), without adding raw scores."""
from lexical_retrieval import validate_search


def reciprocal_rank_fusion(branches, constant=60):
    if not isinstance(constant, int) or isinstance(constant, bool) or constant < 1:
        raise ValueError('RRF constant must be a positive integer')
    combined = {}
    for branch, rows in branches.items():
        seen = set()
        for rank, row in enumerate(rows, 1):
            cid = row['id']
            if cid in seen:
                continue
            seen.add(cid)
            if cid not in combined:
                combined[cid] = {k: v for k, v in row.items()
                                 if k not in ('score', 'distance', 'strategy', 'rank')}
                combined[cid].update(score=0.0, branch_ranks={}, branch_scores={})
            item = combined[cid]
            item['score'] += 1 / (constant + rank)
            item['branch_ranks'][branch] = rank
            item['branch_scores'][branch] = row['score']
    return sorted(combined.values(), key=lambda r: (-r['score'], r['id']))


class HybridRetriever:
    def __init__(self, dense, lexical, candidate_k=30, rrf_constant=60):
        validate_search('check', None, candidate_k)
        if not isinstance(rrf_constant, int) or isinstance(rrf_constant, bool) or rrf_constant < 1:
            raise ValueError('RRF constant must be a positive integer')
        self.dense, self.lexical = dense, lexical
        self.candidate_k, self.rrf_constant = candidate_k, rrf_constant

    def retrieve(self, query, *, filters=None, top_k=9):
        validate_search(query, filters, top_k)
        if top_k > self.candidate_k:
            raise ValueError('top_k must not exceed candidate_k')
        branches = {'dense': self.dense.search(query, filters=filters, top_k=self.candidate_k),
                    'lexical': self.lexical.search(query, filters=filters, top_k=self.candidate_k)}
        fused = reciprocal_rank_fusion(branches, self.rrf_constant)
        return fused[:top_k], {'branches': branches, 'fused_candidates': fused,
                              'candidate_k_per_branch': self.candidate_k,
                              'rrf_constant': self.rrf_constant}

    def search(self, query, *, filters=None, top_k=9):
        return self.retrieve(query, filters=filters, top_k=top_k)[0]
