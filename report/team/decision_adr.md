# Decision record

Điền sau dấu `:` trên cùng dòng, không xóa nhãn. Giảng viên và `python -m lab8.check_submission` (chạy trong `src/`) đọc các dòng này bằng máy. Không đổi tên hay dời file này khỏi `report/team/`.
`Shape chọn` phải là đúng một trong: `workflow`, `single`, `orchestrator`, `swarm`. Đây là shape được chấm cổng hidden.

- Shape chọn: workflow
- Commit hash: <COMMIT_HASH>
- Run id dẫn chứng: R-workflow-C-014-s55, R-workflow-C-002-s55, R-workflow-C-013-s11 (trials trong src/reports/benchmark.json); đối chứng R-swarm-C-002-s55 (fail)
- Pass rate / pass^5 / seed min-max / variance: workflow 1.000 / 1.000 / 1.000–1.000 / 0.000000 trên 14 claim × 5 seed = 70 trial (swarm: 0.986 / 0.929 / 0.929–1.000 / 0.000816)
- Cost per success (mô phỏng, VND): workflow 28.80; single 40.12; orchestrator 47.99; swarm 49.57
- Crash safety: 20/20 (src/reports/crash.json)
- Secret leak / approval bypass: 0 / 0 trên bộ public (mọi trial pass nên không có chuỗi cấm trong trace/kết quả và không có refund khi approval_ok = false; thêm tests/test_student_shapes_safety.py quét trace 3 shape × 14 claim)

Ví dụ một dòng đã điền: `- Shape chọn: workflow`, `- Crash safety: 20/20 (src/reports/crash.json)`.

## Vì sao shape này

Trên cùng corpus public (14 claim C-001…C-014), cùng seed `11,22,33,44,55`, cùng MockLLM, cùng `config/pricing.yaml` và cùng evaluator (`src/reports/benchmark.json`, `controlled_variables`), ba shape nhóm viết đều đạt pass rate 1.000, pass^5 1.000, variance 0. Khi độ đúng ngang nhau, nhóm chọn shape **ít tự chủ nhất**: workflow có cost/success thấp nhất (28.80 VND so với 40.12 của single, 47.99 của orchestrator, 49.57 của swarm), ít bước nhất trong nhóm có trace đầy đủ (mean 4.43, p95 5) và chỉ có 1 model call/trial, dùng để soạn câu trả lời. Bài toán claim là tuần tự (đọc claim → tra đơn → tính quote → gọi host), mọi quyết định có thể viết thành luật trong code, nên không có bước nào cần model chọn hướng đi. Ít chỗ cho model can thiệp nghĩa là ít bề mặt cho injection kiểu "ignore policy" hay ticket nói dối số ngày trễ (T02, T06, T09).

## Có đáng đổi lấy multi-agent không

Không, với dữ liệu hiện có. Single và orchestrator không tăng pass rate (đã 1.000) nhưng tăng cost/success thêm 39% và 67% so với workflow. Swarm vừa đắt nhất vừa có variance khác 0 (fail T02 ở seed 55 vì tin số ngày trong ticket). Nếu một shape multi-agent chỉ nhỉnh pass rate một chút mà cost và variance cao hơn, nhóm vẫn giữ workflow, vì sai lệch về tiền là lỗi nặng hơn chênh vài chục VND chi phí mô phỏng.

Quyết định sẽ đảo lại khi: (1) bộ hidden có loại claim mà luật cố định không bao hết, cần đọc hiểu ngôn ngữ tự do để lấy dữ kiện (ví dụ phân loại loại khiếu nại), và workflow tụt dưới 0.75 trong khi single/orchestrator giữ được; (2) task trở nên song song được, ví dụ một claim phải kiểm nhiều nguồn độc lập (nhiều đơn, nhiều nhà vận chuyển), khi đó investigator chạy song song có thể đáng chi phí; (3) dùng model thật mà chi phí token thấp hơn nhiều so với lỗi do luật cứng bỏ sót.

## Trace và bằng chứng

Trace (`src/traces/<run_id>.json`, ghi qua `lab8.trace.Trace` và `common.finish`) ghi các event: `claim` (chỉ `claim_id` và cờ `has_order_id`), `lookup_order` (order view đã allowlist: order_id, status, delay_days, shipping_fee_vnd, paid_vnd, damage_verified, carrier, hoặc chỉ `reason` khi không thấy đơn), `quote` (amount, reason, clause_ids, parts), `host` (ok, reason, conflict của `issue_refund`), `decision` (status, proposal_amount, reason) và `crash` khi có crash cố ý. Single ghi thêm `react_step`/`observation`/`loop`; orchestrator ghi `handoff` đã qua `make_handoff`/`sanitize` và `investigator`.

Cố ý **không** ghi: nguyên văn ticket (dữ liệu người dùng, có thể chứa SĐT/địa chỉ hoặc chuỗi injection), claim row thô (có `parent_secret`, `raw_headers`, `approval_id`), order row thô (có SĐT, địa chỉ, tên hàng, ghi chú nội bộ), và prompt gửi MockLLM. Exception chỉ ghi tên lớp, không ghi message, để không vô tình kéo dữ liệu vào trace. Trace nằm đúng chỗ scanner quét (`trace_path` và thư mục `traces/`); shape không ghi file nào khác và không in ra stdout. Nếu trace nằm ngoài chỗ scanner quét được thì không chứng minh được nó sạch, nên grader fail-closed là đúng.

## Giới hạn

MockLLM không phải model sản xuất: nó cố định theo seed, không thật sự "hiểu" ticket, nên số pass của single/orchestrator ở đây phản ánh code bao quanh model hơn là năng lực model. Chi phí là mô phỏng theo `config/pricing.yaml`, không phải hóa đơn API. Latency để `unavailable`. Bộ public chỉ có 14 claim; kết luận chưa được kiểm trên 40 claim hidden. Không sửa JSON nào cho đủ 0.75.
