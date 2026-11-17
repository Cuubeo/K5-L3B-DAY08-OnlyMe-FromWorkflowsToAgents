# Báo cáo nhóm — Lab 8 LogiX-VN

Tối đa 5 trang ngoài phụ lục. Số liệu lấy từ file trong `src/reports/`, không chép tay từ terminal.

## 1. Thông tin nhóm

- Tên nhóm: OnlyMe
- Thành viên: xem `TEAM.md` (nhóm 1 người, làm một mình toàn bộ các vai)
- Commit chốt (trùng `report/team/decision_adr.md`): <COMMIT_HASH>

## 2. Mục tiêu và cách tiếp cận

Bài toán: xử lý claim hoàn phí vận chuyển của LogiX-VN bằng bốn kiến trúc có cùng chữ ký `run_claim`, rồi chọn kiến trúc ít tự chủ nhất vẫn làm đúng việc. Ranh giới cốt lõi: số tiền do code tính (`compute_compensation`), quyền ghi tiền thuộc về host (`durability.issue_refund`), chữ trong ticket chỉ là dữ liệu người dùng.

Nhóm chỉ có một người nên gộp các vai theo gợi ý nhóm 4 người thành một luồng làm việc tuần tự:

1. CP1: đọc `business_rules.md`, `contracts.md`, `swarm_reference.py`, `durability.py`, `policy.py`, `runtime.py`, `handoff.py`; chạy smoke và cổng host.
2. CP2–CP3: viết workflow trước (ít tự chủ nhất, làm chuẩn), rồi single (bọc cùng logic trong vòng ReAct), cuối cùng orchestrator (thêm handoff + investigator read-only). Ba shape dùng chung khung: đọc claim view → tra đơn → quote → host → `finish()`.
3. CP4: chạy crash suite, viết thêm test riêng cho 3 shape (crash ở cả 3 điểm, approval mượn của claim khác, quét trace).
4. CP5: benchmark 4 shape × 5 seed, ablation R1, viết ADR và báo cáo.

## 3. Giải pháp

**Khung chung cho cả ba shape.** Mở store, đọc claim qua `get_claim_view` (chỉ `claim_id`, `principal_id`, `order_id`, `ticket`, không có `parent_secret`). Claim không tồn tại thì `failed`. Thiếu `order_id` thì `needs_info`, không đoán mã đơn từ ticket. `lookup_order` theo principal của claim; không thấy đơn hoặc sai chủ thì `escalated`. Quote bằng `compute_compensation` trên order row (policy hiện hành, `is_current` và `effective_date <= 2026-11-15`, lấy số lớn hơn khi cả ship và damage cùng đủ điều kiện). Quote 0 thì `denied` và không gọi host. Quote > 0 thì gọi `durability.issue_refund(conn, claim_id, <quote đầy đủ>, crash_at=crash_at)`: host từ chối thì `denied` với `proposal_amount` là quote đầy đủ (host đã ghi `policy_denied`), conflict thì `failed`, chấp nhận thì `resolved`. Kết quả luôn trả qua `common.finish()` để `refund_effects` và `committed_audit_count` lấy từ ledger. `InjectedCrash` được ghi event `crash`, flush trace rồi ném tiếp; mọi exception khác thành `failed` với `exception:<TênLớp>` để `run_claim` không bao giờ ném lỗi ra grader.

| Shape | Đọc gì | Ai quyết định | Model làm gì | Ai gọi host |
| --- | --- | --- | --- | --- |
| A workflow | claim view, order view, quote | Các bước Python cố định | 1 call soạn câu trả lời (prompt chỉ chứa status) | Code của shape |
| B single | như A, thêm `lookup_refund_history` | Vòng `run_react` (tối đa 8 bước); `decide` chỉ chọn read tool | 1 "thought"/bước + 1 draft; ticket đưa vào prompt như dữ liệu | Code sau vòng lặp, dùng quote do tool trả trong vòng |
| C orchestrator | handoff → investigator: `lookup_order`, `lookup_refund_history`, `compute_compensation` | Orchestrator | 1 call plan + 1 draft | Orchestrator, investigator không có write tool |

**Vì sao truyền quote đầy đủ.** Host trừ phần đơn đã được hoàn bởi claim khác (trần theo đơn). Nếu shape tự trừ trước, host trừ thêm lần nữa: T14 (O-515 đã hoàn 30.000, entitlement mới 150.000) sẽ ghi 90.000 thay vì 120.000, và T13 có thể không gọi host nên mất audit `policy_denied`. Single có đọc `lookup_refund_history` nhưng chỉ để ghi trace, không trừ.

**Handoff.** Orchestrator dựng handoff bằng `make_handoff` với `facts={}`, task `verify_order_and_quote` và ba read tool. `sanitize` bỏ mọi key ngoài allowlist, từ chối chuỗi `CANARY_SECRET_`/`parent_secret`/`raw_headers` và write tool. Trace ghi bản handoff đã sanitize, không ghi parent context. Tóm tắt bằng LLM không được dùng thay cho allowlist.

**Trace.** Event: `claim` (id + cờ có order), `lookup_order`/`observation`/`investigator` (order view đã allowlist), `refund_history` (chỉ count và tổng tiền), `quote`, `host` (ok/reason/conflict), `decision`, `crash`. Không ghi ticket, claim row, order row thô, prompt gửi model, message của exception.

## 4. Kết quả

