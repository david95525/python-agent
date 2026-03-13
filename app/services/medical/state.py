from typing import Optional, List, Dict, Annotated, TypedDict, Literal, Any
import operator
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    user_id: str
    input_message: str
    # 使用 Annotated 與 operator.add 確保對話紀錄會自動 append 而不是 overwrite
    messages: Annotated[List[BaseMessage], operator.add]

    # 意圖標記
    intent: Literal["device_expert", "health_analyst", "general", "visualizer",
                    "error"]
    last_intent: Optional[str]

    # 用於 fetch_records 判斷分流的計數器
    data_count: int

    # 風險標記
    is_emergency: bool

    # API 查詢參數與結果
    query_start: Optional[str]
    query_end: Optional[str]
    context_data: Optional[str]  # 存放 API 回傳的原始 JSON 字串
    # 存放結構化 UI 數據
    ui_data: Optional[Dict[str, Any]]
    # 擴展用欄位
    active_filters: Dict[str, Any]
    final_response: str
