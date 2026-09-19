"""Compiling and running the planning graph.

Checkpointer: PostgreSQL when a database is configured, otherwise an in-memory saver.
A checkpoint is *workflow execution memory* (which node ran, with what state); a person's
preference is *product memory* and lives in its own table. They never share a table.
"""

from __future__ import annotations

import uuid
from typing import Callable, Optional

from langgraph.checkpoint.memory import InMemorySaver

from app import config
from app.adapters.protocol import DeviceAdapter
from app.agents.orchestrator.agent import Intent, Orchestrator
from app.contracts import AssistantReply, PlannerMode, WakeTime
from app.db.session import database_configured
from app.graph.builder import build_graph


def thread_id(account_id: str, person_id: str, space_id: str, conversation_id: str) -> str:
    return f"account:{account_id}:person:{person_id}:space:{space_id}:conversation:{conversation_id}"


# One checkpointer per process, cached like the SQLAlchemy engine in app/db/session.py.
# PostgresSaver opens a psycopg connection of its own, outside SQLAlchemy, so the pool
# settings there do not reach it: a saver per orchestrator meant a connection per
# RestService, held until the process exited. The suite builds a service per test and
# exhausted a stock PostgreSQL (max_connections = 100) long before the run finished.
# Sharing is safe because PostgresSaver guards its connection with its own threading.Lock.
_saver = None
_saver_ctx = None
_saver_url: Optional[str] = None


def _checkpointer():
    """PostgresSaver keeps its own tables (created by setup()), separate from business data."""
    global _saver, _saver_ctx, _saver_url
    if not database_configured():
        # No connection to share; every graph gets its own scratch memory.
        return InMemorySaver()

    # psycopg-style URL: strip the SQLAlchemy driver marker.
    url = config.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    if _saver is not None and _saver_url == url:
        return _saver
    # A different database means the cached connection points at the wrong place.
    close_checkpointer()

    from langgraph.checkpoint.postgres import PostgresSaver

    context = PostgresSaver.from_conn_string(url)
    saver = context.__enter__()
    saver.setup()
    _saver, _saver_ctx, _saver_url = saver, context, url
    return saver


def close_checkpointer() -> None:
    """Release the shared checkpoint connection. Tests and shutdown only."""
    global _saver, _saver_ctx, _saver_url
    if _saver_ctx is not None:
        _saver_ctx.__exit__(None, None, None)
    _saver, _saver_ctx, _saver_url = None, None, None


class GraphOrchestrator:
    """Same entry point as the legacy Orchestrator, planning runs through LangGraph.

    Event adjustments still use the legacy path: they are a single stage, and wrapping them
    would add a graph without adding an observable step.
    """

    mode = "langgraph"

    def __init__(
        self,
        orchestrator: Orchestrator,
        adapter_for: Callable[[str], DeviceAdapter],
        account_id: str = "demo-account",
    ):
        self._legacy = orchestrator
        self._account_id = account_id
        self._adapter_for = adapter_for
        self._saver = _checkpointer()
        self._new_id_holder: Callable[[str], str] = lambda prefix: f"{prefix}-{uuid.uuid4().hex[:8]}"
        self._graph = build_graph(orchestrator, adapter_for, lambda prefix: self._new_id_holder(prefix))
        self._app = self._graph.compile(checkpointer=self._saver)

    # The legacy orchestrator exposes these; keep the surface identical.
    def adjustment_plan(self, *args, **kwargs):
        return self._legacy.adjustment_plan(*args, **kwargs)

    def handle(
        self,
        person_id: str,
        space_id: str,
        text: str,
        mode: Optional[PlannerMode],
        adapter: DeviceAdapter,
        energy_mode: str,
        new_id: Callable[[str], str],
        force_intent: Optional[Intent] = None,
        wake_time: WakeTime = "07:00",
    ) -> AssistantReply:
        # The id generator belongs to the caller's store; it is a dependency, never state.
        self._new_id_holder = new_id
        request_id = uuid.uuid4().hex
        config_ = {
            "configurable": {
                "thread_id": thread_id(self._account_id, person_id, space_id, request_id),
            }
        }
        final = self._app.invoke(
            {
                "request_id": request_id,
                "account_id": self._account_id,
                "person_id": person_id,
                "space_id": space_id,
                "utterance": text,
                "planner_mode": mode,
                "energy_mode": energy_mode,
                "wake_time": wake_time,
                "forced_intent": force_intent,
                "trace": [],
            },
            config_,
        )
        plan = final.get("plan")
        trace = list(final.get("trace", []))
        if plan is not None:
            plan.trace = trace
        return AssistantReply(
            kind=final.get("reply_kind", "answer"),
            intent=final["intent"],
            text=final.get("answer") or "",
            plan=plan,
            trace=trace,
        )

    def last_checkpoint(self, request_thread_id: str):
        """Read a finished run back from the checkpointer (used by tests and debugging)."""
        return self._app.get_state({"configurable": {"thread_id": request_thread_id}})
