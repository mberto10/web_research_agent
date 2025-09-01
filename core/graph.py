from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import State


def scope(state: State) -> State:
    """Placeholder scope phase."""
    return state


def research(state: State) -> State:
    """Placeholder research phase."""
    return state


def write(state: State) -> State:
    """Placeholder write phase."""
    return state


def build_graph() -> StateGraph:
    """Construct the LangGraph workflow."""
    builder = StateGraph(State)
    builder.add_node("scope", scope)
    builder.add_node("research", research)
    builder.add_node("write", write)

    builder.set_entry_point("scope")
    builder.add_edge("scope", "research")
    builder.add_edge("research", "write")
    builder.add_edge("write", END)

    return builder.compile(checkpointer=MemorySaver())
