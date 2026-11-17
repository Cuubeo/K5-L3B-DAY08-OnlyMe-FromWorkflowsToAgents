"""Group tests for the three student shapes: crash windows, approval binding, trace hygiene.

Run with the host gate: `python -m pytest -q`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab8.db import connect, init_store
from lab8.durability import InjectedCrash, committed_audit_count, get_refund
from lab8.shapes import SHAPES
from tests.conftest import CLAIMS, WORLD

STUDENT_SHAPES = ["workflow", "single", "orchestrator"]
CRASH_POINTS = ["before_effect", "after_effect_before_checkpoint", "after_checkpoint"]


def _store(tmp_path: Path, name: str) -> str:
    path = tmp_path / name
    init_store(path, WORLD, CLAIMS).close()
    return str(path)


@pytest.mark.parametrize("shape", STUDENT_SHAPES)
@pytest.mark.parametrize("point", CRASH_POINTS)
def test_crash_then_resume_pays_once(tmp_path, shape, point):
    store = _store(tmp_path, f"{shape}-{point}.sqlite")
    with pytest.raises(InjectedCrash):
        SHAPES[shape]("C-012", seed=11, store_path=store, crash_at=point)
    result = SHAPES[shape]("C-012", seed=11, store_path=store)
    result_again = SHAPES[shape]("C-012", seed=11, store_path=store)
    conn = connect(store)
    try:
        rows = conn.execute("SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = 'C-012'").fetchone()["n"]
        assert rows == 1
        assert int(get_refund(conn, "C-012")["amount_vnd"]) == 35000
        assert committed_audit_count(conn, "C-012") == 1
    finally:
        conn.close()
    assert result.status == "resolved" and result_again.status == "resolved"


@pytest.mark.parametrize("shape", STUDENT_SHAPES)
def test_borrowed_approval_is_denied_with_audit(tmp_path, shape):
    store = _store(tmp_path, f"{shape}-borrowed.sqlite")
    conn = connect(store)
    # C-001 now points at the approval issued for C-003.
    conn.execute("UPDATE claims SET approval_id = 'A-003' WHERE claim_id = 'C-001'")
    conn.commit()
    conn.close()
    result = SHAPES[shape]("C-001", seed=11, store_path=store)
    conn = connect(store)
    try:
        reasons = [
            json.loads(row["details_json"])["reason"]
            for row in conn.execute(
                "SELECT details_json FROM audit_events WHERE claim_id = 'C-001' AND event_type = 'policy_denied'"
            )
        ]
        assert get_refund(conn, "C-001") is None
    finally:
        conn.close()
    assert result.status == "denied"
    assert result.proposal_amount == 35000  # full quote, not the written amount
    assert "approval_claim_mismatch" in reasons


@pytest.mark.parametrize("shape", STUDENT_SHAPES)
@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: c["claim_id"])
def test_trace_has_no_secret_pii_or_ticket(tmp_path, shape, claim):
    store = _store(tmp_path, f"{shape}-{claim['claim_id']}.sqlite")
    result = SHAPES[shape](claim["claim_id"], seed=55, store_path=store)
    body = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
    assert body["run_id"] == result.run_id and isinstance(body["events"], list)
    blob = json.dumps(body, ensure_ascii=False) + json.dumps(result.as_dict(), ensure_ascii=False)
    for needle in claim["expected"]["forbid_substrings"] + ["CANARY_", "Bearer", claim["ticket"]]:
        assert needle not in blob


@pytest.mark.parametrize("shape", STUDENT_SHAPES)
def test_unknown_claim_fails_without_exception(tmp_path, shape):
    store = _store(tmp_path, f"{shape}-unknown.sqlite")
    result = SHAPES[shape]("C-999", seed=11, store_path=store)
    assert result.status == "failed" and result.proposal_amount == 0
    assert Path(result.trace_path).is_file()
