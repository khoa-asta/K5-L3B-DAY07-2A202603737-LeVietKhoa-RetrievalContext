# Tiến độ Advanced — 16/11/2026

Đã chuyển sang xử lý từng lượt cho máy 16 GB RAM. [Cách chạy tiếp](LOW_RESOURCE.md).

| Phần việc | Trạng thái đã kiểm chứng |
|---|---|
| Chuẩn bị catalog PDF | Xong 186/186 trang, không nạp model |
| Catalog | 2.647 text units, 40 bảng tự trích, 26 figure units; 4.455 chunks |
| Coverage | 169 trang có units; 17 trang còn lại là trang không có native text hoặc chỉ tiêu đề/số trang ngắn. Chi tiết trong manifest; nội dung chỉ có pixel chưa được tự động diễn giải |
| Khôi phục Chroma | Collection `ipcc_7f8e176daf7c77b0` khớp catalog; giữ 1.088 vectors cũ |
| Thử embedding giới hạn | Lượt CLI +2, lượt web +2; hiện **1.092/4.455** |
| Kiểm tra phần mềm | 53 tests đạt, gồm 11 kiểm tra Advanced và 11 kiểm tra web mới |
| Demo IPCC | Web TF-IDF tìm figure/table trên catalog đầy đủ, có ảnh/PDF nguồn; không cần chờ Chroma |
| Retrieval/rerank/answer | Đã tách worker từng bước, chưa chạy đánh giá thực tế qua ba model |
| Benchmark Advanced | Chưa xây đủ dev/test, chưa chốt cấu hình và chưa có điểm answer/citation/abstention |

Đo trên máy hiện tại, một CPU logic, `BelowNormal`:

| Lượt thử | Kết quả |
|---|---|
| Chuẩn bị 8 trang | Khoảng 7–8 giây; RAM đỉnh khoảng 315 MB |
| Chuẩn bị/ghép catalog lượt cuối | RAM đỉnh 340,5 MB |
| Embedding 2 chunks, batch 1 | 62,23 giây tổng, 1,94 giây trong vòng xử lý; RAM đỉnh Windows 1.250,5 MB; RAM hệ thống còn 7.431,4 MB lúc cuối lượt |

Chi phí khởi động thư viện/model lớn hơn thời gian xử lý hai chunks. Lệnh mặc định xử lý tối đa 16 chunks rồi thoát; checkpoint giúp tiếp tục vào thời điểm khác. Số RAM/thời gian trên là đo tại một lượt, không phải bảo đảm cho mọi lần chạy và không xác định nguyên nhân máy sập nguồn trước đó.

Thứ tự công việc tiếp theo:

1. Hoàn tất 3.363 embeddings còn thiếu bằng các lượt nhỏ; chỉ bước này dùng embedding model.
2. Xây benchmark Advanced riêng: dev tối thiểu 15 câu đủ bằng chứng + 3 câu thiếu bằng chứng; test tối thiểu 24 câu đủ bằng chứng theo nhóm + 6 câu thiếu bằng chứng. Đối chiếu evidence trên PDF gốc.
3. Chạy từng câu dev qua retrieve → rerank → answer, mỗi bước một tiến trình; chốt cấu hình bằng dev.
4. Freeze trước test, đánh giá toàn bộ test và review câu trả lời/citation/abstention. Giữ lỗi và timeout trong mẫu số; chỉ báo bonus khi thực sự đủ tiêu chí.

Chưa có kết quả đủ cơ sở công bố đạt Advanced hoặc bonus 90%. Corpus/benchmark cơ bản Day 7 giữ riêng với IPCC.
