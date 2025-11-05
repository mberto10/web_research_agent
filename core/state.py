from __future__ import annotations

from typing import Annotated, List, Optional
from pydantic import BaseModel, Field
import operator


class Evidence(BaseModel):
    """Normalized evidence record."""
    url: str
    publisher: Optional[str] = None
    title: Optional[str] = None
    date: Optional[str] = None
    snippet: Optional[str] = None
    tool: Optional[str] = None
    score: Optional[float] = None


class ScopeState(BaseModel):
    """State fields populated during the scope phase."""
    user_request: str
    category: Optional[str] = None
    time_window: Optional[str] = None
    depth: Optional[str] = None
    strategy_slug: Optional[str] = None


class ResearchState(BaseModel):
    """State fields for the research phase."""
    tasks: List[str] = Field(default_factory=list)
    queries: List[str] = Field(default_factory=list)
    evidence: Annotated[List[Evidence], operator.add] = Field(default_factory=list)




class WriteState(BaseModel):
    """State fields for the write phase."""
    sections: Annotated[List[str], operator.add] = Field(default_factory=list)
    citations: Annotated[List[str], operator.add] = Field(default_factory=list)
    # Runtime vars and counters
    vars: dict = Field(default_factory=dict)


class State(ScopeState, ResearchState, WriteState):
    """Combined application state."""
    pass
