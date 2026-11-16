# Kết quả retrieval dev — 16/11/2026

Đây là kết quả lịch sử của lần chạy 15 câu dev ban đầu. Bộ mới đã có 20 dev/7 test, runtime Day 7 độc lập và context nhiều fragment; xem [kết quả cập nhật](BENCHMARK_DAY7_RESULTS.md).

Chạy thực tế trên CPU, cùng 401 chunks từ 49 trang, 15 câu dev Day 6 Q01–Q15; không đánh giá test. Cấu hình: top-k=9, candidate-k=30 mỗi nhánh Hybrid, RRF constant=60, context budget=4.000 ký tự, không dùng filter ở tất cả phương pháp. Query gốc được giữ nguyên.

| Phương pháp | Hit@1 | Evidence Hit@3 | Evidence Hit@9 | Context hit, một chunk | Trung bình/query |
|---|---:|---:|---:|---:|---:|
| Dense | 10/15 (66,67%) | 12/15 (80%) | 13/15 (86,67%) | 13/15 | 26,1 ms |
| TF-IDF âm tiết | 10/15 (66,67%) | 12/15 (80%) | 12/15 (80%) | 12/15 | 1,9 ms |
| TF-IDF tách từ | 9/15 (60%) | 12/15 (80%) | 12/15 (80%) | 12/15 | 4,5 ms |
| Hybrid RRF | 11/15 (73,33%) | 12/15 (80%) | 13/15 (86,67%) | 13/15 | 31,8 ms |
| Hybrid + CrossEncoder rerank | 13/15 (86,67%) | 14/15 (93,33%) | 14/15 (93,33%) | 14/15 | 1.139,9 ms |

Mỗi phương pháp chạy thành công 15/15 câu, không có lỗi. Thời gian đo một lượt trên máy hiện tại, gồm retrieval và đóng gói context, không gồm thời gian khởi tạo suite khoảng 18,4 giây; không phải số liệu thống kê nhiều lần chạy. Không gọi dịch vụ model trả phí; điện năng không được đo.

Kiểm tra code: 27/27 unit tests đạt, `pip check` không có dependency hỏng. Kiểm tra tích hợp dùng model thật: cả năm cấu hình đều trả top-9 hợp lệ với từng category `du_lieu` và `giao_dich_dien_tu` (10 trường hợp); hai nhánh Hybrid giữ cùng filter và kết quả rerank thuộc candidate pool ban đầu.

## Tác động của tách từ tiếng Việt

Tách từ Underthesea thay đổi danh sách top-3 ở **13/15 câu**, nhưng Evidence Hit@3 giữ nguyên 12/15. Hit@1 giảm từ 10/15 xuống 9/15, thời gian query tăng từ khoảng 1,9 ms lên 4,5 ms. Trên tập dev này, tách từ chưa cải thiện chỉ số retrieval đã đo.

Ví dụ Q09 “Chủ thể dữ liệu là ai?”: âm tiết tạo `chủ`, `thể`, `dữ`, `liệu`; tách từ tạo `chủ_thể`, `dữ_liệu`. Chunk evidence `d65bb4594fd5c8d8ab123d53ef02ebbf` nằm ở hạng 1 trong chế độ âm tiết và hạng 3 sau tách từ. Đây là câu làm giảm Hit@1; cả hai vẫn hit trong top-3. Tách từ làm thay đổi từ vựng và trọng số TF-IDF; cần xem thêm tính nhất quán giữa query và văn bản PDF còn lỗi cách chữ trước khi chọn tokenizer cuối cùng.

## Hybrid và rerank

Hybrid RRF tăng Hit@1 lên 11/15 so với Dense 10/15, nhưng Hit@3 giữ nguyên. CrossEncoder tăng Hit@1 lên 13/15 và Hit@3 lên 14/15, đổi lại chi phí tính toán local cao hơn. Tất cả 15 query rerank đều không có cặp bị cắt do giới hạn 512 tokens trong lần chạy này.

Rerank vẫn trượt Hit@1 ở Q02 và Q07. Q02 có evidence trong top-3 sau rerank, cần đọc trace nếu muốn cải thiện top-1. Q07 có giới hạn chunking nêu dưới đây. Chưa dùng kết quả này để tự động chốt cấu hình hay đánh giá test.

## Định nghĩa metric và giới hạn

Evidence hit dùng cùng quy tắc chặt của Day 6: đúng source ID và trang, evidence nằm trọn trong một chunk sau chuẩn hóa NFC và gộp whitespace. Không bỏ dấu, không sửa nội dung evidence. `context_hit` dùng cùng quy tắc một chunk và chỉ xét những chunks thực sự vừa context budget.

**Q07 có evidence trải qua hai chunks ở trang 14**, nên không pipeline nào đạt strict single-chunk hit cho câu đó. Phủ gold bằng một chunk của corpus là **14/15**. Q07 vẫn giữ trong mẫu số và tính là miss cho cả năm cấu hình. Do vậy metric context trong bảng là chỉ số một chunk, có thể đánh giá thấp context chứa đủ bằng chứng từ nhiều chunks; chưa phải phép chấm đầy đủ cho bằng chứng nhiều đoạn. Cần thiết kế phép chấm multi-chunk riêng nếu dùng loại câu này, giữ định nghĩa giống nhau cho mọi pipeline.

Đây là 15 câu dev có đáp án, thiếu ít nhất 2 câu dev không đủ bằng chứng theo yêu cầu Day 7. Kết quả chưa thể hiện chất lượng agent/LLM, citation hoặc abstention. Tập test Day 6 không được chạy trong đợt này; nếu đã dùng test cũ để chỉnh hệ thống trước đó thì cần test mới theo GUIDE.

## Artifact và cách tái tạo

- `starter/results/retrieval-dev/summary.json`: cấu hình, hash corpus/câu hỏi, số liệu đầy đủ.
- `starter/results/retrieval-dev/*-traces.json`: query, source, trang, điểm, branch ranks, candidate pool, thứ hạng trước/sau rerank và context.
- `starter/results/retrieval-dev/segmentation-comparison.json`: tác động tách từ cho từng câu.
- `starter/.models/mmarco-mMiniLMv2-L12-H384-v1/artifact.json`: revision và SHA-256 model đã tải.

Artifact local trong `starter/results` và `.models` được Git bỏ qua. Tái tạo theo [hướng dẫn chạy](../starter/RETRIEVAL_METHODS.md).
