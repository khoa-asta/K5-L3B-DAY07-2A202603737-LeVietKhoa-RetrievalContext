# Benchmark Day 7

`questions.json` có 27 câu: **dev 15 có đáp án + 5 thiếu bằng chứng**, **test 5 có đáp án + 2 thiếu bằng chứng**. 20 câu có đáp án kế thừa nguyên query/split/evidence Day 6; 7 câu thiếu bằng chứng được bổ sung cho Day 7.

| ID | Split | Thông tin cần tìm nhưng thiếu trong corpus |
|---|---|---|
| UDEV01 | dev | Mức lệ phí cấp mới giấy phép dịch vụ tin cậy bằng đồng |
| UDEV02 | dev | Độ dài khóa RSA bắt buộc tối thiểu |
| UDEV03 | dev | URL API triển khai Cơ sở dữ liệu tổng hợp quốc gia |
| UDEV04 | dev | Số tổ chức được cấp phép tại ngày 16/11/2026 |
| UDEV05 | dev | Hotline/email báo sự cố dữ liệu thực tế |
| UTEST01 | test | Khung tiền phạt cụ thể cho cá nhân mua bán dữ liệu trái pháp luật |
| UTEST02 | test | Mã mẫu đơn và danh mục hồ sơ đăng ký trung gian dữ liệu |

Mỗi câu có `answerable: false`, `expected_behavior: search_and_abstain`, `absence_reason`. Nhãn thiếu bằng chứng được rà soát trên **toàn bộ 49 trang text đã index** và đọc các điều khoản liên quan; không suy ra từ việc top-k không tìm thấy. `absence_review.json` lưu phạm vi trang, toàn bộ trang liên quan đã đọc, keyword scan bao gồm cả cách tìm bỏ khoảng trắng để xử lý lỗi PDF, lý do và hash corpus nguồn. Reviewer là Codex, chưa có xác nhận riêng của người học. Trang scan 27 của gddt không thuộc scope; không kết luận về văn bản dưới luật, registry trực tuyến hoặc ảnh ngoài index.

`protocol.json` ghi cấu hình và tiêu chí chọn trên dev trước khi chạy test. `frozen_retrieval.json` được tạo sau dev, trước test, lưu phương pháp chọn, cấu hình và hash nguồn/câu hỏi. Không điều chỉnh cấu hình theo kết quả test.

Đã chọn Hybrid + rerank bằng dev và chạy test cùng Dense baseline. [Kết quả và review context](../docs/BENCHMARK_DAY7_RESULTS.md) ghi tỷ lệ, thời gian và giới hạn. Chỉ số từ chối của agent chưa được đo do chưa nối LLM sinh câu trả lời.

Năm câu test có đáp án từng được đánh giá trong Day 6. Đây là tập test kế thừa, không phải một tập mới hoàn toàn chưa từng được xem. Bài chạy Day 7 hiện tại chỉ lựa chọn bằng dev; nếu dùng các kết quả test để chỉnh hệ thống sau này, cần tạo test mới để đánh giá độc lập.

Metric ranking giữ gold nguyên vẹn trong một chunk để đối chiếu Day 6. Q07 có evidence hai phần: `context_gold_groups` yêu cầu **cả hai** phần cùng đúng nguồn/trang và có trong context; trường này chỉ dùng cho chấm, không đưa vào retriever. Context Evidence Rate nhờ đó chấm được evidence nhiều chunks mà không sửa định nghĩa ranking Hit@1/Hit@3.

Câu thiếu evidence không nằm trong mẫu số retrieval hoặc context. Trả được 9 chunks cho một câu thiếu evidence không có nghĩa trả lời được câu đó; abstention phải chấm từ câu trả lời/từ chối của agent thật và có nhãn review riêng. Môi trường hiện có embedding và reranker; chưa nối LLM sinh câu trả lời, nên kết quả retrieval không được ghi thành kết quả abstention.

Tái tạo dữ liệu (chỉ khi chủ động tạo lại benchmark, không chạy giữa dev và test):

```powershell
& ./.venv/Scripts/python.exe -B starter/build_day7_benchmark.py
```
