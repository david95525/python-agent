from typing import Optional, List, Dict, Annotated, TypedDict, Literal, Any
import operator
from langchain_core.messages import BaseMessage

def merge_dict(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """合併字典的 Reducer"""
    if old is None: old = {}
    if new is None: new = {}
    return {**old, **new}

def last_value(old: Any, new: Any) -> Any:
    """保留最新值的 Reducer"""
    return new

class AgentState(TypedDict):
    user_id: str
    input_message: str
    # 使用 Annotated 與 operator.add 確保對話紀錄會自動 append 而不是 overwrite
    messages: Annotated[List[BaseMessage], operator.add]

    # 意圖標記
    intent: Annotated[Literal["device_expert", "health_analyst", "general", "visualizer",
                    "error", "health_query", "interrupt"], last_value]
    last_intent: Annotated[Optional[str], last_value]

    # 用於 fetch_records 判斷分流的計數器
    data_count: Annotated[int, last_value]
    is_data_missing: Annotated[bool, last_value]

    # 風險標記
    is_emergency: Annotated[bool, last_value]

    # API 查詢參數與結果
    query_start: Annotated[Optional[str], last_value]
    query_end: Annotated[Optional[str], last_value]
    context_data: Annotated[Optional[str], last_value]  # 存放 API 回傳的原始 JSON 字串
    # 存放結構化 UI 數據
    ui_data: Annotated[Optional[Dict[str, Any]], last_value]
    # 存放上一次分析的摘要，供後續節點（如視覺化）參考
    analysis_summary: Annotated[Optional[str], last_value]
    # 存放動態載入的技能執行細則 (Skill Instructions)
    skill_instructions: Annotated[Optional[str], last_value]
    # 快取優化用：紀錄上一次 LLM 處理過的輸入
    last_processed_input: Annotated[Optional[str], last_value]
    # 擴展用欄位
    active_filters: Annotated[Dict[str, Any], merge_dict]
    final_response: Annotated[str, last_value]
