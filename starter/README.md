# Starter Day 7

Đã có **giao diện web local**: từ thư mục gốc chạy `& .\.venv\Scripts\python.exe -B -m demo.server`, mở http://127.0.0.1:8765. Xem [hướng dẫn demo](../docs/DEMO_WEB.md). Giao diện dùng worker tách model và một tác vụ tại một thời điểm cho máy hiện tại; các lệnh benchmark bên dưới là cấu hình thực nghiệm cũ.

Runtime hiện độc lập trong Day 7: xem [model, Chroma và môi trường local](LOCAL_RUNTIME.md). Trên Windows, chạy bằng `& ./.venv/Scripts/python.exe -B ...` thay cho lệnh `python3` nếu máy đang dùng alias Microsoft Store.

Benchmark hiện có 20 dev và 7 test, đã chạy dev, chốt cấu hình rồi chạy Dense + rerank trên test. Xem [kết quả mới](../docs/BENCHMARK_DAY7_RESULTS.md), [câu hỏi và protocol](../benchmark/README.md). Phần trả lời/citation/abstention của agent vẫn cần LLM riêng.

| File | Công dụng |
|---|---|
| `agentic.py` | Khung agent ví dụ với số lượt search, top-k và context budget có thể cấu hình |
| `baseline.py` | TF-IDF lexical baseline, chạy offline |
| `convert_day6.py` | Chuyển một số trường JSON từ Day 6 |
| `day6_retriever.py` | Adapter dense retrieval dùng model local và bản sao Chroma Day 6; xem [cách chạy](DAY6_CONNECTION.md) |
| `dense_retrieval.py` | Dense Day 7: mặc định top-9, metadata filter category và lưu trace; xem [cách chạy](DENSE_RETRIEVAL.md) |
| `retrieval.py` | Chạy Dense, TF-IDF âm tiết/tách từ, Hybrid RRF, Hybrid + CrossEncoder rerank |
| `compare_retrieval.py` | Benchmark một split, so sánh ảnh hưởng tách từ và lưu trace |
| `setup_retrieval.py` | Tạo `.venv` Day 7, cài Underthesea và tải model reranker local |
| `import_day6_assets.py` | Import model embedding, Chroma và tài liệu vào Day 7; có thể sao chép thư viện để gỡ phụ thuộc môi trường Day 6 |
| `local_embeddings.py` | Embedding local tại Day 7, giữ model/revision/normalization Day 6 |
| `build_day7_benchmark.py` | Tạo benchmark 20 dev / 7 test và hồ sơ rà soát thiếu evidence |
| `freeze_retrieval.py` | Chọn bằng dev và chốt cấu hình/hash nguồn trước test |
| `agent_metrics.py` | Tổng hợp nhãn đánh giá do bạn tự chấm |

Dense, Lexical, Hybrid và Retrieval + Rerank đã có; xem [hướng dẫn các phương pháp](RETRIEVAL_METHODS.md) và [kết quả dev](../docs/RETRIEVAL_DEV_RESULTS.md). Dùng `.venv` Day 7 cho Underthesea và reranker. Bạn cần hoàn thiện benchmark Day 7 và nối controller với model thật để hoàn thành agent. Mock chỉ dùng để test code.

## 1. Kết nối agent

Trong `agentic.py`, hiện thực:

- `Controller.decide`: gọi model thật và trả `{action: "search", query: "..."}` hoặc `{action: "answer", answer: "... [chunk-id]", citations: ["chunk-id"]}`.
- `Retriever.search`: tạo query embedding tương thích Day 6, truy vấn vector store thật và trả chunk theo [định dạng dữ liệu](../data/README.md).

Tự viết chương trình nối hai phần với `run_agent`, hoặc thay thế bằng kiến trúc nhiều tool. Tham số `max_searches`, `top_k` và `budget` chỉ là mặc định của ví dụ, không phải giới hạn của đề. Xem `tests/test_agentic.py` để hiểu cách gọi; kết nối trong test là mock. Khung code kiểm tra citation ID có trong context, nhưng bạn phải tự đọc xem nguồn có hỗ trợ câu trả lời. Báo lỗi kết nối, không thay bằng kết quả giả.

## 2. Chạy TF-IDF baseline

Chạy từ thư mục gốc với Python 3.11 trở lên:

