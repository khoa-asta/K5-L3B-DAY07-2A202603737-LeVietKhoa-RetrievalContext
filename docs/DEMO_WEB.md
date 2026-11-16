# Demo sản phẩm Day 7 — Retrieval Studio

Ứng dụng web local dùng dữ liệu thật trong Day 7: retrieval pháp luật, so sánh tách từ, benchmark đã lưu và khám phá PDF IPCC. Không cần cài Flask/Streamlit/Node.js hoặc tải lại model. Giao diện không tự chạy model khi vừa mở trang.

## 1. Khởi động

Mở PowerShell:

```powershell
cd 'C:\Khoa\VinUni\Lab7\K5-L3B-DAY07-2A202603737-LeVietKhoa-RetrievalContext'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
& .\.venv\Scripts\python.exe -B -m demo.server
```

Mở **http://127.0.0.1:8765** trong Edge/Chrome và giữ PowerShell đang chạy. Server chỉ lắng nghe trên máy hiện tại, không công khai lên Internet. Chạy trực tiếp bằng Python cũng tránh alias `python3` Microsoft Store và không cần thay execution policy của PowerShell.

Có thể dùng `./start_demo.ps1` nếu máy cho phép chạy script. Nếu cổng bị chiếm:

```powershell
& .\.venv\Scripts\python.exe -B -m demo.server --port 8766
```

Khi đó mở http://127.0.0.1:8766. Không mở hai server demo cùng lúc. Dừng server bằng **Ctrl+C** trong cửa sổ đang chạy.

## 2. Kịch bản cơ bản — khoảng 5–8 phút

### A. Retrieval, top-k và nguồn

1. Mở **Retrieval cơ bản**, giữ phương pháp **TF-IDF · âm tiết**.
2. Hỏi **“Dữ liệu dùng chung là gì?”**, top-k **9**, budget **2.000 ký tự**, filter **Tất cả tài liệu**.
3. Bấm **Tìm bằng chứng**. Đây là phương án nhẹ, không nạp embedding.
4. Giới thiệu kết quả: ID chunk, thứ hạng, điểm, tên nguồn, số trang và text. Bấm **Mở PDF** để kiểm tra điều khoản gốc. Số trang là thứ tự vật lý PDF.
5. Đổi top-k thành 3, chạy lại và đối chiếu số kết quả. Điểm TF-IDF là cosine từ vựng, không phải xác suất trả lời đúng.

### B. Metadata filter và context

1. Giữ cùng câu hỏi, đổi filter thành **Luật Dữ liệu**, top-k 9, chạy lại.
2. Kiểm tra mọi kết quả thuộc `source_id=dulieu`, `category=du_lieu` trong tab **Trace JSON**.
3. Mở tab **Context**. Các chunk có nhãn **trong context** là phần thực tế được đóng gói.
4. Đổi budget từ 1.000 thành 4.000, chạy từng lượt và so sánh `context_ids`/độ dài. Không phải toàn bộ top-9 đều vừa budget.
5. Dùng **Sao chép** hoặc **Tải JSON** để lưu evidence/cấu hình. Retrieval hiện trả evidence, chưa sinh câu trả lời pháp lý bằng LLM.

### C. Dense, Hybrid và rerank

Chạy từng phương pháp, đợi hoàn tất trước khi đổi:

| Phương pháp | Điều cần trình bày |
|---|---|
| Dense | MiniLM embedding query, Chroma cosine, metadata filter, top-9 |
| TF-IDF tách từ | Underthesea gộp từ tiếng Việt trước khi tính TF-IDF |
| Hybrid | Dense + TF-IDF theo từ, hợp nhất thứ hạng bằng RRF, không cộng trực tiếp điểm cosine |
| Hybrid + rerank | Chọn candidates Hybrid, thoát worker embedding, nghỉ 10 giây, nạp CrossEncoder trong worker khác |

Lần nạp thư viện/model đầu có thể mất 1–2 phút trên máy hiện tại. Trong lúc chạy, banner hiển thị bước đang thực hiện; các nút chạy khác bị khóa. Giao diện chỉ cho một tác vụ, một CPU logic và batch 1. Không mở terminal chạy benchmark hoặc embedding khác cùng lúc.

**Cấu hình demo khác cấu hình benchmark cũ:** web dùng candidate-k 12, reranker tối đa 256 tokens/cặp, batch 1; benchmark đã lưu dùng candidate-k 30, tối đa 512 tokens/cặp, batch 8. Không dùng một câu demo để công bố chất lượng tương đương benchmark.

