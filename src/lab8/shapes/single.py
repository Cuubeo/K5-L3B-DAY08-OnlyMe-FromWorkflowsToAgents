"""Shape B — one ReAct agent.

`lab8.runtime.run_react` drives a bounded loop (max_steps=8). Each step the agent
"thinks" with one MockLLM call, then picks one READ tool:

    lookup_order -> lookup_refund_history -> compute_compensation -> final

Boundaries kept in code, not in the model:

- The agent never sees write tools; `dispatch` refuses them anyway.
- The ticket is shown to the model as user data. `decide` never takes a delay,
  an amount, an order id or a clause from the ticket; the order row is the truth.
- The money is whatever `compute_compensation` returned inside the loop. After
  the loop, the shape (not the model) calls `durability.issue_refund` with the
  FULL quote and `crash_at`. The host subtracts earlier refunds on the order.
- `lookup_refund_history` is read for the trace/reply only; it is not subtracted.

Trace contract v1: `traces/<run_id>.json` on every return path. Tool results are
traced only after allowlisting (order view fields, quote, refund totals).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8 import durability
from lab8.db import connect
from lab8.durability import InjectedCrash
from lab8.mock_llm import complete
from lab8.runtime import run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import get_claim_view, tool_cost
from lab8.trace import Trace

SHAPE = "single"
MAX_STEPS = 8


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


class _Agent:
    """Stateful decide(). Remembers tool results the loop hands back one at a time."""

    def __init__(self, budget: Budget, seed: int, claim: dict[str, Any], ticket: str, trace: Trace) -> None:
        self.budget = budget
        self.seed = seed
        self.claim = claim
        self.ticket = ticket
        self.trace = trace
        self.order_view: dict[str, Any] | None = None
        self.history: dict[str, Any] | None = None
        self.quote: dict[str, Any] | None = None
        self.step = 0

    def decide(self, seen: dict[str, Any]) -> dict[str, Any]:
        self.step += 1
        self._absorb(seen)
        # One "thought" per step. The ticket is data in the prompt, never an instruction.
        complete(
            self.budget,
            seed=self.seed,
            purpose="react",
            prompt=f"step={self.step} tool={seen.get('last_tool')} ticket_as_data={self.ticket}",
        )
        if not self.claim.get("order_id"):
            return {"final": {"status": "needs_info", "reason": "missing_order_id"}}
        if self.order_view is None:
            return self._call("lookup_order", {"order_id": self.claim["order_id"], "principal_id": self.claim["principal_id"]})
        if not self.order_view.get("visible"):
            return {"final": {"status": "escalated", "reason": self.order_view.get("reason")}}
        if self.history is None:
            return self._call(
                "lookup_refund_history",
                {"order_id": self.claim["order_id"], "principal_id": self.claim["principal_id"]},
            )
        if self.quote is None:
            # Quote from the DB order row, not from numbers in the ticket.
            return self._call("compute_compensation", {"order": dict(self.order_view["order"])})
        if int(self.quote["amount_vnd"]) <= 0:
            return {"final": {"status": "denied", "reason": self.quote.get("reason")}}
        return {"final": {"status": "propose_refund", "reason": "entitled"}}

    def _call(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        self.trace.add("react_step", {"step": self.step, "tool": tool})
        return {"tool": tool, "args": args}

    def _absorb(self, seen: dict[str, Any]) -> None:
        tool = seen.get("last_tool")
        result = seen.get("last_result")
        if tool is None or not isinstance(result, dict):
            return
        if tool == "lookup_order":
            self.order_view = result
            self.trace.add("observation", {"tool": tool, "result": safe_dump(result)})
        elif tool == "lookup_refund_history":
            self.history = result
            self.trace.add(
                "observation",
                {"tool": tool, "result": {k: result.get(k) for k in ("visible", "reason", "refund_count", "refunded_vnd")}},
            )
        elif tool == "compute_compensation":
            self.quote = result
            self.trace.add("observation", {"tool": tool, "result": safe_dump(result)})


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
        claim_view = get_claim_view(conn, claim_id)
        if not claim_view["found"]:
            return done("failed", 0, "unknown_claim")
        claim = {k: claim_view[k] for k in ("claim_id", "principal_id", "order_id")}
        trace.add("claim", {"claim_id": claim_id, "has_order_id": bool(claim["order_id"])})

        agent = _Agent(budget, seed, claim, claim_view.get("ticket") or "", trace)
        loop = run_react(conn, budget, observation={"claim": claim}, decide=agent.decide, max_steps=MAX_STEPS)
        final = loop["final"]
        trace.add("loop", {"stopped": loop["stopped"], "steps": agent.step})

        if loop["stopped"] == "step_cap":
            return done("failed", 0, "step_cap")
        verdict = final.get("status")
        if verdict in ("needs_info", "escalated"):
            _draft(budget, seed, verdict)
            return done(verdict, 0, final.get("reason"))

        # Code-side validation: the only money is the tool quote seen in the loop.
        if agent.quote is None:
            return done("failed", 0, "no_quote")
        proposal = int(agent.quote["amount_vnd"])
        if proposal <= 0:
            _draft(budget, seed, "denied")
            return done("denied", 0, agent.quote.get("reason"))

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
