"""
Manager Agent - Mixin Base

Base class for all ManagerAgent mixins. Provides type annotations and
documentation for attributes that mixins expect to find on `self`.

This ensures IDE support and type checking work correctly across mixins.
"""


class ManagerAgentMixin:
    """Base mixin class for ManagerAgent.

    All mixins inherit from this class. The actual ManagerAgent class
    in _main.py combines all mixins via multiple inheritance.

    Expected attributes on `self` (set in ManagerAgent.__init__):
        - llm: LLM client instance
        - agent_registry: AgentRegistry instance
        - tool_registry: ToolRegistry instance
        - web_mode: bool
        - user_tier: str
        - user_id: str
        - session_id: str
        - router: AgentRouter instance
        - tool_access_resolver: ToolAccessResolver instance
        - analysis_policy_resolver: AnalysisPolicyResolver instance
        - _memory_cache: Dict[str, ShortTermMemory]
        - _memory_store: Optional[MemoryStore]
        - progress_callback: Optional[Callable]
        - _consolidating: bool
        - _consolidation_lock: asyncio.Lock
        - _last_consolidated_index: int
        - _consolidation_task: Optional[asyncio.Task]
        - _message_count: int
        - _last_activity_time: float
        - _model_router: ModelRouter instance
        - _token_tracker: TokenTracker instance
        - _trace_collector: TraceCollector instance
        - graph: Compiled LangGraph (wrapped with _TracedGraph)
        - _symbol_resolver: UniversalSymbolResolver instance
    """

    pass
