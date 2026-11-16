# Retrieval Studio — web local

Từ thư mục gốc Day 7:

```powershell
& .\.venv\Scripts\python.exe -B -m demo.server
```

Mở **http://127.0.0.1:8765**. Không cần framework web/Node.js/API key. Giữ terminal mở, Ctrl+C để dừng server. Model chỉ nạp khi chạy tác vụ; embedding/reranker/LLM ở các tiến trình riêng, một tác vụ tại một thời điểm.

- Cơ bản: Dense, TF-IDF hai tokenizer, Hybrid và rerank; filter, top-k, context, PDF và trace.
- So sánh: hai tokenizer trực tiếp; bảng dev/test đọc từ artifact benchmark đã lưu.
- Advanced: TF-IDF trên catalog IPCC, filter nội dung, source/page/bbox và ảnh/PDF; chạy index theo lượt nhỏ. Dense/agent IPCC cần đủ vectors.
- Hướng dẫn demo tích hợp trong UI; [hướng dẫn đầy đủ](../docs/DEMO_WEB.md), [kiểm chứng](../docs/WEB_VERIFICATION.md), [báo cáo](../report/individual/2A202603737_LeVietKhoa.md).

Profile web candidate-k 12, rerank batch 1/256 tokens, CPU 1. Profile benchmark cũ khác và giữ nguyên metrics/source freeze. Artifact tác vụ nằm trong `demo/artifacts`, được Git bỏ qua. Chưa có điểm benchmark Advanced hoặc visual QA trên trình duyệt.
