# Advanced — IPCC AR6 Synthesis Report

Tiếp tục bằng [hướng dẫn chạy từng phần](LOW_RESOURCE.md). Không chạy toàn bộ embedding, reranker và LLM cùng lúc trên máy hiện tại.

- Nguồn: `data/IPCC_AR6_SYR_FullVolume.pdf`, 186 trang; [bản chính thức](https://www.ipcc.ch/report/ar6/syr/downloads/report/IPCC_AR6_SYR_FullVolume.pdf).
- `index --stage status`: xem tiến độ, không nạp model.
- `safe_run`: đúng một lượt hữu hạn có checkpoint rồi thoát.
- `worker`: mỗi câu hỏi qua ba tiến trình riêng: retrieve → rerank → answer.
- `artifacts/document`: native text/layout, bảng, nhãn hình và ảnh trang để đối chiếu.
- `artifacts/index`: catalog, checkpoint từng trang và Chroma; không xóa để chạy lại.
- `artifacts/jobs`: trace, câu trả lời hoặc lỗi của từng job.

Artifact lớn và PDF được Git bỏ qua; model đã có tại `starter/.models`. Không cần cài hoặc tải lại để chạy tiếp trên máy này. Yêu cầu chấm điểm đầy đủ nằm ở [ADVANCED.md](../ADVANCED.md); kết quả chưa được công bố khi index/benchmark còn đang làm.
