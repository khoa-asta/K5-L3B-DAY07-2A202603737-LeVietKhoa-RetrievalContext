# Dense retrieval Day 7 — top-k = 9

`dense_retrieval.py` triển khai phương pháp Dense cho bước 2 trong GUIDE, kế thừa model và index B đã chọn của Day 6.

1. Tạo embedding query bằng MiniLM multilingual local, vector 384 chiều, chuẩn hóa L2.
2. Truy vấn Chroma cosine trên bản sao collection `day6_b_c7a6473e1d69` (401 chunks). Chroma dùng HNSW approximate nearest neighbors theo cấu hình Day 6.
3. Lấy **top-9 mặc định**, cho phép thay bằng `--top-k` để thử nghiệm.
4. Nếu có `--category`, truyền metadata filter vào Chroma ngay khi tìm vector. Category do người dùng cung cấp; không lấy từ đáp án hoặc gold.

## Chạy trên PowerShell

Chạy ở thư mục gốc repo Day 7:

```powershell
$day6 = 'C:\Khoa\VinUni\Lab6\K5-L3B-Day06-2A202603737-DataIngestion'
$py = '.\.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'

# Máy hiện tại đã có model và Chroma trong Day 7. Nếu cần import lần đầu:
& $py -B starter/import_day6_assets.py --day6-root $day6 --copy-dependencies

# Tìm trên toàn bộ corpus, mặc định top-k=9.
& $py -B starter/dense_retrieval.py --query 'Dữ liệu dùng chung là gì?' --output starter/results/dense/top9-all.json

# Tìm trong nhóm Luật Dữ liệu, top-k=9.
& $py -B starter/dense_retrieval.py --query 'Dữ liệu dùng chung là gì?' --top-k 9 --category du_lieu --output starter/results/dense/top9-du-lieu.json

# Tìm trong nhóm Luật Giao dịch điện tử.
& $py -B starter/dense_retrieval.py --query 'Thông điệp dữ liệu là gì?' --category giao_dich_dien_tu --output starter/results/dense/top9-gddt.json

# Mốc so sánh top-k=3 trên cùng câu hỏi.
& $py -B starter/dense_retrieval.py --query 'Dữ liệu dùng chung là gì?' --top-k 3 --output starter/results/dense/top3-all.json
```

Nếu không truyền `--output`, trace được lưu tại `starter/results/dense/latest.json`, ghi đè ở lần chạy sau. Dùng tên output riêng để giữ các thí nghiệm. Không cần cài thêm thư viện.

## Trace và cách dùng lại

Mỗi kết quả có rank, ID chunk, text, nguồn, trang, metadata, cosine distance và `score = 1 - distance`. Điểm lớn hơn tương ứng gần hơn; điểm này không phải xác suất câu trả lời đúng. Trace ghi query gốc, top-k yêu cầu, số kết quả thực tế, filter, model/revision, chữ ký index và thời gian. Nếu số chunk phù hợp ít hơn top-k, trả số có sẵn. `top3_ids` giữ ba ID đầu để hỗ trợ so sánh cùng cutoff sau này.

`retrieval_seconds` gồm embedding query và truy vấn Chroma; `model_and_index_load_seconds` ghi riêng thời gian khởi tạo trong CLI. Query vượt giới hạn 128 tokens của model sẽ báo lỗi. Khi gọi từ Python, có thể dùng lại một retriever cho nhiều query:

```python
from day6_retriever import Day6Retriever
from dense_retrieval import run_dense

retriever = Day6Retriever()
trace = run_dense(retriever, 'Dữ liệu dùng chung là gì?', category='du_lieu')
chunks = trace['results']  # tối đa 9, đã xếp hạng
```

Khi nối với `run_agent`, truyền rõ `top_k=9`; khung agent hiện mặc định top-k=3. Context budget và cách chọn context cần thử riêng; top-9 retrieval không đảm bảo cả 9 chunks sẽ vừa context.

Đây là một phương pháp Dense với các cấu hình top-k/filter. Để đo chất lượng, cần chạy cùng bộ dev thật và báo Hit@1, Evidence Hit@3, thêm Hit@9 nếu cần. Các truy vấn thử chỉ kiểm tra khả năng hoạt động, chưa chứng minh top-9 tốt hơn top-3.
