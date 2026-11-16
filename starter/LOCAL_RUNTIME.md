# Day 7 chạy bằng model và index local

Model embedding và Chroma đã được sao chép vào repo Day 7. Thư viện Python đã được sao chép vào `.venv` Day 7 và liên kết `day6_dependencies.pth` đã gỡ. Dữ liệu nguồn Day 6 được giữ nguyên tại thư mục cũ; các query/benchmark ở Day 7 dùng file local tại đây.

| Thành phần | Vị trí trong Day 7 |
|---|---|
| Embedding MiniLM 384 chiều | `starter/.models/paraphrase-multilingual-MiniLM-L12-v2` |
| Code tạo embedding | `starter/local_embeddings.py` |
| Chroma snapshot | `starter/data/day6/chroma` |
| Chunks cho Lexical | `starter/data/day6/chunks.json` |
| Reranker CrossEncoder | `starter/.models/mmarco-mMiniLMv2-L12-H384-v1` |
| Python và thư viện | `.venv/Scripts/python.exe`, `.venv/Lib/site-packages` |
| PDF nguồn | `data/36-vbhn-vpqh.pdf`, `data/luat60.pdf` |
| Manifest và trang text | `data/day6_manifest.json`, `starter/data/day6/pages.jsonl` |
| Benchmark Day 7 | `benchmark/questions.json`: 20 dev + 7 test |

## Chạy thường ngày

Từ thư mục gốc repo Day 7:

```powershell
$py = '.\.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

& $py -B starter/retrieval.py --method dense --query 'Dữ liệu dùng chung là gì?' --top-k 9 --category du_lieu --output starter/results/local-query.json
& $py -B starter/retrieval.py --method rerank --query 'Dữ liệu dùng chung là gì?' --top-k 9 --output starter/results/local-rerank.json
& $py -B -m unittest discover -s tests -v
& $py -m pip check
```

Không cần chạy `--prepare` hoặc mở Day 6 mỗi lần query. Model không tải ngầm lúc truy vấn. Các file lớn và `.venv` được Git bỏ qua; chuyển sang máy khác cần mang theo các artifact hoặc tái tạo/import chúng.

## Import một lần từ Day 6

```powershell
$day6 = 'C:\Khoa\VinUni\Lab6\K5-L3B-Day06-2A202603737-DataIngestion'
& ./.venv/Scripts/python.exe -B starter/import_day6_assets.py --day6-root $day6 --copy-dependencies
```

Importer kiểm tra SHA-256 file embedding/PDF, từ chối ghi đè file khác nội dung, dùng lại snapshot Chroma phù hợp và sao chép các thư viện còn thiếu vào môi trường Day 7 trước khi gỡ liên kết site-packages Day 6. Báo cáo import lưu ở `starter/results/local-assets-import.json`. Việc import cần Day 6 tồn tại; các lần query sau không cần đường dẫn đó.

## Vì sao còn nhắc tới LLM?

Embedding MiniLM biến query/tài liệu thành vectors để tìm đoạn liên quan. Chroma lưu và tìm các vectors. CrossEncoder chấm mức liên quan của cặp query–chunk để xếp lại kết quả. Các thành phần này thực hiện retrieval và tạo context.

LLM sinh văn bản phục vụ phần agent: đọc context, quyết định tìm tiếp, tạo câu trả lời có citation hoặc từ chối khi thiếu bằng chứng. `BENCHMARK.md` yêu cầu chấm riêng phần này. Hiện chưa nối LLM, nên bộ câu thiếu evidence đã có nhưng chưa có số liệu abstention/câu trả lời của agent. Không suy ra từ chối chỉ vì query có điểm retrieval thấp, và không dùng nhãn `answerable` để quyết định kết quả hệ thống.
