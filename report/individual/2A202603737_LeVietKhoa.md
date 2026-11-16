# Báo cáo cá nhân — Day 7: Retrieval & Context Engineering

**Lê Viết Khoa · MSSV 2A202603737 · lớp K5-L3B / 3B**

**Ngày cập nhật:** 16/11/2026

**Phạm vi báo cáo:** Day 7 có model embedding, Chroma, code và môi trường Python độc lập; đã có **giao diện web local Retrieval Studio**. Phần cơ bản đã chạy 5 cấu hình retrieval trên 20 dev, chốt Hybrid + rerank rồi đánh giá cùng Dense trên 7 test. Context test đã được rà soát với hỗ trợ Codex, chưa có xác nhận riêng của học viên. Advanced dùng IPCC AR6, 186 trang: catalog đầy đủ, demo lexical có nguồn/ảnh trang và Chroma đang được bổ sung theo từng lượt. Đã viết worker Qwen local theo từng bước nhưng chưa chạy đánh giá answer/citation/abstention; không công bố phần này đã đạt benchmark hoặc bonus.

## 1. Dữ liệu và benchmark

### 1.1. Nguồn và phạm vi corpus

Day 7 kế thừa corpus từ [repo Day 6](https://github.com/khoa-asta/K5-L3B-DAY06-LeVietKhoa-2A202603737-DataIngestion), nằm tại `C:\Khoa\VinUni\Lab6\K5-L3B-Day06-2A202603737-DataIngestion`.

| Source ID | Tài liệu / snapshot | Trang PDF vật lý | Trang index | Chunks B | Category |
|---|---|---:|---|---:|---|
| `gddt` | Luật Giao dịch điện tử, 36/VBHN-VPQH; 13/03/2026 | 27 | 1–26 | 219 | `giao_dich_dien_tu` |
| `dulieu` | Luật Dữ liệu, 60/2024/QH15; 30/11/2024 | 23 | 1–23 | 182 | `du_lieu` |
| **Tổng** | **Hai tài liệu** | **50** | **49 trang nội dung** | **401** | |

Trang 27 của `gddt` là scan không có text trích xuất nên bị loại khỏi index và không tính vào 49 trang. Số trang là thứ tự vật lý PDF. Chunks giữ nguyên ID, text, source ID, nguồn, trang và metadata Day 6.

Nguồn công bố là Cổng Thông tin điện tử Chính phủ. Quyền sử dụng được kê khai trong [manifest đã sao chép vào Day 7](../../data/day6_manifest.json): văn bản pháp luật công khai, ghi nguồn cơ quan công bố, không sao chép bình luận biên tập bên thứ ba. PDF nguồn đã có ở `data/36-vbhn-vpqh.pdf` và `data/luat60.pdf` trong Day 7. Bài thực nghiệm đánh giá truy xuất trong các snapshot đã lưu.

| File nguồn trong repo Day 6 | SHA-256 theo manifest |
|---|---|
| `data/36-vbhn-vpqh.pdf` | `8f547592b11193e314452c02d83e6ce1be4e320f977e8a15360ff0a0ff46d120` |
| `data/luat60.pdf` | `d77fc7c76798697a4ee95c2e72d2c942d473f3a32947d752e51de398237af446` |

### 1.2. Embedding, vector store và kết nối

| Thành phần | Cấu hình thực tế |
|---|---|
| Embedding model | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Embedding revision | `e8f8c211226b894fcb81acc59f3b34ba3efd5f42` |
| Vector | 384 chiều, chuẩn hóa L2; query/document dùng cùng model |
| Giới hạn query embedding | 128 tokens; vượt giới hạn được báo lỗi |
| Vector store | Chroma PersistentClient, cosine, HNSW approximate nearest neighbors |
| Collection | `day6_b_c7a6473e1d69`, 401 chunks/vectors |
| Chunking kế thừa | B: theo đoạn văn, giới hạn 96 tokens/chunk, overlap 0 |
| Index signature | `c7a6473e1d692588e72b733a59c01bcfd57cfc14513e74f5fb43894e3b10662e` |
| Snapshot Day 7 | `starter/data/day6/chroma` |
| Corpus Lexical | `starter/data/day6/chunks.json`, trùng toàn bộ chunks trong snapshot Chroma |

[Adapter](../../starter/day6_retriever.py) dùng code [local_embeddings.py](../../starter/local_embeddings.py) và model tại `starter/.models/paraphrase-multilingual-MiniLM-L12-v2`, cùng Chroma đều trong Day 7. Thư viện đã có trong `.venv` Day 7; đã gỡ liên kết `day6_dependencies.pth`. Kiểm tra với đường dẫn nguồn Day 6 không tồn tại vẫn truy vấn thành công. [Importer](../../starter/import_day6_assets.py) sao chép và kiểm tra SHA-256 một lần; query thường ngày không cần mở Day 6 hoặc chạy `--prepare`. Khi nhập snapshot mới cần dừng ingestion Day 6 để giữ index nhất quán.

### 1.3. Benchmark dev/test và tiêu chí evidence

Nguồn câu hỏi hiện tại là [benchmark/questions.json](../../benchmark/questions.json) trong Day 7, gồm 27 câu. Giữ query/split/evidence của 20 câu Day 6, thêm UDEV01–UDEV05 và UTEST01–UTEST02 thiếu bằng chứng. Đã chạy **20 dev** cho năm cấu hình và **7 test** cho Dense + Hybrid rerank được chọn trên dev.

| Nhóm | Hiện có | Đã đánh giá trong Day 7 | Phần cần bổ sung |
|---|---|---|---|
| Dev có đáp án | 15 câu Day 6 | Đã chạy cho năm cấu hình | Đủ số lượng |
| Dev thiếu evidence | 5 câu mới | Đã chạy retrieval cho năm cấu hình | Chưa chấm từ chối của agent |
| Test có đáp án | 5 câu kế thừa Day 6 | Đã chạy Dense và rerank sau freeze | Không phải test mới hoàn toàn chưa từng được xem |
| Test thiếu evidence | 2 câu mới | Đã chạy retrieval cho Dense và rerank | Chưa chấm từ chối của agent |

Benchmark đã đủ số lượng câu hỏi theo yêu cầu. Năm test có đáp án từng được đánh giá tại Day 6; đây là test kế thừa. Cấu hình Day 7 chọn bằng dev, không điều chỉnh theo test. Nếu dùng kết quả test này để chỉnh tiếp, cần test mới để đánh giá độc lập. Các file `data/example_*.json` chỉ minh họa schema.

Mỗi câu có đáp án giữ ID, query, expected answer, source ID, trang và evidence. Evaluator chọn split trước khi chấm; retrieval chỉ nhận query/filter, không nhận gold, expected answer hoặc nhãn answerable. Bảy câu thiếu evidence hỏi về lệ phí cụ thể, độ dài RSA, URL API, số liệu cấp phép hiện tại, hotline/email, khung phạt tiền và mẫu/hồ sơ đăng ký. [Hồ sơ rà soát](../../benchmark/absence_review.json) lưu phạm vi toàn bộ 49 trang index, keyword scan và điều khoản liên quan đã đọc. Nhãn do Codex hỗ trợ, `human_confirmed=false`, không suy ra chỉ từ top-k không tìm thấy.

Quy tắc đo:

- **Hit@1:** số câu có evidence hợp lệ trong chunk hạng 1 / số câu có đáp án chạy thành công.
- **Evidence Hit@3:** số câu có evidence hợp lệ trong top-3 / cùng mẫu số.
- **Evidence Hit@9:** tương tự trên top-9; là chỉ số bổ sung.
- **Context Evidence Rate:** số câu có đủ evidence trong context thực tế / cùng mẫu số. Nếu có `context_gold_groups`, phải có đủ mọi fragment trong một nhóm thay thế, đúng nguồn/trang.

Ranking evidence phải đúng source ID/trang, nằm trọn trong một chunk sau chuẩn hóa NFC và gộp whitespace, giữ quy tắc Day 6. Các câu thiếu evidence loại khỏi mẫu số retrieval/context. Không có lỗi thực thi: mẫu số chất lượng dev là 15 và test là 5, dù số query thực chạy mỗi cấu hình là 20/7.

**Q07 có gold trải qua hai chunks**, corpus chỉ phủ **14/15 câu bằng một chunk**. Ranking giữ Q07 trong mẫu số và tính miss theo metric chặt. Context đã khai báo trước lần chạy mới hai fragment bắt buộc qua `context_gold_groups`; chỉ tính đạt khi cả hai có trong context. Quy tắc giống nhau cho mọi phương pháp: rerank đạt context 15/15 dù ranking Hit@3 là 14/15.

| Fingerprint của lần so sánh | SHA-256 |
|---|---|
| File chunks dùng chung | `2008855359d92b64ee842fcf56f6429a64a5ce3c0ba9681f88fe03073139cf82` |
| Tập dev mới đã chọn | `da5c16d5c7ba88e6bab88851886aa51d5a2ef8e381ef3474831730946ef18c3b` |
| Tập test mới đã chọn | `16c732872db4235238664719258c00e343e795f8242bdeabf8c9cc7b05670e8f` |

## 2. Retrieval và thử nghiệm

### 2.1. Phương pháp và giả thuyết

**Dense:** embedding query, tìm vector gần nhất bằng Chroma cosine, trả top-9. Điểm là `1 - distance`; điểm lớn hơn nghĩa là gần hơn. Category filter do người dùng chỉ định được truyền vào truy vấn vector.

**Lexical:** thử `tfidf-syllable` dùng regex `\w+` trên văn bản NFC/lowercase, và `tfidf-word` dùng Underthesea 9.5.0 trước khi lowercase/token hóa, ví dụ `chủ_thể`, `dữ_liệu`. Hai cấu hình dùng cùng corpus, linear term frequency, `idf = log((1+N)/(1+df)) + 1`, chuẩn hóa L2 và cosine. Không thay stopword hoặc sửa OCR giữa hai cấu hình.

**Hybrid:** Dense và TF-IDF theo từ lấy tối đa 30 candidates mỗi nhánh, cùng query/filter. Hợp nhất bằng `RRF(id) = sum(1/(60 + rank))`, không cộng trực tiếp điểm khác thang đo. Union có tối đa 60 IDs; trả top-9, tie xử lý theo ID.

**Retrieval + rerank:** lấy top-30 từ RRF, CrossEncoder chấm từng cặp query–chunk và chọn lại top-9. Model `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, revision `1427fd652930e4ba29e8149678df786c240d8825`, CPU, batch size 8, giới hạn cặp 512 tokens. Score là logit, trace giữ điểm retrieval và thứ hạng trước rerank. Không có cặp bị truncation trong đợt 15 câu dev này.

TF-IDF âm tiết và tách từ là hai cấu hình của cùng phương pháp Lexical. Dense, Lexical, Hybrid, Retrieval + Rerank là bốn pipeline khác nhau.

| Cấu hình | Vai trò / giả thuyết của phép thử | Thay đổi |
|---|---|---|
| Dense | Baseline kế thừa index thật Day 6 | Query embedding + Chroma top-9 |
| TF-IDF âm tiết | Đối chiếu khả năng khớp từ khóa, điều khoản | Lexical cosine |
| TF-IDF tách từ | Kiểm tra gộp từ tiếng Việt có giúp xếp hạng không | Chỉ thay tokenizer so với TF-IDF âm tiết |
| Hybrid RRF — cải thiện 1 | Kết hợp độ phủ semantic và từ khóa | 30 candidates mỗi nhánh, RRF constant 60 |
| Hybrid + rerank — cải thiện 2 | Chấm tương tác query–chunk để đưa evidence lên đầu | CrossEncoder xếp lại 30 candidates Hybrid |

Hybrid và rerank đồng thời là phương pháp mới và cấu hình thử cải thiện. Giữ cả kết quả không tăng điểm của tách từ. Thay top-k đơn thuần không tính là phương pháp mới.

### 2.2. Cấu hình chung và kết quả dev

Các cấu hình dùng cùng 401 chunks, 20 câu dev, query gốc, top-k=9 và budget=4.000 ký tự. Benchmark chính không bật filter ở mọi phương pháp. Filter được kiểm tra chức năng riêng với hai category; chưa benchmark chất lượng có/không filter trên cùng bộ dev. [Protocol](../../benchmark/protocol.json) ưu tiên Hit@3, Hit@1, Context Evidence Rate rồi độ trễ. [Freeze](../../benchmark/frozen_retrieval.json) chốt rerank lúc 12:04:47 ngày 16/11/2026 (UTC+7), sau dev và trước test, lưu hash code/câu hỏi/cấu hình; evaluator kiểm tra hash trước test.

| Cấu hình / split | Top-k / candidates / filter | Hit@1 | Evidence Hit@3 | Evidence Hit@9 | Context Evidence Rate | TB/query | API model |
|---|---|---:|---:|---:|---:|---:|---:|
| Dense / dev | 9 / Chroma / không filter | 10/15 (66,67%) | 12/15 (80,00%) | 13/15 (86,67%) | 13/15 (86,67%) | 33,0 ms | 0 USD |
| TF-IDF âm tiết / dev | 9 / toàn corpus / không filter | 10/15 (66,67%) | 12/15 (80,00%) | 12/15 (80,00%) | 12/15 (80,00%) | 2,6 ms | 0 USD |
| TF-IDF tách từ / dev | 9 / toàn corpus / không filter | 9/15 (60,00%) | 12/15 (80,00%) | 12/15 (80,00%) | 12/15 (80,00%) | 4,1 ms | 0 USD |
| Hybrid RRF / dev | 9 / 30 mỗi nhánh / không filter | 11/15 (73,33%) | 12/15 (80,00%) | 13/15 (86,67%) | 14/15 (93,33%) | 31,2 ms | 0 USD |
| Hybrid + rerank / dev | 9 / rerank 30 / không filter | 13/15 (86,67%) | 14/15 (93,33%) | 14/15 (93,33%) | 15/15 (100,00%) | 1.132,8 ms | 0 USD |
| Dense baseline / test | 9 / Chroma / không filter | 3/5 (60,00%) | 4/5 (80,00%) | 4/5 (80,00%) | 4/5 (80,00%) | 31,3 ms | 0 USD |
| Hybrid + rerank / test | 9 / rerank 30 / không filter | 5/5 (100,00%) | 5/5 (100,00%) | 5/5 (100,00%) | 5/5 (100,00%) | 1.162,4 ms | 0 USD |

Context budget gồm ID/nguồn/trang/text. Mỗi phương pháp dev chạy đủ 20/20, baseline và rerank test chạy đủ 7/7; tổng 100 lượt dev và 14 lượt test, không lỗi. Số liệu từ [dev summary](../../starter/results/benchmark-day7-local/dev/summary.json) và [test summary](../../starter/results/benchmark-day7-local/test/summary.json), không từ mock. Câu thiếu evidence đã chạy nhưng không tính vào mẫu số chất lượng.

Thời gian trung bình tính cả 20 query dev hoặc 7 query test, gồm retrieval/context; loại thời gian khởi tạo suite (dev 95,3 giây, test 26,9 giây trong lượt này). Chưa đo nhiều lần, độ lệch chuẩn, điện năng hoặc phần cứng. Model/corpus xử lý local, không gọi API model trả phí.

### 2.3. Kết quả trước/sau và ứng viên cấu hình

Tách từ thay đổi top-3 ở **13/15 câu**, nhưng Hit@3 vẫn 12/15; Hit@1 giảm từ 10/15 xuống 9/15. Trên tập hiện tại chưa có bằng chứng tách từ cải thiện TF-IDF. Hybrid vẫn dùng nhánh theo từ như cấu hình triển khai trước lần benchmark; chưa thử thêm Hybrid với nhánh âm tiết.

Hybrid tăng Hit@1 thêm 1 câu so với Dense, từ 66,67% lên 73,33%; Hit@3 giữ nguyên. Rerank tăng Hit@1 thêm 2 câu so với Hybrid và tăng Hit@3 từ 12/15 lên 14/15. Thời gian tăng từ khoảng 31,2 ms lên 1.132,8 ms/query. Context Q07 được chấm đủ hai fragment, nên context đạt 14/15 ở Hybrid và 15/15 ở rerank.

**Hybrid + rerank đã được chốt bằng dev trước test**, theo protocol đã công bố. Test đạt Hit@1/Hit@3/Context Evidence Rate 5/5, so với Dense 3/5, 4/5, 4/5. Test còn nhỏ và có phần kế thừa Day 6; không suy rộng thành độ chính xác toàn bộ hệ thống hay điểm agent. Chưa điều chỉnh pipeline theo lỗi test Q19 của Dense.

Top-k=3 và top-k=9 đã được kiểm tra khả năng chạy. Hit@3/Hit@9 trong bảng tính từ cùng ranking top-9; chưa có thí nghiệm chất lượng riêng chứng minh đổi tham số top-k từ 3 sang 9 luôn cải thiện hệ thống.

### 2.4. Phân tích lỗi dev và ví dụ có nguồn

| Query | Quan sát và nguyên nhân / giả thuyết | Thay đổi đã thử, kết quả | Phần cần thử tiếp |
|---|---|---|---|
| Q02 — ai được tiếp cận và sử dụng dữ liệu mở? | Evidence `37b62112af57b4179d21bb345ae2edc0`, `dulieu`, trang 2, ở hạng 14 nhánh Dense, 22 nhánh Lexical; có trong candidate pool nhưng xếp thấp | RRF xếp evidence hạng 12, ngoài top-9. CrossEncoder đưa lên hạng 3; Hit@3 chuyển miss thành hit, Hit@1 vẫn miss | Đối chiếu các đoạn gần chủ đề; chưa sửa corpus/gold để tăng điểm |
| Q09 — chủ thể dữ liệu là ai? | Chunk `d65bb4594fd5c8d8ab123d53ef02ebbf`, `dulieu`, trang 2: hạng 1 ở TF-IDF âm tiết, hạng 3 sau tách từ. Gộp `chủ_thể`, `dữ_liệu` làm đổi từ vựng/trọng số; PDF còn lỗi cách chữ cần kiểm tra | Ablation tokenizer làm giảm Hit@1 ở câu này, cả hai vẫn hit top-3. Hybrid và rerank đưa evidence về hạng 1 | So sánh Hybrid dùng nhánh âm tiết; kiểm tra chuẩn hóa cách chữ bằng quy tắc chung |
| Q07 — ba loại dịch vụ tin cậy | Gold ở trang 14 `gddt` chia giữa hai chunks | Rerank trả phần đầu hạng 1 (`af1e338ab0f031d9f308f068f9cf66fd`), phần còn lại hạng 4 (`10bd9eaa10ed23cc344e23801492c0ad`). Ranking strict vẫn miss; context mới yêu cầu đủ cả hai và tính đạt | Đã triển khai/chấm context nhiều fragment; chưa đổi chunking hoặc định nghĩa ranking |

Ví dụ thành công **Q04**: query hỏi về giá trị pháp lý của thông tin trong thông điệp dữ liệu. Cả năm cấu hình trả chunk `ce6ef0d824ff2042666a754f9f16004c`, nguồn `gddt`, trang 4, hạng 1; chunk chứa Điều 8 và khớp evidence. Đây là ví dụ retrieval có nguồn; chưa có câu trả lời do agent sinh hoặc nhãn citation của agent cho câu này.

## 3. Agent, context và đánh giá câu trả lời

### 3.1. Tool, vòng lặp và điều kiện dừng

[Khung agent](../../starter/agentic.py) có giao thức `Controller.decide` và `Retriever.search`, action search/answer, giới hạn lượt tìm, context tích lũy, kiểm tra ID citation trong context và trả abstain khi thiếu citation hợp lệ hoặc hết lượt tìm.

Mặc định trong khung cơ bản là `max_searches=4`, `top_k=3`, `budget=800`. Đây là mặc định code, chưa phải cấu hình agent đã chạy thực nghiệm. Với corpus pháp luật, demo hiện trả evidence/context và chưa dùng LLM để sinh câu trả lời; top-k giao diện mặc định 9. Không lấy hành vi mock trong tests làm kết quả agent thật.

Advanced đã có [LocalAgent](../../advanced/agent.py) gọi Qwen3-0.6B local và [worker](../../advanced/worker.py) lưu trạng thái `retrieve → rerank → answer`. Model chọn action `answer`, `abstain` hoặc `search`; tối đa hai lần tìm. Mỗi bước chạy trong một tiến trình riêng để không giữ đồng thời embedding, CrossEncoder và Qwen trong RAM. Nút agent trên web chỉ được mở khi index IPCC hoàn tất; chưa có trace chạy Qwen thực tế hoặc nhãn đánh giá câu trả lời.

Các retriever Dense, Lexical và Hybrid có giao diện search; [suite](../../starter/retrieval.py) chạy cả pipeline rerank và trả trace kết quả/context. Benchmark gọi trực tiếp từng phương pháp theo cấu hình cố định, chưa đo việc LLM tự chọn tool, số lượt search hay điều kiện dừng thực tế.

### 3.2. Context và xử lý lỗi

`pack_context` duyệt theo ranking, loại ID trùng, thêm nguyên chunk nếu cả block ID/nguồn/trang/text vừa budget. Chunk không vừa bị bỏ; chưa nén, ghép hàng xóm, thêm multimodal evidence hoặc viết lại query. Trace giữ `context_ids` và số ký tự thực tế.

Filter hỗ trợ `category=du_lieu` hoặc `category=giao_dich_dien_tu`. CLI dùng filter người dùng chỉ định; tùy chọn `--use-question-filters` dùng filter đã có trong câu hỏi. Không tạo filter từ gold. Hai nhánh Hybrid dùng cùng filter trước hợp nhất.

Thiếu artifact, snapshot/model không khớp, query rỗng, top-k/filter không hợp lệ hoặc lỗi model/store đều được báo. Evaluator ghi `status=error`, loại lỗi và thông báo; có lỗi thì CLI trả exit code khác 0. Reranker tải ở bước setup, truy vấn nạp local; không âm thầm thay bằng điểm giả/model khác.

### 3.3. Tình trạng đánh giá agent

| Cấu hình / split | Tool use của LLM | Số lượt gọi | Grounded answer 0/1/2 | Citation hợp lệ / câu có citation | Abstention / từ chối nhầm |
|---|---|---|---|---|---|
| Agent / dev | Chưa chạy agent thật | Chưa đo | Chưa có nhãn | Chưa có câu trả lời để chấm | Đã có 5 câu thiếu evidence, chưa chấm abstention |
| Baseline agent / test | Chưa chạy | Chưa đo | Chưa có nhãn | Chưa đánh giá | Chưa đánh giá |
| Agent cấu hình được chọn / test | Retrieval đã chốt/chạy; chưa nối LLM | Chưa đo agent | Chưa có nhãn | Chưa đánh giá | Đã có 2 câu thiếu evidence, chưa chấm abstention |

| Query ID | Loại câu / bằng chứng | Tool call và kết quả hiện tại | Câu trả lời / citation / nhãn agent |
|---|---|---|---|
| Q04 | Có đáp án, `gddt`, trang 4 | Retrieval trực tiếp trả evidence hạng 1 ở năm cấu hình | Chưa sinh/chấm câu trả lời agent |
| Q02 | Có đáp án, lỗi xếp hạng ban đầu | Rerank đưa evidence từ RRF hạng 12 lên hạng 3 | Chưa sinh/chấm câu trả lời agent |
| Q07 | Có đáp án, gold nhiều chunks | Hai phần evidence ở hạng 1 và 4; strict metric vẫn miss | Chưa sinh/chấm câu trả lời agent |
| UDEV01–05, UTEST01–02 | Đã bổ sung 7 câu thật, có absence review | Đã có trace retrieval, tách khỏi mẫu số hit/context | Chưa sinh câu trả lời nên chưa đánh giá abstention |

Đã đọc 5 context test có đáp án cho mỗi cấu hình theo rubric 0/1/2: Dense có phân bố **1/0/4**, rerank **0/0/5**. Q19 Dense thiếu ngoại lệ đăng ký trong nội bộ tổ chức nên mức 0; các trường hợp mức 2 có đủ evidence và nguồn/trang. Nhãn nằm ở [test_context_review.json](../../benchmark/test_context_review.json), reviewer Codex, `human_confirmed=false`. Hai câu test thiếu evidence cũng được đối chiếu context: đoạn nói về phí không đủ suy ra tiền phạt; quy định đăng ký không cung cấp mã mẫu đơn/hồ sơ. Chưa có nhãn answer/citation/abstention của agent vì chưa nối LLM.

## 4. Môi trường, kiểm tra và tái lập

### 4.1. Môi trường đã dùng

| Thành phần | Phiên bản / vị trí |
|---|---|
| Hệ điều hành / Python | Windows, Python 3.14.10 |
| Python Day 7 | `.venv/Scripts/python.exe` trong repo Day 7 |
| Thư viện runtime | Đã sao chép vào `.venv/Lib/site-packages` Day 7, đã gỡ `day6_dependencies.pth` |
| PyTorch | `2.15.0+cpu` |
| Sentence Transformers / Transformers | `5.7.0` / `5.23.0` |
| Chroma / NumPy | `1.5.9` / `2.5.4` |
| Tách từ | `underthesea==9.5.0`, `underthesea_core==3.3.2` |
| Reranker | Safetensors local, revision ghi tại phần 2.1 |

Các mốc kiểm tra: 31 tests phần cơ bản đã đạt; sau bổ sung Advanced là 42 tests; web bổ sung 11 kiểm tra cho HTTP, validation, chạy một tác vụ, timeout và checkpoint. Tích hợp cơ bản trước đây dùng embedding, Chroma, Underthesea và CrossEncoder thật: năm cấu hình × hai category = **10/10 trường hợp đạt**, mỗi trường hợp trả top-9 đúng filter, điểm hữu hạn và ranking giảm dần; rerank giữ kết quả trong candidate pool. Standalone check xác nhận query hoạt động khi đường dẫn Day 6 giả lập không tồn tại và mọi module nền nạp từ Day 7. Mock chỉ kiểm tra hợp đồng code, không tạo số liệu chất lượng retrieval. Các lượt thử web thực tế được lưu riêng trong `demo/artifacts/verification.json`.

Lần chạy toàn bộ sau khi hoàn thành web đạt **53/53 tests**, không có lỗi/failure. Chín smoke cases qua server HTTP thật cũng thành công; chi tiết thời gian, RAM và phạm vi kiểm chứng nằm ở [WEB_VERIFICATION.md](../../docs/WEB_VERIFICATION.md). Đây là kiểm chứng chức năng, không thay thế benchmark chất lượng hay review câu trả lời.

### 4.2. Lệnh chạy PowerShell

Chạy từ thư mục gốc repo Day 7; mở PowerShell mới cần khai báo lại biến:

```powershell
$py = '.\.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'

# Máy hiện tại đã có model, Chroma và thư viện trong Day 7.
# Nếu cần import một lần trên máy mới, xem starter/LOCAL_RUNTIME.md.

# Khởi động giao diện web; giữ terminal mở và truy cập URL được in ra.
& $py -B -m demo.server
```

Các lệnh sau là lựa chọn riêng; dừng tác vụ web trước khi dùng, không dán chạy cả dãy:

```powershell
# Xem tiến độ IPCC, không nạp model:
& $py -B -m advanced.index --stage status
```

```powershell
# Chạy đúng một lượt xử lý rồi thoát, tự lưu checkpoint:
& $py -B -m advanced.safe_run
```

Mở **http://127.0.0.1:8765**. Kịch bản demo đầy đủ, thay cổng, dừng/chạy tiếp và cách xuất trace nằm ở [DEMO_WEB.md](../../docs/DEMO_WEB.md). Có thể chạy `./start_demo.ps1` nếu execution policy cho phép; lệnh Python không yêu cầu thay chính sách hệ thống.

Các lệnh dùng Python cụ thể để tránh alias `python3` Microsoft Store trên Windows. Không cần đọc lại Day 6. Các lệnh benchmark cấu hình cũ được ghi trong [BENCHMARK_DAY7_RESULTS.md](../../docs/BENCHMARK_DAY7_RESULTS.md); chúng từng nạp nhiều thành phần và không phải đường chạy mặc định cho máy hiện tại. Không ghi đè freeze, không sửa hệ thống theo test rồi dùng lại test như đánh giá độc lập. Giao diện đọc artifact benchmark đã lưu thay vì tự chạy lại toàn bộ benchmark.

### 4.3. Code và artifact đối chiếu

| Nội dung | Đường dẫn |
|---|---|
| Adapter Day 6 / Dense top-9 | [day6_retriever.py](../../starter/day6_retriever.py), [dense_retrieval.py](../../starter/dense_retrieval.py) |
| TF-IDF hai chế độ | [lexical_retrieval.py](../../starter/lexical_retrieval.py), [baseline.py](../../starter/baseline.py) |
| Hybrid / rerank | [hybrid_retrieval.py](../../starter/hybrid_retrieval.py), [rerank_retrieval.py](../../starter/rerank_retrieval.py) |
| CLI chung / evaluator | [retrieval.py](../../starter/retrieval.py), [compare_retrieval.py](../../starter/compare_retrieval.py) |
| Benchmark, rà soát thiếu evidence | [questions.json](../../benchmark/questions.json), [absence_review.json](../../benchmark/absence_review.json) |
| Protocol và cấu hình đã chốt | [protocol.json](../../benchmark/protocol.json), [frozen_retrieval.json](../../benchmark/frozen_retrieval.json) |
| Metrics test / trace | [summary.json](../../starter/results/benchmark-day7-local/test/summary.json), [dense-traces.json](../../starter/results/benchmark-day7-local/test/dense-traces.json), [rerank-traces.json](../../starter/results/benchmark-day7-local/test/rerank-traces.json) |
| Review context test | [test_context_review.json](../../benchmark/test_context_review.json) |
| Import và kiểm tra runtime độc lập | [local-assets-import.json](../../starter/results/local-assets-import.json), [standalone-check.json](../../starter/results/standalone-check.json) |
| Setup / dependency bổ sung | [setup_retrieval.py](../../starter/setup_retrieval.py), [requirements-retrieval.txt](../../starter/requirements-retrieval.txt) |
| Cấu hình và metrics | [summary.json](../../starter/results/benchmark-day7-local/dev/summary.json) |
| Trace Dense | [dense-traces.json](../../starter/results/benchmark-day7-local/dev/dense-traces.json) |
| Trace TF-IDF | [tfidf-syllable-traces.json](../../starter/results/benchmark-day7-local/dev/tfidf-syllable-traces.json), [tfidf-word-traces.json](../../starter/results/benchmark-day7-local/dev/tfidf-word-traces.json) |
| Trace Hybrid / rerank | [hybrid-traces.json](../../starter/results/benchmark-day7-local/dev/hybrid-traces.json), [rerank-traces.json](../../starter/results/benchmark-day7-local/dev/rerank-traces.json) |
| So sánh tokenizer từng câu | [segmentation-comparison.json](../../starter/results/benchmark-day7-local/dev/segmentation-comparison.json) |
| Kiểm tra tích hợp | [retrieval-integration.json](../../starter/results/retrieval-integration.json) |
| Revision / hash model | [artifact.json](../../starter/.models/mmarco-mMiniLMv2-L12-H384-v1/artifact.json) |
| Hướng dẫn / kết quả mới | [LOCAL_RUNTIME.md](../../starter/LOCAL_RUNTIME.md), [RETRIEVAL_METHODS.md](../../starter/RETRIEVAL_METHODS.md), [BENCHMARK_DAY7_RESULTS.md](../../docs/BENCHMARK_DAY7_RESULTS.md) |
| Giao diện và server local | [index.html](../../demo/static/index.html), [app.js](../../demo/static/app.js), [server.py](../../demo/server.py) |
| Worker web, khóa tài nguyên | [worker.py](../../demo/worker.py), [safety.py](../../advanced/safety.py), [low_resource.json](../../advanced/low_resource.json) |
| Demo, kiểm tra và trace mới | [DEMO_WEB.md](../../docs/DEMO_WEB.md), [smoke.py](../../demo/smoke.py), `demo/artifacts/tasks`, `demo/artifacts/verification.json` |

Artifact trong `starter/data`, `starter/results`, `.models`, cache và `.venv` được Git bỏ qua, tồn tại trên máy hiện tại. Khi chia sẻ repo cần cung cấp artifact được phép chia sẻ hoặc tái tạo theo lệnh và nguồn Day 6 đã dẫn. Chưa có bộ `reviews.json` của agent Day 7.

### 4.4. Sản phẩm demo web và giới hạn của phép trình diễn

**Retrieval Studio** gồm bốn mục: Retrieval cơ bản; So sánh & benchmark; Advanced IPCC; Hướng dẫn demo. HTTP server dùng thư viện chuẩn Python, frontend HTML/CSS/JavaScript không cần cài Node/framework. Server chỉ bind `127.0.0.1`; model nạp ở worker khi người dùng chủ động chạy. POST cần token của phiên và đúng origin local. Chỉ một tác vụ tại một thời điểm, dùng chung khóa OS với CLI Advanced. Tiến trình được giới hạn một CPU logic, ưu tiên BelowNormal; worker nặng có RAM guard và checkpoint.

| Chức năng | Hành vi trình diễn |
|---|---|
| Retrieval cơ bản | Năm cấu hình, top-k 3/5/9, filter hai category, context budget 1.000/2.000/4.000 |
| Evidence / nguồn | Thứ hạng, score, ID, source, trang, text; mở đúng PDF/trang vật lý |
| Context / trace | Context thực tế, IDs được dùng, sao chép context, tải JSON và xem lại lịch sử |
| So sánh tokenizer | Cùng query/corpus/filter/budget, hiển thị terms và top evidence cho hai TF-IDF |
| Benchmark | Đọc summary dev/test đã lưu, không gọi model hoặc tạo metrics giả |
| IPCC lexical | Tìm trên catalog 4.455 chunks; filter text/table/figure, page/bbox, text evidence, ảnh trang và PDF gốc |
| IPCC embedding | Chạy hữu hạn 2/8/16 chunks, cập nhật số vectors thực tế, yêu cầu dừng và cho phép tiếp tục |
| IPCC agent | Khóa khi index chưa đủ; sau đó chạy đúng một bước retrieve/rerank/answer mỗi lần bấm |

Profile web giảm tải: candidate-k 12, RRF constant 60, rerank batch 1 và tối đa 256 tokens/cặp. Profile benchmark đã lưu vẫn là candidate-k 30, batch 8, tối đa 512 tokens/cặp. Web không sửa các file Python trong `starter` đã freeze và không thay số liệu benchmark. Chưa đánh giá chất lượng toàn bộ profile web trên dev/test; kết quả một câu demo không thay thế benchmark.

Đã kiểm tra frontend JavaScript bằng bộ phân tích cú pháp, đối chiếu các DOM IDs, API HTTP/static/PDF và các worker thật. Kết nối trình duyệt tự động không khả dụng trong phiên kiểm tra, nên **chưa xác nhận trực quan giao diện trên trình duyệt và các thao tác click**. Người demo cần mở URL để kiểm tra hiển thị trên máy. Không dùng hạn chế này để khẳng định đã có ảnh/screenshot kiểm chứng.

Đo thực tế từng lượt web: TF-IDF âm tiết 0,347 giây/22,4 MB RAM đỉnh; Dense 28,679 giây/1.228,2 MB; Hybrid 32,398 giây/1.238,1 MB; Hybrid + rerank 79,170 giây tổng, worker rerank 1.241,1 MB. So sánh hai tokenizer mất 13,173 giây; IPCC figure/table lexical khoảng 0,4–0,5 giây, RAM đỉnh khoảng 41 MB. Thời gian bao gồm nạp thư viện/model, khác `mean_ms` của benchmark; không suy rộng một query thành kết quả chất lượng toàn hệ thống.

## 5. Thử thách nâng cao

### 5.1. Tài liệu, quyền sử dụng và phạm vi index

**Đang triển khai riêng với IPCC AR6 Synthesis Report, 186 trang**, nguồn local `data/IPCC_AR6_SYR_FullVolume.pdf`, SHA-256 `f5258cf9434fd8887848e334197b6397ad6e107a6f06ddf21a00b2bce3f5dee6`. Corpus cơ bản 49 trang giữ nguyên. Đã trích native text/layout trên toàn bộ tài liệu, bảng tự phát hiện và nhãn/caption hình; có ảnh trang phục vụ đối chiếu. Không coi nhãn biểu đồ trích từ PDF là khả năng đọc mọi nội dung ảnh: giá trị chỉ thể hiện bằng pixel/màu/đường cong vẫn chưa được tự động diễn giải.

Nguồn: [bản IPCC chính thức](https://www.ipcc.ch/report/ar6/syr/downloads/report/IPCC_AR6_SYR_FullVolume.pdf), Climate Change 2023: Synthesis Report. Trang bản quyền PDF giữ quyền của IPCC, có điều kiện cho trích dẫn ngắn kèm nguồn. File PDF, full extracted text và ảnh trang giữ local/Git-ignored; chưa xuất bản lại toàn bộ corpus.

Catalog gồm **2.647 text units, 40 bảng tự trích, 26 figure units**, chia thành **4.455 chunks**. 169 trang có units; 17 trang còn lại không có native text hoặc chỉ tiêu đề/nhãn/số trang ngắn, được kê trong `manifest.json`. Phạm vi này không phải một bộ benchmark đã chấm đúng mọi bảng/ảnh. Text có bbox khối, bảng có bbox trích xuất, figure dùng bbox trang chính và danh sách `source_pages` cho hình/caption trải nhiều trang; chưa có crop sát mọi chi tiết hình. Chunk theo tokenizer embedding, cửa sổ 88 tokens, overlap 12; thêm label và kiểm tra không vượt 126 tokens. ID, SHA nguồn và signature xác định catalog để chạy tiếp không trộn corpus.

### 5.2. Xử lý theo từng phần và demo nâng cao

Sau khi máy bị sập nguồn lúc xử lý, pipeline Advanced được chia thành các lượt hữu hạn, checkpoint từng trang và từng vector. Chroma còn 1.088 vectors đã lưu trước khi bị ngắt. Cấu hình máy hiện tại dùng một CPU logic, một luồng tính toán, batch embedding 1; tối đa 8 trang hoặc 16 embeddings/lượt, có nghỉ và kiểm tra RAM. Embedding, reranker và Qwen3-0.6B được tách thành các tiến trình riêng, khóa chống chạy trùng và từ chối nạp model thứ hai trong một tiến trình. Không kết luận nguyên nhân sập nguồn từ ảnh Task Manager.

Đã chuẩn bị catalog 186/186 trang, gồm 4.455 chunks. Lượt kiểm chứng tiếp tục chỉ tạo thêm 2 embeddings, đưa Chroma lên **1.090/4.455 vectors**, batch 1, RAM đỉnh đo bởi Windows 1.250,5 MB; không nạp reranker hoặc LLM. Chi tiết mốc chạy và các phần còn lại: [PROGRESS.md](../../advanced/PROGRESS.md).

Sau đó, lượt kiểm chứng nút index qua web bổ sung đúng hai vectors nữa: **tiến độ hiện tại 1.092/4.455**, còn 3.363 vectors. Task mất 29,787 giây gồm worker startup; RAM đỉnh worker index 1.233,2 MB. Các số này là mốc kiểm chứng trên máy, không phải bảo đảm cho mọi lần chạy.

Hướng dẫn chạy tiếp: [LOW_RESOURCE.md](../../advanced/LOW_RESOURCE.md); checkpoint và tiến độ thực tế nằm trong `advanced/artifacts/index`, xem bằng `python -B -m advanced.index --stage status`. Mốc 42 tests trước web gồm 11 kiểm tra mới cho resume, giới hạn context, khóa worker, ngưỡng RAM và citation alias; sau bổ sung web đạt 53/53. Chúng không phải kết quả benchmark Advanced. Model Qwen đã tải local nhưng chưa có kết quả đánh giá answer/citation/abstention. Chưa hoàn tất benchmark theo nhóm và chưa có cơ sở công bố tỷ lệ đạt hoặc bonus.

Demo web đã truy xuất **Figure SPM.7 (PDF trang 43)** và **Table SPM.1 (PDF trang 37)** bằng TF-IDF trên catalog, có source ID, page/bbox, text evidence và liên kết PDF/ảnh trang. Chức năng này hoạt động độc lập với việc Chroma chưa đủ vector; giao diện ghi rõ chưa sinh answer. Schema/layout bảng có thể chứa ô gộp; PDF gốc là nguồn đối chiếu.

Qwen3-0.6B dùng local, float32/CPU, input tối đa 1.024 tokens, output tối đa 96 tokens, ngân sách vòng sinh 30 giây, tối đa hai lần tìm. Worker kiểm tra RAM trống tối thiểu 6 GB trước nạp LLM và 4 GB sau nạp; ngưỡng RSS quan sát 4.608 MB. Embedding/rerank giữ ngưỡng RSS quan sát 1.800 MB. Giới hạn kiểm tra giữa thao tác không phải quota RAM/thời gian cứng trong lúc cấp phát. Lỗi, timeout, citation alias không hợp lệ hoặc hết số lần tìm được ghi là lỗi; không thay bằng câu trả lời hay abstention giả.

### 5.3. Benchmark Advanced và phần chưa đạt

Benchmark IPCC chưa được xây đủ và chưa chạy đánh giá độc lập. Kế hoạch là dev ít nhất 15 câu đủ evidence + 3 thiếu evidence, chọn cấu hình bằng dev; freeze trước test. Test ít nhất 30 câu, phân loại chính theo bảng dưới. Mỗi câu cần đáp án, evidence nguồn/trang/bbox hoặc ô bảng/nhãn hình và review từ PDF; pipeline chỉ nhận câu hỏi, không nhận gold/nhãn answerable.

| Nhóm test | Số lượng tối thiểu theo yêu cầu | Kết quả hiện tại |
|---|---:|---|
| Bảng | 6 | Chưa chạy benchmark |
| Ảnh/sơ đồ | 5 | Chưa chạy benchmark |
| Biểu đồ | 5 | Chưa chạy benchmark |
| Multi-hop từ ít nhất hai trang | 4 | Chưa chạy benchmark |
| Text | 4 | Chưa chạy benchmark |
| Thiếu bằng chứng | 6 | Chưa chạy benchmark |
| **Toàn bộ** | **30** | **Chưa có tỷ lệ đạt** |

Không sử dụng retrieval hit làm điểm trả lời Advanced. Cần review mọi câu test, giữ lỗi/timeout trong mẫu số và đạt ít nhất 27/30 khi dùng test 30 câu mới đủ ngưỡng 90%; hiện **chưa có cơ sở công bố bonus**. Các khoảng trống quan trọng còn lại là hoàn tất vector index, benchmark/nhãn độc lập, kiểm chứng Qwen thực tế, và giải pháp cho nội dung hình chỉ có pixel nếu benchmark yêu cầu.

## 6. Kết luận và phần cần hoàn thành tiếp

Phần retrieval đã có bốn pipeline, năm cấu hình, benchmark đủ 27 câu và runtime độc lập trong Day 7. Hybrid + rerank đạt 14/15 Evidence Hit@3 và context 15/15 trên dev; sau chốt, test đạt 5/5 ở các chỉ số so với Dense Hit@3 4/5. Tách từ không tự động cải thiện TF-IDF. Context Q07 được chấm đủ hai phần, tách biệt với metric ranking một chunk. Web local đã tích hợp demo, context/trace và IPCC lexical theo từng lượt. Corpus pháp luật chưa sinh answer bằng LLM; Advanced đã có code gọi Qwen nhưng chưa chạy đánh giá. Việc trả chunks cho câu thiếu evidence không được tính là agent từ chối đúng.

| Yêu cầu tiếp theo | Trạng thái hiện tại |
|---|---|
| Benchmark đủ ít nhất 4 câu thiếu evidence | Đã bổ sung 5 dev + 2 test; có hồ sơ rà soát, chờ người học xác nhận nhãn |
| Agent dùng LLM thật, tool call và câu trả lời có nguồn | Advanced đã có worker theo từng bước và Qwen local; chưa chạy đánh giá câu trả lời |
| Chấm context nhiều đoạn, answer, citation, abstention | Context đã chấm, có review test Codex; chưa có nhãn answer/citation/abstention của agent thật |
| Chốt bằng dev rồi đánh giá baseline và cấu hình chọn trên test | Đã thực hiện; 5 test có đáp án kế thừa Day 6, không coi là test mới hoàn toàn |
| Demo sản phẩm | Đã có web local, hướng dẫn và 9 smoke cases qua HTTP thật; chưa có browser visual QA |
| Thử thách nâng cao | Catalog 186 trang, lexical PDF có nguồn/ảnh; Chroma 1.092/4.455; chưa hoàn tất benchmark Advanced |

Code, kiểm tra và bản thảo báo cáo được thực hiện với hỗ trợ của Codex. Báo cáo ghi kết quả tự động quan sát được, không xác nhận thay người học các nhãn thủ công chưa có.
