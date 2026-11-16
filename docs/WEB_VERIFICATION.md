# Kiểm chứng demo web — 16/11/2026

Server local và worker thật đã được kiểm tra qua HTTP. Không dùng mock để tạo kết quả retrieval trong bảng dưới. Các lượt chạy lần lượt, không nạp đồng thời embedding, reranker và LLM.

| Case | Kết quả | Tổng giây | RAM đỉnh worker (MB) |
|---|---|---:|---:|
| TF-IDF âm tiết | 9 đoạn, context trong 2.000 ký tự | 0,347 | 22,4 |
| Filter `du_lieu` | 9 đoạn đều đúng category | 0,352 | 22,4 |
| IPCC Figure SPM.7 | Có figure evidence, PDF/ảnh trang nguồn truy cập được | 0,455 | 40,8 |
| IPCC Table SPM.1 | Có table evidence, PDF/ảnh trang nguồn truy cập được | 0,428 | 40,4 |
| Dense | 9 đoạn từ Chroma/model local thật | 28,679 | 1.228,2 |
| Hybrid | 9 đoạn, Dense + TF-IDF theo từ + RRF | 32,398 | 1.238,1 |
| Hybrid + rerank | 9 đoạn; hai worker + nghỉ 10 giây giữa model | 79,170 | 1.241,1 (worker rerank) |
| So sánh tokenizer | Hai output cùng query; token có gạch dưới của Underthesea | 13,173 | 316,7 |
| Index IPCC từ web | Bổ sung đúng 2 vectors, Chroma 1.090 → 1.092 / 4.455 | 29,787 | 1.233,2 (index last-job) |

Đây là thời gian **toàn bộ task**, gồm khởi động và nạp thư viện/model. Không so sánh trực tiếp với `mean_ms` retrieval benchmark cũ vốn loại phần load. RAM là peak working set do Windows ghi nhận cho worker trong lượt đó, không phải tổng RAM mọi ứng dụng và không bảo đảm mọi query có cùng mức dùng.

**53/53 tests đạt**, gồm 31 tests cơ bản, 11 tests checkpoint/tài nguyên Advanced, 11 tests web/HTTP/task. Kiểm tra mới bao gồm token/origin local, đầu vào và đường dẫn, khóa một task, rerank khác tiến trình, timeout, restart, static/status/PDF byte range, checkpoint vector và citation alias.

16 file nguồn trong freeze được đối chiếu SHA-256: **không có file thay đổi**. Code web nằm riêng ở `demo/`; profile web không được gán metrics từ profile benchmark.

Frontend JavaScript đã qua syntax parser; Python đã qua AST và tests; DOM IDs được đối chiếu không thiếu tham chiếu. **Chưa kiểm chứng trực quan/click trên trình duyệt** vì không có browser kết nối trong phiên làm việc. Không có screenshot QA. Cần mở trang trên máy và kiểm tra trước buổi trình bày.

Artifact chi tiết local:

- `demo/artifacts/verification.json`: 9 case thật và task ID.
- `demo/artifacts/unit-verification.json`: số tests/lỗi và thời điểm chạy.
- `demo/artifacts/tasks/<id>/`: request, state, stage logs, retrieval/result JSON.
- `advanced/artifacts/index/last-job.json`: lượt index 2 vectors qua web.

Advanced Dense/agent Qwen chưa chạy vì index chưa hoàn tất. Không có điểm answer/citation/abstention hoặc kết quả đủ điều kiện bonus. Đây là kiểm chứng chức năng demo, không phải benchmark chất lượng mới.
