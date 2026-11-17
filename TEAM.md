# Team

## Thông tin nhóm

- Tên nhóm: OnlyMe
- Lớp: L3A
- Repo nhóm: `K5-L3B-DAY08-OnlyMe-FromWorkflowsToAgents` (xem [SUBMISSION.md](SUBMISSION.md))
- URL repo, nhánh nộp, commit chốt: https://github.com/Cuubeo/K5-L3A-DAY08-OnlyMe-FromWorkflowsToAgents, nhánh `main`, commit <COMMIT_HASH>

## Thành viên

Nhóm một người: một thành viên đảm nhận toàn bộ các vai.

| STT | Họ tên | MSSV | Email | GitHub | Vai trò |
| --: | ------ | ---- | ----- | ------ | ------- |
|   1 | Bùi Phước Anh | 2A202604102 | cuubui2004@gmail.com | Cuubeo | Toàn bộ: integration, workflow, single, orchestrator + handoff, ledger/policy/crash, evaluation/report |

Gợi ý chia vai:

- Nhóm 6 người: integration; workflow; single agent; orchestrator; ledger/policy/crash; eval/report.
- Nhóm 4 người: workflow + integration; single; orchestrator + handoff; ledger + evaluation.

## Bảng đóng góp

`python -m lab8.check_submission` đọc bảng này bằng máy: giữ nguyên tiêu đề `## Bảng đóng góp` và các cột. Mỗi người một dòng: commit có nội dung và ít nhất một test đã thêm hoặc sửa.

| Người | Vai | Commit | Test đã thêm hoặc sửa |
| --- | --- | --- | --- |
| Bùi Phước Anh | Toàn bộ (workflow, single, orchestrator, handoff, crash, benchmark, báo cáo) | <COMMIT_HASH> | `src/tests/test_student_shapes_safety.py` (57 test: crash 3 điểm × 3 shape, approval mượn của claim khác, quét trace secret/PII/ticket, claim không tồn tại) |

## Cá nhân

Mỗi thành viên đồng thời tạo một báo cáo riêng trong `report/` theo dạng:

```text
report/team/MSSV_HoTen.md
```

Ví dụ: `report/team/20241234_NguyenVanAn.md`.

## 2A202604102_BuiPhuocAnh

### Phần việc phụ trách

- Toàn bộ bài lab (nhóm một người): ba shape A/B/C, handoff, crash/idempotency, benchmark, ADR, research card, báo cáo.

### Đóng góp cụ thể

- Viết `src/lab8/shapes/workflow.py`, `single.py`, `orchestrator.py`.
- Thêm `src/tests/test_student_shapes_safety.py`.
- Sinh `src/reports/benchmark.json`, `crash.json`, `ablation_r1_investigator.json`; viết `report/team/*.md`.

### Bằng chứng

- Ma trận student `248 passed`; cổng host `111 passed`; `crash_safety 20/20`. Chi tiết: `report/team/2A202604102_BuiPhuocAnh.md`.