### D. So sánh tách từ và benchmark

1. Mở **So sánh & benchmark**. Hỏi “Dữ liệu dùng chung là gì?”, bấm **So sánh hai tokenizer**.
2. Đối chiếu token âm tiết và token có dấu gạch dưới như `dữ_liệu`, rồi xem top evidence. Tách từ có thể đổi ranking, không mặc định cải thiện chất lượng.
3. Phần **Benchmark retrieval đã lưu** đọc JSON thật trong `starter/results/benchmark-day7-local`.
4. Chọn **Dev**: 20 câu thực chạy, chất lượng hit/context tính trên 15 câu có đáp án. Giải thích lựa chọn rerank bằng dev, rồi freeze trước test.
5. Chọn **Test**: 7 câu thực chạy, chất lượng tính trên 5 câu có đáp án; Dense Evidence Hit@3 = **4/5**, rerank = **5/5**. Năm câu này kế thừa Day 6; không gọi đây là bộ test hoàn toàn mới.
6. Nhấn mạnh: retrieval hit và context đủ evidence chưa phải answer/citation/abstention của LLM. Bảy câu thiếu evidence đã có nhãn nhưng chưa được chấm khả năng từ chối của agent.

## 3. Kịch bản Advanced — có thể demo ngay

### A. Đọc tiến độ và khám phá tài liệu

1. Mở **Advanced · IPCC**: tài liệu `IPCC_AR6_SYR_FullVolume.pdf` gồm **186 trang**, catalog **4.455 chunks**. Chroma hiển thị số vectors thực tế đã lưu; tiến độ tự cập nhật.
2. Giữ truy vấn **“Figure SPM.7 demand-side mitigation potential”**, chọn loại **Hình / sơ đồ / biểu đồ**, bấm **Tìm evidence IPCC**.
3. Mở text evidence và bbox. Figure SPM.7 ở **PDF trang 43**; đọc ảnh trang cạnh evidence và mở PDF để kiểm tra chú thích/đơn vị.
4. Đổi sang **“Table SPM.1 emissions reductions 2030”**, chọn loại **Bảng tự trích**. Mở PDF trang **37**, đối chiếu đúng hàng/cột. Bảng trích tự động có thể có ô gộp, không coi text extraction là bảng đã được chấm đúng hoàn toàn.
5. Có thể thử **“Figure 4.6 investment needs”** để minh họa một biểu đồ khác. Bấm nguồn/ảnh của từng kết quả để đổi trang xem trước.
6. Dùng **Tải JSON** để lưu sources, trang vật lý, bbox, unit ID và text thực tế.

Chức năng này dùng **TF-IDF trên toàn bộ catalog đã chuẩn bị**, hoạt động khi Chroma còn đang lập index. Nó tìm native text, bảng và nhãn/caption; không phải vision model đọc mọi pixel của biểu đồ. Chưa sinh answer bằng LLM.

### B. Chạy tiếp embedding bằng lượt nhỏ

1. Ở thanh tiến độ, chọn **2 chunks**.
2. Bấm **Chạy một lượt**. Chương trình chỉ embedding tối đa hai chunks còn thiếu, lưu Chroma/checkpoint rồi thoát.
3. Đợi banner hoàn tất và quan sát số vectors tăng. Nếu gặp RAM guard/lỗi, đọc thông báo; không xóa index hoặc tăng giới hạn RAM tùy tiện.
4. Nếu muốn dừng, bấm **Yêu cầu dừng**. Worker kiểm tra tín hiệu giữa các thao tác; nạp model/thao tác hiện tại có thể cần hoàn tất trước khi dừng. Sau khi worker thoát, bấm **Cho phép chạy tiếp** khi muốn làm tiếp.

Tín hiệu dừng dùng chung `advanced/STOP`. Đóng server khi đang xử lý cũng tạo tín hiệu này và giữ checkpoint. Khởi động lại sẽ thấy banner dừng, cần chủ động cho phép chạy tiếp. Không có vòng chạy nền vô hạn.

## 4. Advanced agent — sau khi index hoàn tất

Khi Chroma đạt **4.455/4.455** và manifest là `success`, nút **Agent theo từng bước** được mở. Hiện index chưa hoàn tất nên UI sẽ khóa nút và giải thích điều kiện; không chạy một bản trả lời giả để minh họa.

Ví dụ câu hỏi: **“What global warming level was observed in 2011-2020 relative to 1850-1900?”**

