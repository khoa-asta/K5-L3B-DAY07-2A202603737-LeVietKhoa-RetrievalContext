"""Build 15+5 dev / 5+2 test cases, with a full-corpus absence-review record."""
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from day6_retriever import DEFAULT_DAY6, ROOT, read_json, write_json

NEGATIVES = [
    ('UDEV01', 'dev',
     'Lệ phí cấp mới giấy phép kinh doanh dịch vụ tin cậy là bao nhiêu đồng?',
     'Thiếu mức tiền cụ thể; quy định về cấp phép, công khai chi phí và dẫn chiếu pháp luật phí không cung cấp biểu lệ phí cấp mới.',
     ['lệ phí', 'chi phí', 'giấy phép'], [('gddt', 14), ('gddt', 15), ('gddt', 25), ('dulieu', 20)]),
    ('UDEV02', 'dev',
     'Chữ ký số theo Luật Giao dịch điện tử bắt buộc dùng khóa RSA tối thiểu bao nhiêu bit?',
     'Có định nghĩa chữ ký số và yêu cầu an toàn/tiêu chuẩn, nhưng không có tham số RSA hoặc độ dài khóa tối thiểu.',
     ['RSA', 'thuật toán', 'khóa', 'tiêu chuẩn'], [('gddt', 11), ('gddt', 12), ('dulieu', 11), ('dulieu', 14)]),
    ('UDEV03', 'dev',
     'Đường dẫn URL API cụ thể để kết nối Cơ sở dữ liệu tổng hợp quốc gia là gì?',
     'Các điều về kết nối, chia sẻ và khai thác quy định nguyên tắc/thẩm quyền; không có tài liệu endpoint hoặc URL triển khai API.',
     ['API', 'URL', 'kết nối', 'chia sẻ'], [('dulieu', 17), ('dulieu', 18), ('dulieu', 19), ('dulieu', 20)]),
    ('UDEV04', 'dev',
     'Tính đến ngày 16/11/2026, có bao nhiêu tổ chức đang được cấp phép kinh doanh dịch vụ tin cậy tại Việt Nam?',
     'Luật quy định điều kiện, trách nhiệm và chế độ báo cáo, không chứa danh sách/số liệu tổ chức được cấp phép tại ngày được hỏi.',
     ['thống kê', 'báo cáo', 'tổ chức cung cấp', '2026'], [('gddt', 14), ('gddt', 15), ('gddt', 23), ('gddt', 24)]),
    ('UDEV05', 'dev',
     'Số điện thoại đường dây nóng và email tiếp nhận báo cáo sự cố dữ liệu của Trung tâm dữ liệu quốc gia là gì?',
     'Các điều về trách nhiệm, bảo vệ dữ liệu và kênh tiếp nhận không cung cấp số hotline hoặc địa chỉ email liên hệ thực tế.',
     ['điện thoại', 'đường dây nóng', 'email', 'sự cố'], [('dulieu', 13), ('dulieu', 14), ('dulieu', 16), ('gddt', 15)]),
    ('UTEST01', 'test',
     'Cá nhân mua bán dữ liệu trái pháp luật bị phạt tiền cụ thể bao nhiêu đồng theo bộ tài liệu này?',
     'Luật nêu hành vi bị nghiêm cấm và quản lý/xử lý vi phạm, không có khung tiền phạt cụ thể cho tình huống này.',
     ['mức phạt', 'phạt tiền', 'vi phạm', 'mua bán'], [('dulieu', 5), ('dulieu', 6), ('gddt', 4), ('gddt', 24)]),
    ('UTEST02', 'test',
     'Mã mẫu đơn và danh mục giấy tờ cụ thể để đăng ký cung cấp dịch vụ trung gian dữ liệu là gì?',
     'Điều 40 nêu yêu cầu đăng ký và giao Chính phủ quy định chi tiết; corpus không có mẫu đơn hoặc danh mục hồ sơ thực hiện thủ tục.',
     ['mẫu đơn', 'hồ sơ', 'biểu mẫu', 'đăng ký'], [('dulieu', 21), ('gddt', 14), ('gddt', 15)]),
]


