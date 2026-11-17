# Báo cáo cá nhân — 2A202604102_BuiPhuocAnh

Đổi tên file theo quy tắc `MSSV_HoTen.md`, ví dụ `20241234_NguyenVanAn.md`.

## 1. Thông tin thành viên

- Họ tên: Bùi Phước Anh
- MSSV: 2A202604102
- Email: cuubui2004@gmail.com
- GitHub: Cuubeo

## 2. Phần việc phụ trách

Nhóm một người nên phụ trách toàn bộ: ba shape `workflow`, `single`, `orchestrator`; handoff của orchestrator; ghi tiền an toàn khi gọi lại và khi crash; benchmark, ablation; ADR, research card, báo cáo nhóm.

## 3. Đóng góp cụ thể

- Commit chính: <COMMIT_HASH>.
- `src/lab8/shapes/workflow.py`: các bước Python cố định, quote từ order row, gọi `durability.issue_refund` với quote đầy đủ và `crash_at`.
- `src/lab8/shapes/single.py`: vòng `run_react` tối đa 8 bước với `decide` có trạng thái, chỉ chọn read tool; sau vòng lặp code mới gọi host.
- `src/lab8/shapes/orchestrator.py`: handoff qua `make_handoff` (facts rỗng, 3 read tool), investigator read-only, orchestrator là nơi duy nhất ghi.
- Test thêm: `src/tests/test_student_shapes_safety.py` (57 test).
- Quyết định kỹ thuật: (1) chọn workflow làm shape chấm hidden vì cùng độ đúng mà rẻ nhất; (2) không ghi ticket nguyên văn vào trace dù ticket không chứa secret, vì ticket là dữ liệu người dùng có thể chứa PII hoặc injection; (3) exception chỉ ghi tên lớp; (4) không trừ phần đã hoàn trong shape, để host tự trừ.

## 4. Bằng chứng

- Lịch sử commit theo checkpoint: CP1 `724cb85` (TEAM.md); CP2+CP3 `b5a797e` (ba shape); CP4 <CP4_HASH> (test an toàn + crash.json); CP5 <CP5_HASH> (benchmark, ablation, báo cáo).
- `python -m pytest -q -m student -o addopts=` → `248 passed`.
- `python -m pytest -q` → `111 passed`.
- `python -m lab8.crash_test --count 20 --out reports/crash.json` → `crash_safety 20/20`.
- `src/reports/benchmark.json`: workflow pass 1.000, pass^5 1.000, cost/success 28.80; run id ví dụ `R-workflow-C-014-s55`.

## 5. Công cụ AI đã dùng

- Claude (Anthropic): đọc đề và code starter, gợi ý cấu trúc ba shape, viết nháp test và báo cáo.
- Cách tự kiểm tra: chạy lại toàn bộ cổng host, ma trận student, crash suite và benchmark; đối chiếu từng số trong ADR với `src/reports/benchmark.json` và `crash.json`; tự đọc lại `policy.authorize` để hiểu vì sao phải truyền quote đầy đủ; mở trace mẫu để chắc không có ticket, `parent_secret`, SĐT, địa chỉ.
- <BỔ SUNG nếu dùng công cụ khác>

## 6. Tự đánh giá

<TỰ VIẾT: phần nào bạn hiểu chắc, phần nào còn mơ hồ (ví dụ vì sao checkpoint đơn lẻ không thay được ledger), nếu làm lại bạn sẽ đổi gì.>
