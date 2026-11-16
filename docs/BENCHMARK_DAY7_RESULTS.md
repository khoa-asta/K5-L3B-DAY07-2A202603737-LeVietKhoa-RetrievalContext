# Benchmark Day 7 và runtime độc lập — 16/11/2026

Đã bổ sung 5 câu dev và 2 câu test thiếu bằng chứng, tạo bộ **27 câu: dev 15 có đáp án + 5 thiếu evidence, test 5 có đáp án + 2 thiếu evidence**. Câu hỏi nằm ở [benchmark/questions.json](../benchmark/questions.json); [absence_review.json](../benchmark/absence_review.json) ghi rà soát toàn bộ 49 trang index, đọc điều khoản liên quan và lý do cho từng câu mới. Nhãn này do Codex hỗ trợ, chưa có xác nhận riêng của người học.

## Model và dữ liệu local

Embedding MiniLM, bản sao Chroma, PDF nguồn, code embedding và các thư viện Python đã nằm trong Day 7. Gỡ liên kết site-packages Day 6 sau khi sao chép. Kiểm tra với đường dẫn Day 6 giả lập không tồn tại vẫn trả 9 chunks đúng filter; các module Torch, Chroma, Sentence Transformers và Underthesea nạp từ `.venv` Day 7.

- Embedding: `starter/.models/paraphrase-multilingual-MiniLM-L12-v2`, 384 chiều, cùng revision Day 6.
- Vector store: `starter/data/day6/chroma`, collection B, 401 chunks.
- Thư viện: `.venv/Lib/site-packages` Day 7, không còn `day6_dependencies.pth`.
- Nguồn: `data/36-vbhn-vpqh.pdf`, `data/luat60.pdf`, `data/day6_manifest.json`.
- Bằng chứng: `starter/results/local-assets-import.json`, `starter/results/standalone-check.json`.

## Protocol và chốt trước test

Cấu hình chung: top-k=9, candidate-k=30 mỗi nhánh, RRF constant=60, budget=4.000 ký tự, query gốc, không dùng filter trong mọi phương pháp so sánh. Câu thiếu evidence được chạy retrieval nhưng loại khỏi mẫu số Hit@1/Hit@3/Hit@9 và Context Evidence Rate.

[Protocol](../benchmark/protocol.json) ưu tiên dev Evidence Hit@3, rồi Hit@1, Context Evidence Rate và độ trễ. [Freeze](../benchmark/frozen_retrieval.json) chốt **Hybrid + rerank** lúc **12:04:47 ngày 16/11/2026, UTC+7**, sau dev và trước test; lưu hash code, câu hỏi, protocol và identity corpus/index. Evaluator kiểm tra freeze trước khi chạy test và chỉ cho phép Dense baseline + phương pháp được chọn. Không chỉnh tham số dựa trên test.

Năm câu test có đáp án kế thừa Day 6 và từng được đánh giá tại đó. Đây là test kế thừa, không phải tập mới hoàn toàn chưa từng được xem. Nếu dùng kết quả này để chỉnh tiếp thì cần test mới cho đánh giá độc lập.

## Kết quả dev — 20 câu mỗi phương pháp

| Phương pháp | Hit@1 | Evidence Hit@3 | Evidence Hit@9 | Context Evidence Rate | TB/query |
|---|---:|---:|---:|---:|---:|
| Dense | 10/15 (66,67%) | 12/15 (80,00%) | 13/15 (86,67%) | 13/15 (86,67%) | 33,0 ms |
| TF-IDF âm tiết | 10/15 (66,67%) | 12/15 (80,00%) | 12/15 (80,00%) | 12/15 (80,00%) | 2,6 ms |
| TF-IDF tách từ | 9/15 (60,00%) | 12/15 (80,00%) | 12/15 (80,00%) | 12/15 (80,00%) | 4,1 ms |
| Hybrid RRF | 11/15 (73,33%) | 12/15 (80,00%) | 13/15 (86,67%) | 14/15 (93,33%) | 31,2 ms |
| Hybrid + rerank | 13/15 (86,67%) | 14/15 (93,33%) | 14/15 (93,33%) | 15/15 (100,00%) | 1.132,8 ms |

Mỗi phương pháp chạy đủ 20/20, gồm 5 câu thiếu evidence, không có lỗi. Mẫu số chất lượng là 15 câu có đáp án. Thời gian trung bình tính cả 20 query, loại thời gian khởi tạo; đây là một lượt đo, chưa có độ lệch chuẩn. Không gọi API model trả phí; điện năng không đo.

Ranking giữ định nghĩa evidence nguyên vẹn trong một chunk của Day 6. Với Q07, chấm context bằng `context_gold_groups`: cả hai đoạn bắt buộc phải có trong context và đúng nguồn/trang. Vì vậy rerank đạt context 15/15 dù ranking Hit@3 tối đa 14/15 với định nghĩa một chunk. Không đổi nhãn chỉ để làm tăng điểm; quy tắc nhiều đoạn được khai báo trước lần chạy mới và áp dụng giống nhau cho mọi pipeline.

