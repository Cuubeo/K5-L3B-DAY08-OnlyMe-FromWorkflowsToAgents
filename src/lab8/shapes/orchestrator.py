"""Shape C — orchestrator plus read-only investigators.

1. The orchestrator reads the allowlisted claim view and plans (one MockLLM call).
2. It builds a typed handoff with `lab8.handoff.make_handoff`: request id, claim id,
   task, empty facts, read-only tools. No parent_secret, headers, ticket or claim row.
   `make_handoff` sanitizes against the allowlist and refuses canaries / write tools.
3. `lab8.runtime.run_readonly_investigators` runs the tools named in the handoff:
   lookup_order, lookup_refund_history, compute_compensation. Workers have no write
   registry (`dispatch(worker=True)`).
4. The orchestrator quotes from the investigator's result and alone calls
   `durability.issue_refund` with the FULL quote and `crash_at`. The host does the
   per-order subtraction, approval check and idempotency.
5. The trace records the sanitized handoff and allowlisted investigator output,
   never the parent context. An LLM summary would not be a sanitizer.
"""

from __future__ import annotations

import sqlite3

from lab8 import durability
from lab8.db import connect
from lab8.durability import InjectedCrash
from lab8.handoff import make_handoff
from lab8.mock_llm import complete
from lab8.runtime import run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import get_claim_view, tool_cost
from lab8.trace import Trace

SHAPE = "orchestrator"
INVESTIGATOR_TOOLS = ["lookup_order", "lookup_refund_history", "compute_compensation"]


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
        budget.add_tool(tool_cost())
        claim = get_claim_view(conn, claim_id)
        if not claim["found"]:
            return done("failed", 0, "unknown_claim")
        trace.add("claim", {"claim_id": claim_id, "has_order_id": bool(claim["order_id"])})

        # Orchestrator plan. The ticket goes to the model as data only.
        complete(budget, seed=seed, purpose="plan", prompt=f"ticket_as_data={claim.get('ticket') or ''}")

        if not claim["order_id"]:
            _draft(budget, seed, "needs_info")
            return done("needs_info", 0, "missing_order_id")

        handoff = make_handoff(
            request_id=f"REQ-{claim_id}",
            claim_id=claim_id,
            task="verify_order_and_quote",
            facts={},
            allowed_tools=list(INVESTIGATOR_TOOLS),
        )
        trace.add("handoff", safe_dump(handoff))

        investigated = run_readonly_investigators(conn, budget, handoff, principal_id=claim["principal_id"])
        tools = investigated["tools"]
        order_view = tools.get("lookup_order") or {}
        history = tools.get("lookup_refund_history") or {}
        trace.add(
            "investigator",
            {
                "lookup_order": safe_dump(order_view),
                "refund_history": {k: history.get(k) for k in ("visible", "reason", "refund_count", "refunded_vnd")},
            },
        )

        if not order_view.get("visible"):
            _draft(budget, seed, "escalated")
            return done("escalated", 0, order_view.get("reason"))

        quote = tools.get("compute_compensation")
        if not quote:
            return done("failed", 0, "no_quote")
        trace.add("quote", safe_dump(quote))
        proposal = int(quote["amount_vnd"])
        if proposal <= 0:
            _draft(budget, seed, "denied")
            return done("denied", 0, quote.get("reason"))

        # Only the orchestrator writes, and only through the host.
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
        _draft(budget, seed, "resolved")
        return done("resolved", proposal, None)
    except InjectedCrash:
        raise
    except Exception as exc:
        return done("failed", 0, f"exception:{type(exc).__name__}")


def _draft(budget: Budget, seed: int, status: str) -> None:
    complete(budget, seed=seed, purpose="draft", prompt=f"status={status}")
