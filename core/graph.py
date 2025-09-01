from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import State
from strategies import load_strategy, select_strategy


def scope(state: State) -> State:
    """Scope phase selects a strategy based on state fields."""
    if (
        state.strategy_slug is None
        and state.category
        and state.time_window
        and state.depth
    ):
        slug = select_strategy(state.category, state.time_window, state.depth)
        if slug:
            state.strategy_slug = slug
            # Load strategy to surface validation errors early.
            load_strategy(slug)
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