def canonical(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', text)).strip()


def main():
    source = ROOT / 'starter/data/day6/original_questions.json'
    page_path = ROOT / 'starter/data/day6/pages.jsonl'
    if not source.exists() or not page_path.exists():
        raise FileNotFoundError('Import Day 6 assets once with starter/import_day6_assets.py first.')
    pages = [json.loads(line) for line in page_path.read_text(encoding='utf-8').splitlines()]
    assert len(pages) == 49
    page_by_id = {(p['document_id'], p['page']): p for p in pages}
    questions = []
    for old in read_json(source):
        q = {k: old[k] for k in ('id', 'split', 'question', 'expected_answer')}
        q['answerable'] = True
        q['gold'] = [{'source_id': g['source_id'], 'page': g['page'],
                      'evidence': g.get('evidence', g.get('evidence_quote'))} for g in old['gold']]
        q['filter'] = old.get('filter')
        q['filter_provenance'] = old.get('filter_provenance')
        q['provenance'] = 'Day 6 benchmark, original question/split/evidence retained'
        if q['id'] == 'Q07':
            g = q['gold'][0]
            first, last = g['evidence'].split('c) ', 1)
            q['context_gold_groups'] = [[
                {'source_id': g['source_id'], 'page': g['page'], 'evidence': first.strip()},
                {'source_id': g['source_id'], 'page': g['page'], 'evidence': 'c) ' + last.strip()}]]
            q['context_scoring_note'] = 'Both fragments are required; strict ranking metrics still use the original full single-chunk gold.'
        questions.append(q)
    audits = []
    for qid, split, query, reason, terms, related in NEGATIVES:
        scope = [{'source_id': doc, 'page': page} for doc, page in sorted(page_by_id)]
        q = {'id': qid, 'split': split, 'question': query, 'answerable': False,
             'expected_behavior': 'search_and_abstain', 'absence_reason': reason,
             'absence_review_id': qid, 'filter': None,
             'provenance': 'Day 7 added near-domain unanswerable case; Codex review, not human-confirmed'}
        questions.append(q)
        scans = []
        for term in terms:
            # Remove all whitespace too, to catch spacing artifacts in source PDFs.
            key = re.sub(r'\s+', '', canonical(term).casefold())
            matches = [{'source_id': p['document_id'], 'page': p['page']} for p in pages
                       if key in re.sub(r'\s+', '', canonical(p['text']).casefold())]
            scans.append({'term': term, 'matching_pages': matches})
        audits.append({'id': qid, 'reviewer': 'Codex', 'human_confirmed': False,
            'scope': scope, 'page_count': len(pages),
            'method': 'Scanned all indexed page texts and document article coverage; read related provisions semantically. Keyword matches are navigation evidence, not the sole basis for absence.',
            'absence_reason': reason, 'keyword_scan': scans,
            'related_pages_reviewed': [{'source_id': doc, 'page': page,
                                       'text': page_by_id[(doc, page)]['text']} for doc, page in related],
            'excluded_scope': 'gddt physical page 27 has no extracted text and is not indexed; no claim about external decrees, live registries or non-indexed images.'})
    out = ROOT / 'benchmark'
    write_json(out / 'questions.json', questions)
    write_json(out / 'absence_review.json', {'source_pages_sha256': hashlib.sha256(page_path.read_bytes()).hexdigest(),
        'original_questions_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'reviews': audits})
    write_json(out / 'protocol.json', {'baseline': 'dense',
        'dev_methods': ['dense', 'tfidf-syllable', 'tfidf-word', 'hybrid', 'rerank'],
        'top_k': 9, 'candidate_k': 30, 'rrf_constant': 60, 'budget_chars': 4000,
        'filter_policy': 'none for all comparison methods',
        'selection_rule': ['highest dev Evidence Hit@3', 'highest dev Hit@1',
                           'highest dev Context Evidence Rate', 'lowest mean dev retrieval latency'],
        'ranking_metric': 'strict full single-chunk gold as Day 6',
        'context_metric': 'any alternative full evidence; when context_gold_groups is specified, all fragments in one alternative group must be supported',
        'unanswerable_policy': 'exclude from retrieval/context denominators; measure abstention only from actual agent answers with separate review labels',
        'test_policy': 'freeze chosen method/config/source hashes before test; run baseline + selected only; do not tune using test results',
        'test_provenance': 'Five answerable test cases reused from Day 6, previously evaluated there; two unanswerable test cases newly authored. Not a wholly new unseen test set.'})
    print(json.dumps({'questions': len(questions), 'dev_answerable': 15, 'dev_unanswerable': 5,
                      'test_answerable': 5, 'test_unanswerable': 2}, indent=2))


if __name__ == '__main__':
    main()
