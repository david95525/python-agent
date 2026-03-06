from typing import Optional, List, Dict, Annotated, TypedDict, Literal
import operator
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    user_id: str
    input_message: str
    messages: Annotated[List[BaseMessage], operator.add]
    intent: Literal["device", "health", "general", "visualizer"]
    is_emergency: bool
    last_intent: str
    query_start: Optional[str]
    query_end: Optional[str]
    context_data: str
    active_filters: Dict[str, any]
    final_response: str
