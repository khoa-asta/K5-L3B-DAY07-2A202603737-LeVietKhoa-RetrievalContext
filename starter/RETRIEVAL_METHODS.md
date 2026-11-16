# Lexical, Hybrid và Retrieval + Rerank

Các phương pháp dùng chung corpus Day 6 gồm 401 chunks. Mặc định top-k=9, context budget=4.000 ký tự. Model và dữ liệu chạy local; kết quả, trace và lỗi được ghi riêng.

| Tên CLI | Cách tìm và xếp hạng |
|---|---|
| `dense` | Query embedding MiniLM 384 chiều, Chroma cosine |
| `tfidf-syllable` | TF-IDF với token regex theo âm tiết/khoảng trắng tiếng Việt |
| `tfidf-word` | Cùng TF-IDF, thay bằng tách từ Underthesea |
| `hybrid` | Dense + TF-IDF theo từ, hợp nhất bằng RRF |
| `rerank` | Lấy candidates Hybrid, CrossEncoder xếp lại từng cặp query–chunk |

TF-IDF hai chế độ là hai cấu hình ablation của cùng phương pháp Lexical. Dense, Lexical, Hybrid và Retrieval + Rerank là bốn pipeline có cách truy xuất/xếp hạng khác nhau.

## Môi trường và chạy nhanh

Môi trường Day 7 tại `.venv` hiện độc lập: model embedding, Chroma, code và thư viện nền đều được lưu trong Day 7. `day6_dependencies.pth` đã được gỡ sau khi sao chép các thư viện cần dùng. Underthesea 9.5.0 và underthesea_core 3.3.2 được cài tại Day 7. Truy vấn và benchmark thường ngày không cần đọc thư mục Day 6; xem [runtime local](LOCAL_RUNTIME.md).

Chạy từ thư mục gốc repo Day 7:

```powershell
$py = '.\.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'

# Hai cấu hình Lexical để so sánh ảnh hưởng tách từ.
& $py -B starter/retrieval.py --method tfidf-syllable --query 'Chủ thể dữ liệu là ai?' --output starter/results/lexical-syllable.json
& $py -B starter/retrieval.py --method tfidf-word --query 'Chủ thể dữ liệu là ai?' --output starter/results/lexical-word.json

# Hybrid: top-30 mỗi nhánh, RRF rồi lấy top-9.
& $py -B starter/retrieval.py --method hybrid --query 'Dữ liệu dùng chung là gì?' --candidate-k 30 --top-k 9 --output starter/results/hybrid.json

# Hybrid + CrossEncoder rerank: chọn lại top-9 từ 30 candidates đã hợp nhất.
& $py -B starter/retrieval.py --method rerank --query 'Dữ liệu dùng chung là gì?' --candidate-k 30 --top-k 9 --output starter/results/rerank.json

# Metadata filter áp dụng nhất quán cho mọi nhánh.
& $py -B starter/retrieval.py --method hybrid --query 'Dữ liệu dùng chung là gì?' --category du_lieu --output starter/results/hybrid-filtered.json

& $py -B -m unittest discover -s tests -v
& $py -m pip check
```

Trên máy mới, tạo môi trường Day 7 và import artifact Day 6 một lần. Setup cần mạng để tải package/model reranker; import embedding và Chroma dùng file local:

```powershell
$day6 = 'C:\Khoa\VinUni\Lab6\K5-L3B-Day06-2A202603737-DataIngestion'
$day6Python = Join-Path $day6 'starter\.venv\Scripts\python.exe'
& $day6Python -B starter/setup_retrieval.py
$py = '.\.venv\Scripts\python.exe'
& $py -B starter/import_day6_assets.py --day6-root $day6
```

## Chi tiết thuật toán

**Lexical:** giữ dấu tiếng Việt và chuẩn hóa NFC. Chế độ syllable dùng `\w+` và lowercase. Chế độ word dùng `underthesea.word_tokenize(format='text')`, sau đó lowercase và `\w+`; ví dụ `giao dịch`, `dữ liệu` trở thành `giao_dịch`, `dữ_liệu`. Cùng cách xử lý được áp dụng cho tài liệu và query. Không thêm stopword hoặc sửa lỗi OCR giữa hai chế độ để giữ phép so sánh rõ ràng.

Cả hai dùng linear term frequency, `idf = log((1+N)/(1+df)) + 1`, chuẩn hóa L2 và cosine. IDF được fit trên toàn bộ cùng corpus, độc lập với đáp án/gold; khi lọc category, chỉ xếp hạng các chunks đủ điều kiện. Query không khớp từ nào trả danh sách rỗng.

**Hybrid:** mỗi nhánh lấy tối đa `candidate-k` (mặc định 30), cùng query và cùng filter. Mỗi ID duy nhất nhận điểm `sum(1/(60+rank))` từ các nhánh có ID đó. Không cộng trực tiếp cosine Dense với cosine TF-IDF. Union có thể có tới 60 IDs; tie được xử lý theo ID để có kết quả ổn định. Hybrid lexical mặc định dùng chế độ word, lựa chọn này được cố định trước lần benchmark đầu tiên; kết quả dev không được dùng để thay đổi âm thầm pipeline.

**Rerank:** lấy top-30 từ danh sách RRF, chấm từng cặp query–chunk bằng `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, rồi trả top-9 theo logit. Model đa ngôn ngữ có tiếng Việt trong model card, revision cố định `1427fd652930e4ba29e8149678df786c240d8825`, nạp safetensors local, CPU, batch size 8. Giới hạn cặp 512 tokens; trace ghi số cặp bị truncation. Điểm reranker là logit và có thể âm; không diễn giải thành xác suất. Trace giữ `retrieval_score`, `pre_rerank_rank`, các candidates trước rerank và revision để kiểm tra thay đổi thứ hạng.

Nguồn kỹ thuật: [Underthesea](https://pypi.org/project/underthesea/), [model card mMARCO](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1), [CrossEncoder API](https://www.sbert.net/docs/package_reference/cross_encoder/model.html).

## So sánh dev và ảnh hưởng tách từ

Lệnh tái tạo phép so sánh đã chạy:

```powershell
$day6 = 'C:\Khoa\VinUni\Lab6\K5-L3B-Day06-2A202603737-DataIngestion'
& $py -B starter/compare_retrieval.py --questions "$day6\benchmark\questions.json" --split dev --top-k 9 --candidate-k 30 --budget 4000 --output starter/results/retrieval-dev
```

Mặc định không bật filter ở mọi phương pháp để so sánh cùng điều kiện. Nếu muốn dùng filter đã được người tạo câu hỏi cung cấp dựa trên query, thêm `--use-question-filters` và chọn thư mục output mới. Không tạo filter từ gold hoặc expected answer.

Kết quả gồm `summary.json`, trace từng phương pháp và `segmentation-comparison.json` với tokens, top-3 IDs, nhãn hit trước/sau tách từ. Đánh giá chọn split trước khi xử lý nhãn; chỉ truyền query và filter vào retrieval. Trace ghi fingerprint corpus và tập câu được chọn. Lỗi được lưu riêng và làm CLI trả exit code khác 0; không thay bằng kết quả giả.

Lần thử ban đầu trên 15 câu có đáp án nằm ở [báo cáo dev lịch sử](../docs/RETRIEVAL_DEV_RESULTS.md). Bộ mới tại `benchmark/questions.json` có 20 dev (15 có đáp án + 5 thiếu evidence), 7 test (5 có đáp án + 2 thiếu evidence). Xem [benchmark Day 7](../benchmark/README.md); test yêu cầu `--freeze` và chỉ chạy baseline + phương pháp đã chọn trên dev.
