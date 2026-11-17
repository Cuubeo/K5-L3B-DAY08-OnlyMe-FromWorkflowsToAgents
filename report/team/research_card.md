# Research card

File này nằm cố định ở `report/team/research_card.md`; `python -m lab8.check_submission` đọc cột "Nhóm điền" bằng máy.

Phần này nối tiếp phần mini research ở buổi lý thuyết (slide 62–63). Chọn **một** câu R1–R4, điền 6 dòng, rồi biến nó thành **một ablation** chạy được trong lab: giữ nguyên model (MockLLM), tool, seed, corpus và giá, chỉ thay đổi một biến.

| Câu | Nguồn (thư viện tham khảo, slide 68–69) | Câu hỏi gợi ý cho lab |
| --- | --- | --- |
| R1 · Scaling | Google Research 2026, *Towards a Science of Scaling Agent Systems* | Task claims chủ yếu tuần tự hay song song được? Dự đoán thêm investigator sẽ làm pass rate và cost/success thay đổi thế nào. |
| R2 · Failure taxonomy | MAST, NeurIPS 2025, *Why Do Multi-Agent LLM Systems Fail?* | Các trial fail của swarm (seed 55) thuộc nhóm nào: lỗi giao việc, lệch mục tiêu, hay lỗi kiểm chứng? |
| R3 · Architecture choices | AgentArch, AACL 2026 | Nếu đổi topology mà giữ nguyên mọi thứ khác, biến nào phải cố định để kết luận còn đúng? |
| R4 · Evaluation confounders | EMNLP 2026, *Rethinking Evaluation of MAS Efficiency* | Làm sao chứng minh chênh lệch giữa A/B/C/D là do topology, không phải do prompt, tool hay seed? |

## Phiếu của nhóm

Điền vào cột cuối. Không xóa hai cột đầu.

| Field | Hướng dẫn | Nhóm điền |
| --- | --- | --- |
| CÂU | R1 / R2 / R3 / R4 | R1 · Scaling |
| SOURCE | Paper/blog, năm, URL, loại bằng chứng (benchmark, production report, blog kinh nghiệm) | Kim et al. (Google Research, Google DeepMind, MIT), "Towards a Science of Scaling Agent Systems", arXiv:2512.08296 (12/2025), blog Google Research 28/01/2026: https://arxiv.org/abs/2512.08296 · https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/ . Loại bằng chứng: benchmark có kiểm soát (180 cấu hình agent) |
| CLAIM | Một kết luận gốc của nguồn. Không viết rộng hơn phạm vi paper | Lợi ích của phối hợp multi-agent phụ thuộc tính chất task: giúp task tách song song được, nhưng với task suy luận tuần tự thì mọi biến thể multi-agent được thử đều làm giảm hiệu năng (39–70%); task nhiều tool chịu thiệt nặng từ chi phí phối hợp khi ngân sách cố định |
| BOUNDARY | Model / dataset / setup giới hạn kết luận đó | 3 họ LLM thật, 4 benchmark agentic (tài chính, duyệt web, lập kế hoạch kiểu Plancraft, thực thi workflow), 5 kiến trúc (single + 4 MAS), ngân sách tính toán cố định. Không có MockLLM, không có cổng host chặn ghi tiền như lab này, nên chỉ dùng làm giả thuyết hướng, không chuyển nguyên con số 39–70% sang đây |
| HYPOTHESIS | Nếu đổi shape A→B (hoặc bật/tắt một thành phần), metric X sẽ đổi theo hướng nào, khoảng bao nhiêu | Claims là task tuần tự (claim → đơn → quote → host). Bật tầng orchestrator + investigator (A workflow → C orchestrator) sẽ **không tăng** pass rate (giữ 1.000 trên public) và **tăng** cost/success khoảng +50–70% do thêm model call (plan) và tool call của investigator |
| METHOD | Biến giữ cố định: model, tools, seed, corpus, giá, evaluator. Biến duy nhất được thay đổi: … | Cố định: MockLLM, cùng read tool trong lab8.tools, seed 11,22,33,44,55, corpus data/public_claims.jsonl (14 claim), config/pricing.yaml, evaluator lab8.metrics.trial_pass, mỗi trial một SQLite mới, cùng cổng host durability.issue_refund. Biến duy nhất thay đổi: topology, có hay không tầng orchestrator + investigator read-only (workflow vs orchestrator) |
| FAILURE / METRIC | Một lỗi dự kiến và cách đo nó: pass rate, pass^5, variance, cost/success, leak, bypass | Lỗi dự kiến: overhead phối hợp (thêm bước, thêm call) mà không thêm độ đúng; rủi ro phụ là handoff mang secret qua ranh giới. Đo bằng pass rate, pass^5, seed variance, cost/success, mean steps; leak đo bằng quét CANARY_SECRET_* trong trace (tests/test_student_shapes_safety.py) |

## Kết quả ablation

- Lệnh đã chạy (copy nguyên văn): `python -m lab8.benchmark --shapes workflow,orchestrator --cases data/public_claims.jsonl --seeds 11,22,33,44,55 --out reports/ablation_r1_investigator.json`
- Run id / file report: `src/reports/ablation_r1_investigator.json` (ví dụ R-workflow-C-014-s55, R-orchestrator-C-014-s55); cùng số với `src/reports/benchmark.json`
- Kết quả so với hypothesis (đúng / sai / không kết luận được), kèm số liệu: **Đúng.** Pass rate 1.000 → 1.000, pass^5 1.000 → 1.000, variance 0 → 0 (không tăng độ đúng). Cost/success 28.80 → 47.99 VND (+66.6%), mean steps 4.43 → 5.36, model calls/trial 1.0 → 2.0, tool calls/trial 2.79 → 4.64. Không có leak ở cả hai shape. Hướng khớp với claim của paper (task tuần tự không lợi từ thêm agent), nhưng ở đây pass rate không *giảm* vì code bao quanh model quyết hết, nên chỉ thấy phần chi phí phối hợp
- Giới hạn: MockLLM không phải model sản xuất, latency là `unavailable`. Corpus public chỉ 14 claim, pass rate đã chạm trần 1.000 nên không đo được tác động lên độ đúng; cần bộ hidden hoặc model thật để kiểm chiều đó.

Muốn đi xa hơn một ablation để lấy điểm cộng thì xem [docs/bonus_topics.md](../../docs/bonus_topics.md).