Bộ public, 14 claim × 5 seed (`11,22,33,44,55`) = 70 trial/shape, MockLLM, giá mô phỏng `config/pricing.yaml`, mỗi trial một SQLite mới (`src/reports/benchmark.json`):

| Shape | Pass rate | Pass^5 | Seed min–max | Variance | Cost/success (VND, mô phỏng) | Mean / p95 steps | Model calls/trial |
| --- | ---: | ---: | --- | ---: | ---: | --- | ---: |
| workflow | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 28.80 | 4.43 / 5 | 1.00 |
| single | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 40.12 | 8.93 / 10 | 4.64 |
| orchestrator | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 47.99 | 5.36 / 6 | 2.00 |
| swarm | 0.986 | 0.929 | 0.929–1.000 | 0.000816 | 49.57 | 2.80 / 3 | 3.00 |

- Swarm fail đúng 1 trial: C-002 (T02) seed 55, `status resolved != denied`. Ticket ghi "trễ 5 ngày", order ghi 2 ngày; ở seed chia hết cho 5 swarm tin ticket (khối `REFERENCE_WEAKNESS`).
- Crash safety: `20/20` (`src/reports/crash.json`).
- Ma trận student: `248 passed` (62 test × 4 shape, gồm T11 gọi lại và T12 crash rồi resume). Cổng host `python -m pytest -q`: `111 passed` (54 test gốc + 57 test nhóm thêm trong `tests/test_student_shapes_safety.py`).
- Tự kiểm trên `student_drop/` (40 claim không nhãn × 5 seed = 200 trial/shape, `src/reports/hidden_selfcheck.json`): cả ba shape `error_trials` = 0, `leak_suspect_trials` = 0; status giống hệt nhau giữa 3 shape và giữa 5 seed (denied 95, resolved 90, escalated 10, needs_info 5). Không có nhãn nên không ra pass rate; nhóm rà tay từng claim theo `docs/business_rules.md` và không thấy quyết định sai: ticket nói dối số ngày (C-H01, C-H13, C-H20, C-H40) theo DB; injection (C-H03, C-H04, C-H36) bị bỏ qua; policy cũ/tương lai (C-H07, C-H24) denied; homoglyph (C-H21) dùng cột `order_id`; approval hết hạn/thu hồi/của claim khác/bằng 0/thiếu (C-H08, C-H32, C-H31, C-H09, C-H17, C-H25) denied kèm quote đầy đủ; đơn đã hoàn đủ (C-H26) denied, hoàn phần chênh (C-H30) ghi 62.000; ship + hỏng (C-H11, C-H35) lấy 150.000. Steps trung bình: workflow 4.53, single 9.28, orchestrator 5.50.

Quyết định kiến trúc và lý do: xem `report/team/decision_adr.md`. Phiếu nghiên cứu và ablation: xem `report/team/research_card.md`.

## 5. Khó khăn và cách xử lý

- **Làm một mình.** Bài thiết kế cho nhóm 4–6 người. Cách xử lý: làm tuần tự theo thứ tự mức tự chủ tăng dần (A → B → C), dùng chung một khung xử lý để khi A đúng thì B, C chỉ khác phần điều phối.
- **Bẫy "tự trừ phần đã hoàn".** Đọc `policy.authorize` thấy host đã trừ `already_refunded_vnd`, nên giữ quote đầy đủ; T13, T14 xanh ngay.
- **Bẫy `-k single` khớp cả `test_public_single_run_cases`.** Lệnh `-k single` chạy 242 test thay vì 62; kiểm bằng toàn bộ ma trận (`248 passed`) thay vì tin con số của bộ lọc.
- **Môi trường.** Máy ảo hỗ trợ chỉ có Python 3.10 (smoke báo `Python 3.10.12 quá cũ`) nên chạy trên Windows; máy Windows dùng Python 3.15.2, ngoài dải 3.11–3.13 đề ghi đã kiểm, nhưng smoke, pytest, crash suite và benchmark đều ra đúng số nên giữ nguyên.

## 6. Tổng hợp đóng góp

Chi tiết đóng góp của từng thành viên nằm trong `TEAM.md` (bảng đóng góp) và báo cáo cá nhân `report/team/MSSV_HoTen.md`.

## 7. Hạn chế và hướng cải thiện

MockLLM không phải model sản xuất; latency là `unavailable`. Ngoài ra:

- Corpus public chỉ 14 claim và ba shape đều chạm trần 1.000, nên benchmark public không phân biệt được độ đúng giữa A, B, C; chỉ phân biệt được cost và số bước. Cần bộ hidden 40 claim để kiểm các biến thể như homoglyph, principal lẫn, policy tương lai.
- Single dùng `decide` xác định thay cho model thật, nên con số của nó đo "vòng ReAct có guardrail" chứ không đo một model tự quyết. Với model thật, variance của single gần như chắc sẽ khác 0.
- Kết luận sẽ đổi nếu task có bước song song thật (nhiều nguồn độc lập) hoặc có loại claim mà luật cố định không bao hết.

## 8. Tài liệu tham khảo

- Đề bài và tài liệu trong repo: `README.md`, `docs/business_rules.md`, `docs/contracts.md`, `docs/metrics.md`, `src/lab8/shapes/swarm_reference.py`.
- Kim et al., "Towards a Science of Scaling Agent Systems", arXiv:2512.08296, 2025. https://arxiv.org/abs/2512.08296