Tách từ vẫn chưa cải thiện TF-IDF trên 15 câu có đáp án: Hit@1 giảm 10/15 xuống 9/15, Hit@3 không đổi. Không dùng 5 câu thiếu evidence để tính các chỉ số đó.

## Kết quả test — 7 câu mỗi phương pháp

| Phương pháp | Hit@1 | Evidence Hit@3 | Evidence Hit@9 | Context Evidence Rate | TB/query |
|---|---:|---:|---:|---:|---:|
| Dense baseline | 3/5 (60,00%) | 4/5 (80,00%) | 4/5 (80,00%) | 4/5 (80,00%) | 31,3 ms |
| Hybrid + rerank đã chốt | 5/5 (100,00%) | 5/5 (100,00%) | 5/5 (100,00%) | 5/5 (100,00%) | 1.162,4 ms |

Cả hai chạy đủ 7/7, bao gồm UTEST01/UTEST02, không lỗi. Mẫu số chất lượng là 5 câu có đáp án; thời gian tính cả 7 query. Kết quả 100% là retrieval/context trên 5 câu này, không phải điểm agent hay tỷ lệ của toàn bộ bài lab.

## Review context test theo mức 0/1/2

Đã đọc 5 context test có đáp án cho mỗi cấu hình, đối chiếu nguồn/trang và điều kiện/ngoại lệ. Nhãn ở [test_context_review.json](../benchmark/test_context_review.json) do Codex rà soát, `human_confirmed=false`; chưa coi là xác nhận thủ công của học viên.

| Query | Dense | Rerank | Lý do chính |
|---|---:|---:|---|
| Q16 | 2 | 2 | Có quy tắc giao kết và ngoại lệ các bên thỏa thuận khác, gddt trang 17 |
| Q17 | 2 | 2 | Có giá trị thông báo tương đương văn bản giấy, gddt trang 17 |
| Q18 | 2 | 2 | Có quyền lựa chọn tài khoản và ngoại lệ luật khác, gddt trang 22 |
| Q19 | 0 | 2 | Dense thiếu Điều 40(2); rerank đưa ngoại lệ dịch vụ trong nội bộ tổ chức lên hạng 1, dulieu trang 21 |
| Q20 | 2 | 2 | Có giá trị khai thác/sử dụng như dữ liệu gốc, dulieu trang 19 |

Phân bố: Dense mức 0/1/2 = **1/0/4**, rerank = **0/0/5**. UTEST01 trả các đoạn về phí/nguyên tắc, không có khung tiền phạt; UTEST02 trả quy định đăng ký, không có mã mẫu đơn/danh mục hồ sơ. Đây là nhận xét về context và nhãn thiếu thông tin, không phải câu trả lời/từ chối do agent sinh.

## Phần chưa có LLM

MiniLM tạo embedding; Chroma tìm vector; CrossEncoder xếp hạng cặp query–chunk. Chúng đủ để thực hiện và đánh giá retrieval. Phần agent của `BENCHMARK.md` cần LLM sinh câu trả lời có citation, chọn hành động tiếp hoặc từ chối.

Theo phạm vi đang thực hiện, chưa tải/nối LLM sinh văn bản. Do đó `abstention.status=not_evaluated`; chưa có Grounded answer, Citation support, Tool use do LLM hay False abstention. Không dùng điểm retrieval hoặc nhãn `answerable` để giả lập việc từ chối. Phần agent của BENCHMARK vẫn cần hoàn thành riêng.

## Cách chạy lại và artifact

```powershell
$py = '.\.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

# Query thường ngày, không cần mở Day 6.
& $py -B starter/retrieval.py --method rerank --query 'Dữ liệu dùng chung là gì?' --top-k 9 --output starter/results/query-local.json

# Tái tạo các kết quả dev/test vào thư mục khác, giữ nguyên freeze hiện tại.
& $py -B starter/compare_retrieval.py --questions benchmark/questions.json --split dev --top-k 9 --candidate-k 30 --budget 4000 --output starter/results/benchmark-repeat/dev
& $py -B starter/compare_retrieval.py --questions benchmark/questions.json --split test --methods dense rerank --top-k 9 --candidate-k 30 --budget 4000 --freeze benchmark/frozen_retrieval.json --output starter/results/benchmark-repeat/test
```

Freeze hiện tại đã tồn tại, không chạy lại `freeze_retrieval.py` lên cùng file. Thí nghiệm mới phải giữ nguyên kết quả cũ, dùng freeze mới sau dev và không chỉnh theo test đã xem.

- Dev: `starter/results/benchmark-day7-local/dev/summary.json`, trace từng phương pháp và `segmentation-comparison.json`.
- Test: `starter/results/benchmark-day7-local/test/summary.json`, `dense-traces.json`, `rerank-traces.json`.
- Câu hỏi/nhãn: `benchmark/questions.json`, `absence_review.json`, `test_context_review.json`.
- Kiểm tra: **31/31 tests đạt**; standalone check xác nhận không cần đường dẫn Day 6. Artifact lớn vẫn Git-ignore; xem [runtime local](../starter/LOCAL_RUNTIME.md).
