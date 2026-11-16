# Rà soát môi trường cho bước 2 — 16/11/2026

Đây là bản rà soát ban đầu trước khi triển khai các pipeline bổ sung. Hiện đã có `.venv` Day 7, Underthesea, Hybrid và CrossEncoder rerank; xem [hướng dẫn hiện tại](../starter/RETRIEVAL_METHODS.md) và [kết quả dev](RETRIEVAL_DEV_RESULTS.md). Các mục “cần bổ sung” bên dưới phản ánh thời điểm rà soát ban đầu.

Môi trường sẵn sàng để triển khai và thử Dense + TF-IDF + Hybrid RRF trên CPU. Cần bổ sung phương pháp Hybrid, chương trình so sánh chung và benchmark Day 7 trước khi đánh giá đủ yêu cầu bài lab.

## Môi trường đã kiểm tra

| Thành phần | Kết quả |
|---|---|
| Python dùng để chạy | `Lab6/K5-L3B-Day06-2A202603737-DataIngestion/starter/.venv/Scripts/python.exe`, Python 3.14.10 |
| Kiểm tra dependency | `pip check`: `No broken requirements found.` |
| Torch | `2.15.0+cpu`, chạy trên CPU |
| Embedding | `sentence-transformers==5.7.0`, `transformers==5.23.0` |
| Vector store | `chromadb==1.5.9` |
| Thư viện số | `numpy==2.5.4`, `scipy==1.18.1`, `scikit-learn==1.9.1` |
| Unit tests | 18/18 đạt |

Lệnh `python` mặc định trên PATH trỏ tới Python hệ thống. Kết quả rà soát này áp dụng cho môi trường `$py` ở Day 6; nên dùng đường dẫn đó để chạy lab.

## Dữ liệu và kiểm tra chạy thực tế

- Model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`.
- Vector 384 chiều, chuẩn hóa L2, truy vấn cosine; giới hạn đầu vào model hiện tại là **128 tokens**. Adapter báo lỗi khi query quá dài.
- Collection B `day6_b_c7a6473e1d69`, 401 chunks từ 49 trang của hai nguồn: `dulieu` 182 chunks, `gddt` 219 chunks.
- Toàn bộ dữ liệu trong `starter/data/day6/chunks.json` trùng bản sao Chroma: ID, nội dung, nguồn, trang và metadata.
- Dense và TF-IDF được chạy với cùng câu truy vấn thử trên cùng corpus; cả hai trả top-3 và đóng gói context thành công với budget 2.000 ký tự.
- Dense lọc thành công cả hai category `du_lieu` và `giao_dich_dien_tu`.
- Chi tiết phiên bản và kết quả chạy được lưu tại `starter/results/retrieval-environment-review.json` (file local, được Git bỏ qua).

Các kiểm tra trên xác nhận khả năng chạy. Chất lượng retrieval cần đo bằng evidence trên bộ dev theo `BENCHMARK.md`.

## Ba phương pháp có thể thực hiện

| Phương pháp | Tình trạng code | Nhu cầu môi trường |
|---|---|---|
| Dense | Có `starter/day6_retriever.py`, đã truy vấn model và Chroma thật | Đã đủ |
| Lexical TF-IDF | Có `starter/baseline.py`, đã chạy trên 401 chunks | Python standard library, đã đủ |
| Hybrid Dense + TF-IDF, hợp nhất RRF | Cần triển khai, benchmark riêng | Có thể dùng standard library cùng hai retriever trên |

Chưa cài `rank-bm25`, `underthesea`, `pyvi`. Các gói này chỉ cần xem xét nếu chọn BM25 hoặc thử tách từ tiếng Việt. Với ba phương pháp trong bảng, có thể bắt đầu mà không cài thêm thư viện hoặc tải thêm model. RRF hợp nhất theo thứ hạng để tránh cộng trực tiếp điểm cosine và TF-IDF khác thang đo.

## Các phần cần chuẩn bị để benchmark bước 2

1. Chuẩn bị benchmark Day 7 thật: ít nhất 15 câu dev có đáp án + 2 câu dev thiếu bằng chứng, và 5 câu test có đáp án + 2 câu test thiếu bằng chứng. Lab7 hiện chỉ có các file câu hỏi ví dụ. Day 6 có 15 dev / 5 test; cần chuyển schema và kiểm tra evidence nếu tái sử dụng. Nếu test cũ đã dùng để chỉnh hệ thống thì tạo test mới theo GUIDE.
2. Hiện thực Hybrid RRF và chương trình so sánh ba phương pháp với cùng corpus, câu hỏi, cutoff, metadata và context budget. Nếu bật filter, áp dụng chính sách nhất quán cho các nhánh; TF-IDF starter hiện chưa hỗ trợ filter.
3. Đo Hit@1, Evidence Hit@3, Context Evidence Rate, thời gian và lưu trace trên dev. Chỉ chốt cấu hình bằng dev trước khi đánh giá test. Câu thiếu evidence được báo riêng, không đưa vào mẫu số retrieval hit metrics.

Phần model thật điều phối agent thuộc bước 3 trong GUIDE. Các kiểm tra retrieval local ở bước 2 có thể thực hiện trước khi nối LLM.

## Lệnh kiểm tra trên PowerShell

Chạy ở thư mục gốc repo Day 7:

```powershell
$day6 = 'C:\Khoa\VinUni\Lab6\K5-L3B-Day06-2A202603737-DataIngestion'
$py = Join-Path $day6 'starter\.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'

& $py -B -m pip check
& $py -B starter/day6_retriever.py --day6-root $day6 --prepare --export-chunks starter/data/day6/chunks.json
& $py -B starter/day6_retriever.py --day6-root $day6 --query 'Dữ liệu dùng chung là gì?' --top-k 3
& $py -B -m unittest discover -s tests -v
```
