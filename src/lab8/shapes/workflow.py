"""Shape A — deterministic workflow.

Signature (do not change):

    run_claim(claim_id, *, seed, store_path, crash_at=None) -> RunResult

Fixed Python steps, no model in the decision path:

1. Read the claim through `get_claim_view` (allowlisted columns, no parent_secret).
2. Missing order_id -> `needs_info`. No ledger write.
3. `lookup_order` scoped to the claim's principal. Not visible -> `escalated`.
4. Quote from the order row with `compute_compensation`. Ticket text is never parsed
   for numbers: the delay and the clause come from the DB only.
5. Quote 0 -> `denied`, no issue_refund.
6. Quote > 0 -> `durability.issue_refund(conn, claim_id, <full quote>, crash_at=...)`.
   The host checks approval, per-order cap and idempotency. Host refusal -> `denied`
   (host writes `policy_denied`), conflict -> `failed`, ok -> `resolved`.
7. MockLLM is used once, only to draft the customer reply text.

Trace contract v1: every return path writes `traces/<run_id>.json` through
`lab8.shapes.common.finish`. The trace never holds the ticket, the raw claim row or
the raw order row; only allowlisted views and the quote.
"""

from __future__ import annotations

import sqlite3

from lab8 import durability
from lab8.db import connect
from lab8.durability import InjectedCrash
from lab8.mock_llm import complete
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import compute_compensation, get_claim_view, lookup_order, tool_cost
from lab8.trace import Trace

SHAPE = "workflow"


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))

    def done(status: str, proposal: int, reason: str | None) -> RunResult:
        trace.add("decision", {"status": status, "proposal_amount": int(proposal), "reason": reason})
        return finish(
            conn,
            shape=SHAPE,
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    try:
        # Step 1: allowlisted claim view.
        budget.add_tool(tool_cost())
        claim = get_claim_view(conn, claim_id)
        if not claim["found"]:
            return done("failed", 0, "unknown_claim")
        trace.add("claim", {"claim_id": claim_id, "has_order_id": bool(claim["order_id"])})

        # Step 2: no order id -> ask for it. Never guess it from ticket text.
        if not claim["order_id"]:
            _draft(budget, seed, "needs_info")
            return done("needs_info", 0, "missing_order_id")

        # Step 3: order scoped to the principal on the claim row.
        budget.add_tool(tool_cost())
        order_view = lookup_order(conn, claim["order_id"], claim["principal_id"])
        trace.add("lookup_order", safe_dump(order_view))
        if not order_view["visible"]:
            _draft(budget, seed, "escalated")
            return done("escalated", 0, order_view["reason"])

        # Step 4: code quotes from the order row and current policy.
        budget.add_tool(tool_cost())
        quote = compute_compensation(conn, order_view["order"])
        trace.add("quote", safe_dump(quote))
        proposal = int(quote["amount_vnd"])

        # Step 5: nothing owed -> deny without touching the host.
        if proposal <= 0:
            _draft(budget, seed, "denied")
            return done("denied", 0, quote["reason"])

        # Step 6: the host is the only writer. Full quote, crash_at forwarded.
        try:
            outcome = durability.issue_refund(conn, claim_id, proposal, crash_at=crash_at)
        except InjectedCrash:
            trace.add("crash", {"at": crash_at})
            trace.write()
            raise
        trace.add("host", {"ok": outcome["ok"], "reason": outcome["reason"], "conflict": outcome["conflict"]})

        if not outcome["ok"]:
            status = "failed" if outcome["conflict"] else "denied"
            _draft(budget, seed, status)
            return done(status, proposal, outcome["reason"])

        # Step 7: success. finish() reads the effect and audit count from the ledger.
        _draft(budget, seed, "resolved")
        return done("resolved", proposal, None)
    except InjectedCrash:
        raise
    except Exception as exc:  # run_claim must not raise; record the class only, no payload.
        return done("failed", 0, f"exception:{type(exc).__name__}")


def _draft(budget: Budget, seed: int, status: str) -> None:
    """Reply text only. The prompt carries the decision, not the ticket or any PII."""
    complete(budget, seed=seed, purpose="draft", prompt=f"status={status}")
