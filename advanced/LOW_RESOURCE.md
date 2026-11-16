# Advanced IPCC: chạy từng phần trên máy 16 GB RAM

Chạy trong thư mục gốc repo Day 7. Dùng Python `.venv` của Day 7 để tránh alias `python3` của Microsoft Store.

```powershell
$py = '.\.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'

# Chỉ xem tiến độ; không nạp model.
& $py -B -m advanced.index --stage status

# Mỗi lần chạy đúng một lượt: tự chọn prepare hoặc embed rồi thoát.
& $py -B -m advanced.safe_run
```

Lặp lại lệnh cuối khi muốn làm tiếp. Chương trình giữ checkpoint và bỏ qua trang/vector đã lưu, không tạo lại toàn bộ index. Nếu index hoàn tất, lệnh chỉ thông báo và thoát. Phần chuẩn bị xử lý tối đa **8 trang/lượt**, dùng tokenizer nhẹ, không dùng PyTorch. Phần embedding xử lý tối đa **16 chunks/lượt**, **batch 1**, nghỉ 0,75 giây giữa chunks. Có thể chọn lượt nhỏ hơn:

```powershell
& $py -B -m advanced.index --stage prepare --limit 4 --max-seconds 15
# Chỉ dùng sau khi toàn bộ 186 trang đã chuẩn bị xong:
& $py -B -m advanced.index --stage embed --limit 2 --max-seconds 5
```

`--max-seconds` giới hạn vòng xử lý, được kiểm tra giữa các trang/chunks. Thời gian khởi động, nạp model và hoàn tất thao tác hiện tại có thể làm tổng thời gian dài hơn. Đây không phải giới hạn cứng của hệ điều hành.

Muốn chạy vài lượt chuẩn bị nhẹ liên tiếp, dùng `--stage prepare --steps 3`. Có nghỉ 10 giây giữa lượt và chỉ một tiến trình con hoạt động tại một thời điểm; `--steps` tối đa 5. Không mở nhiều cửa sổ chạy các lệnh này cùng lúc. File lock dùng chung sẽ từ chối worker thứ hai và tự nhả khóa khi tiến trình thoát, kể cả khi bị ngắt.

## Giới hạn tài nguyên

Cấu hình: [low_resource.json](low_resource.json). Trên Windows, tiến trình dùng một CPU logic, mức ưu tiên `BelowNormal`, một luồng thư viện số học; GPU bị tắt cho các model Advanced. Việc giới hạn CPU là để giảm tải trên máy hiện tại, không dựa vào giả định GPU Quadro hỗ trợ được các model.

- Kiểm tra RAM trống tối thiểu 4 GB ở các điểm kiểm tra. Worker embedding/rerank dừng nếu RSS quan sát vượt 1.800 MB.
- LLM cần tối thiểu 6 GB RAM trống trước khi nạp; sau khi nạp giữ ngưỡng trống 4 GB và RSS tối đa quan sát 4.608 MB.
- Chỉ một model nặng trong mỗi tiến trình. Constructor từ chối model thứ hai. Embedding, rerank và LLM chạy trong ba tiến trình khác nhau, tiến trình trước thoát rồi mới chạy tiến trình sau.
- Giới hạn RAM được kiểm tra tại ranh giới các thao tác, không phải hạn mức cứng trong lúc cấp phát. Không đo nhiệt độ hoặc bảo đảm ngăn sập nguồn. Ảnh Task Manager chưa đủ xác định nguyên nhân sập nguồn; nếu tiếp tục tự tắt dù tải nhỏ, dừng xử lý để kiểm tra nguồn và tản nhiệt.

## Dừng và chạy tiếp

```powershell
# Yêu cầu dừng sau trang/chunk/token đang xử lý.
New-Item -ItemType File -Path advanced/STOP -Force
```

Checkpoint trang được lưu sau từng trang, vector sau từng upsert thành công. Tắt máy đột ngột có thể khiến vector cuối được lưu trước checkpoint; lần sau chương trình đối chiếu ID thực tế trong Chroma để bỏ qua vector đó. Không xóa `advanced/artifacts` hoặc Chroma để chạy lại.

```powershell
# Chỉ xóa file tín hiệu dừng này khi muốn chạy tiếp.
Remove-Item -LiteralPath advanced/STOP -ErrorAction SilentlyContinue
& $py -B -m advanced.safe_run
```

## Retrieval, rerank, LLM: từng câu, từng tiến trình

Chỉ chạy sau khi status index là `success`. Lệnh tạo job dưới đây chỉ lưu câu hỏi và hiển thị trạng thái, chưa nạp model:

```powershell
& $py -B -m advanced.worker --job ipcc-demo --question 'What global warming level was observed in 2011-2020 relative to 1850-1900?'

# Mỗi lệnh hoàn tất một bước và thoát. Có thể nghỉ tùy ý giữa các bước.
& $py -B -m advanced.worker --job ipcc-demo --stage retrieve
& $py -B -m advanced.worker --job ipcc-demo --stage rerank
& $py -B -m advanced.worker --job ipcc-demo --stage answer

# Xem trạng thái, không nạp model.
& $py -B -m advanced.worker --job ipcc-demo
```

Retrieval lấy tối đa 12 candidates, đóng gói tối đa 4 nguồn/3.600 ký tự. Rerank dùng batch 1, tối đa 256 tokens/cặp; có thể cắt bớt văn bản dài. LLM Qwen3-0.6B dùng tối đa 1.024 input tokens, 96 output tokens và ngân sách sinh 30 giây; lưu đúng evidence thực tế sau khi rút gọn. Context nhỏ và timeout có thể làm giảm chất lượng; phải đánh giá bằng dev trước khi chốt cấu hình.

Nếu model yêu cầu tìm thêm, job chuyển về `retrieve`, tối đa hai lần tìm kiếm. `--stage next` thực hiện đúng một bước kế tiếp, không tự chạy tất cả. Lỗi, thiếu RAM, timeout và hết số lần tìm mà chưa trả lời được lưu là `error`, không giả thành câu từ chối đúng. Job lỗi được giữ nguyên; dùng tên job mới nếu thử lại. Trace/câu trả lời nằm trong `advanced/artifacts/jobs/<job>.json`.

Embedding `paraphrase-multilingual-MiniLM-L12-v2` tạo vector cho index và query. Chroma lưu/tìm vector. Hai thành phần này đủ để lấy evidence; LLM chỉ cần khi thực hiện phần sinh câu trả lời, citation và abstention theo benchmark. Không cần nạp LLM trong bước lập index.

## Dữ liệu và giới hạn hiện tại

PDF IPCC có 186 trang; SHA-256 được kiểm tra trong manifest. Index native text, bảng trích xuất và nhãn/caption biểu đồ có provenance trang/bbox. Chưa có vision model để đọc nội dung chỉ tồn tại trong pixel hoặc suy ra giá trị đường cong từ màu ảnh. Bảng tự trích có thể có ô gộp và cần đối chiếu PDF gốc.

Chưa hoàn tất benchmark Advanced, chưa có điểm answer/citation/abstention và chưa có căn cứ công bố bonus 90%. Các bài test phần mềm kiểm tra checkpoint/tài nguyên không thay thế đánh giá câu trả lời trên PDF.