```bash
python3 -m unittest discover -s tests -v
python3 starter/baseline.py --chunks data/example_chunks.json --questions data/example_questions.json --split dev --output starter/results/example-dev
```

Kết quả có `summary.json` và `traces.json`. Dữ liệu mẫu chỉ có một câu, không đủ để nộp bài. TF-IDF là lexical retrieval, không dùng filter và không thay dense retrieval.

## 3. Dùng dữ liệu Day 6

Xuất chunk và câu hỏi thành hai JSON array. Starter Day 6 không quy định tên bảng hay cách xuất; bạn cần tự thực hiện. Nếu chunk có `chunk_id`, `document_id`, `source`, `page`, `text`, `metadata` và câu hỏi có `gold_source_id`, `gold_page`, `evidence_quote`, chạy:

```bash
python3 starter/convert_day6.py --chunks <day6_chunks.json> --questions <day6_questions.json> --output starter/data/converted
python3 starter/baseline.py --chunks starter/data/converted/chunks.json --questions starter/data/converted/questions.json --split dev --output starter/results/dev-tfidf
```

Thay phần trong `< >` bằng đường dẫn thật. Script chỉ đổi tên trường, không tự truy cập database hay đoán evidence. Nếu cấu trúc khác, tự viết adapter. Đối chiếu lại nguồn, trang và evidence.

`--split dev` chỉ chấm dev. Sau khi chốt cấu hình, dùng `--split test` và chọn thư mục kết quả khác. Nếu test Day 6 từng dùng để chỉnh hệ thống, tạo test mới theo [GUIDE.md](../GUIDE.md). Baseline mẫu dùng evidence nằm trong một chunk và context từ top-3; cần mở rộng hoặc tự đánh giá nếu dùng multi-hop, context từ nhiều lượt hay schema khác. Khớp nguyên văn bằng code không thay thế đánh giá thủ công.

## 4. Tổng hợp đánh giá agent

Sau khi chạy agent thật và tự chấm, chuẩn bị ba JSON array:

- `cases.json`: mỗi câu có `id`, `split`, `answerable` (`true` nếu có đủ evidence).
- `traces.json`: mỗi kết quả có `query_id`, `status` (`answered`, `abstain`, `error`), `events`, `citations`. Thêm `query_id` vào kết quả `run_agent`; lỗi kết nối ghi riêng với `status: "error"`. Script đếm tool use qua event `search`: nếu dùng nhiều tool, chuẩn hóa mỗi lượt retrieval về event này và ghi tên tool trong trường khác, hoặc tự viết metric tương đương.
- `reviews.json`: mỗi nhãn có `query_id`, `citation_support` là danh sách đúng/sai ứng với từng citation. Câu có đáp án cần `answer_grade` 0–2 theo [BENCHMARK.md](../BENCHMARK.md); nếu bị từ chối, chấm 0. Câu thiếu evidence cần `abstention_correct` (`true`/`false`) do người chấm xác nhận. Lần chạy lỗi không cần nhãn.

```bash
python3 starter/agent_metrics.py --cases <cases.json> --traces <traces.json> --reviews <reviews.json> --split test --output starter/results/agent-test/summary.json
```

Thay đường dẫn trong `< >`. Script tổng hợp nhãn bạn đã chấm, không tự đánh giá nội dung. Mẫu số bằng 0 nghĩa là không áp dụng. Lỗi kết nối được báo riêng, không tính vào chất lượng; giữ trace và nhãn để đối chiếu.

## Lưu ý

TF-IDF dùng cách tách từ đơn giản. `baseline.py` dùng mặc định context budget 800 ký tự, gồm cả nguồn; chunk không vừa bị bỏ. Bạn có thể chọn cách khác. File kết quả cùng tên sẽ bị ghi đè. `starter/data/` và `starter/results/` không được Git theo dõi mặc định; nếu được phép chia sẻ, dùng `git add -f <đường-dẫn>`, hoặc ghi cách tái tạo. Không nộp dữ liệu mật và secret.

Khung agent ưu tiên giữ chunk từ lần search trước. Khi chunk đầu chiếm gần hết budget, lần search sau có thể không thêm được evidence; hãy kiểm tra trace và thử cách chọn context phù hợp trên dev. Citation ID hợp lệ hoặc verifier trả “đúng” không đảm bảo câu trả lời được hỗ trợ; cần chấm thủ công.
