# Kết nối Day 6 vào Day 7

Nguồn local: `C:\Khoa\VinUni\Lab6\K5-L3B-Day06-2A202603737-DataIngestion`.
Repo nguồn: https://github.com/khoa-asta/K5-L3B-DAY06-LeVietKhoa-2A202603737-DataIngestion.

Adapter `day6_retriever.py` dùng lại index/model của Day 6, với code `LocalEmbedder` và weights hiện đã lưu trong Day 7:

- Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Revision: `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`, vector 384 chiều, chuẩn hóa L2, cosine.
- Mặc định dùng cấu hình đã chọn trên dev Day 6: B, collection `day6_b_c7a6473e1d69`, 401 chunks.
- Đọc model ở `starter/.models/paraphrase-multilingual-MiniLM-L12-v2` và truy vấn Chroma ở `starter/data/day6/chroma`, đều trong Day 7. Không tạo lại embedding tài liệu.
- Giữ ID chunk, nội dung, nguồn, trang và metadata. `score = 1 - distance`.

## Chạy trên PowerShell

Chạy từ thư mục gốc repo Day 7, dùng môi trường Python Day 7 hiện đã có đủ thư viện. Xem [runtime local](LOCAL_RUNTIME.md):

```powershell
$day6 = 'C:\Khoa\VinUni\Lab6\K5-L3B-Day06-2A202603737-DataIngestion'
$py = '.\.venv\Scripts\python.exe'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'

# Import một lần nếu chưa có model/index trong Day 7.
# Máy hiện tại đã import xong; dừng ingestion Day 6 nếu cần import snapshot mới.
& $py -B starter/import_day6_assets.py --day6-root $day6 --copy-dependencies

# Các lần sau: mở lại bản sao đã có và truy vấn bằng embedding thật.
& $py -B starter/day6_retriever.py --day6-root $day6 --query 'Dữ liệu dùng chung là gì?' --top-k 3 --output starter/results/day6-connection.json

# Filter do người dùng chọn, không suy ra từ đáp án benchmark.
& $py -B starter/day6_retriever.py --query 'Dữ liệu dùng chung là gì?' --category du_lieu
& $py -B -m unittest discover -s tests -v
```

`--prepare` có thể chạy lại: kết quả `preparation: "reused"` nghĩa là dùng lại snapshot phù hợp, `"created"` nghĩa là vừa tạo mới. Adapter tiếp tục kiểm tra collection và embedding trước khi báo `status: "connected"`. Snapshot thiếu file hoặc khác cấu hình Day 6 sẽ báo lỗi; dùng `--store-path` mới để tạo snapshot mới. Sao chép HNSW cần Day 6 ngừng ghi trong suốt bước chuẩn bị; SQLite được sao chép bằng backup API ở chế độ chỉ đọc nguồn. Không chạy ingestion đồng thời.

Có thể đặt `DAY6_ROOT` hoặc truyền `--day6-root` khi chuyển máy. Mặc định adapter tìm Day 6 trong thư mục `Lab6` cạnh `Lab7`. GitHub là nguồn mã; clone repo chưa đảm bảo có `.models`, `.chroma` và `.venv`. Nếu dùng máy khác, chuẩn bị các artifact theo `starter/SETUP_LOCAL.md` và pipeline của Day 6 trước. Adapter báo lỗi khi thiếu artifact hoặc model/index không khớp, không tải model ngầm.

## Dùng với agent

Trong chương trình đặt ở `starter/`:

```python
from day6_retriever import Day6Retriever
from agentic import run_agent

retriever = Day6Retriever()
# controller cần hiện thực Controller.decide bằng model thật.
result = run_agent(question, controller, retriever, top_k=9, budget=4000)
```

`Day6Retriever.search(query, filters=..., top_k=...)` trả đúng schema Day 7: `id`, `text`, `source_id`, `source`, `page`, `metadata`, `score`. Trường `source` giữ đường dẫn tương đối theo repo Day 6. Query vượt giới hạn token của model sẽ báo lỗi thay vì cắt âm thầm.

File chunks phục vụ cả lexical và hybrid retrieval. Benchmark Day 7 hiện có 20 dev và 7 test tại `benchmark/questions.json`; xem `benchmark/README.md` và `starter/RETRIEVAL_METHODS.md`. Controller sinh câu trả lời bằng LLM chưa được nối. Các artifact trong `starter/data`, `starter/results`, `.models` và `.venv` được Git bỏ qua; tái tạo/import khi chuyển máy.