1. Bấm bước đầu để chạy retrieval, lưu evidence và thoát model embedding.
2. Bấm bước tiếp theo để rerank, lưu kết quả và thoát CrossEncoder.
3. Bấm tiếp để Qwen3-0.6B đọc context, trả action `answer`, `abstain` hoặc yêu cầu tìm thêm.
4. Nếu model yêu cầu tìm thêm, tiếp tục từng bước; tối đa hai lần tìm. Lỗi/timeout/hết budget được lưu là lỗi, không giả thành abstention đúng.
5. Tải trace, kiểm tra câu trả lời và citation theo PDF gốc. Citation có ID hợp lệ chưa đủ chứng minh câu trả lời đúng.

Ngân sách local: tối đa 1.024 input tokens, 96 output tokens, 30 giây vòng sinh, và kiểm tra RAM trước/sau khi nạp. Context nhỏ có thể làm giảm chất lượng. Chưa có benchmark Advanced hay điểm answer/citation/abstention, chưa đủ điều kiện công bố bonus.

## 5. Lưu kết quả và báo cáo

| Artifact | Vị trí |
|---|---|
| Web task, payload, kết quả và log mỗi stage | `demo/artifacts/tasks/<task-id>/` |
| Kết quả smoke test thực tế | `demo/artifacts/verification.json` |
| Checkpoint/corpus/Chroma IPCC | `advanced/artifacts/index/` |
| Agent IPCC từng câu | `advanced/artifacts/jobs/web-<id>.json` |
| PDF và ảnh trang để đối chiếu | `data/IPCC_AR6_SYR_FullVolume.pdf`, `advanced/artifacts/document/pages/` |
| Báo cáo cá nhân | `report/individual/2A202603737_LeVietKhoa.md` |

Có thể mở báo cáo từ thanh bên. Artifact lớn được Git bỏ qua; không chia sẻ toàn bộ PDF/IPCC extracted corpus khi chưa xác định quyền sử dụng. Nguồn IPCC chính thức: https://www.ipcc.ch/report/ar6/syr/downloads/report/IPCC_AR6_SYR_FullVolume.pdf. Phần báo cáo dùng các trích đoạn/nhãn ngắn có ghi nguồn; file đầy đủ giữ local.

## 6. Kiểm tra và xử lý sự cố

```powershell
# Kiểm tra web/API mà không nạp embedding/reranker/LLM
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_demo_web.py -v

# Server phải đang chạy; mỗi lệnh chỉ thử một chức năng thật
& .\.venv\Scripts\python.exe -B -m demo.smoke --case lexical
& .\.venv\Scripts\python.exe -B -m demo.smoke --case ipcc
```

Không dán cả dãy thử model để chạy nền. Khi cần kiểm tra thêm, chọn một `--case`: `word`, `filter`, `compare`, `dense`, `hybrid`, `rerank`, `ipcc-table` hoặc `index`, đợi xong rồi mới chạy case tiếp theo.

| Hiện tượng | Cách xử lý |
|---|---|
| Trình duyệt không mở được địa chỉ | Kiểm tra cửa sổ server còn chạy, URL/cổng đúng và không mở HTML bằng double-click |
| Đang có tác vụ / worker khác | Chờ tác vụ hiện tại; kiểm tra terminal CLI, không khởi chạy song song |
| Nút chạy bị khóa sau khi dừng | Đợi worker thoát rồi bấm Cho phép chạy tiếp |
| Worker bị ngắt lúc tắt máy | Chạy lại server, xem checkpoint; web đánh dấu lượt cũ interrupted, không gọi đó là thành công |
| Query vượt 128 embedding tokens | Rút ngắn câu hỏi; không thay model khác trong index cũ |
| Báo thiếu RAM / RSS vượt ngưỡng | Dừng tác vụ, đóng ứng dụng khác, bắt đầu lại bằng lượt nhỏ; giữ checkpoint |
| Model chưa trả JSON trong budget | Giữ trạng thái lỗi và raw output trong trace; không coi là câu trả lời đúng |
| Ảnh trang chưa có sẵn | Bấm Mở PDF trang tương ứng; UI không tự render hàng loạt |

Việc giới hạn CPU/RAM giúp giảm tải, không xác định hoặc bảo đảm khắc phục nguyên nhân sập nguồn phần cứng. Nếu máy tiếp tục tự tắt ở tải nhẹ, dừng xử lý để kiểm tra nguồn/tản nhiệt.
