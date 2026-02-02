import os
from typing import List, Dict, Annotated, TypedDict, Literal
import operator
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrock

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.core.config import settings
from app.services.tools.system_tools import get_skill_content
from app.services.tools.medical_tools import search_device_manual, get_user_health_data


# 1. 定義 Graph 狀態
class AgentState(TypedDict):
    user_id: str
    input_message: str
    messages: Annotated[List[BaseMessage], operator.add]  # 累加對話歷史
    intent: Literal["device", "health", "general"]  # 路由意圖
    is_emergency: bool  # 新增：用於判斷是否觸發緊急狀態
    context_data: str  # 工具抓取的原始數據
    final_response: str  # 最終產出的回覆


class AgentService:

    def __init__(self):
        # 初始化 LLM (動態選擇 LLM)
        self.llm = self._get_llm()

        # 載入技能內容
        self.skills = {
            "device": get_skill_content("device_expert"),
            "health": get_skill_content("health_analyst")
        }

        # 構建生產線 (Graph)
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()

        # 簡單記憶體
        self.chat_history_map: Dict[str, List[BaseMessage]] = {}

    def _get_llm(self):
        """根據環境變數返回對應的 LLM 實例"""
        # 注意：通常 Embedding 與 LLM Provider 會設為同一個，但也可以分開
        provider = os.getenv("LLM_PROVIDER", "google").lower()

        if provider == "google":
            return ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                google_api_key=settings.gemini_api_key,
                temperature=0)
        elif provider == "openai":
            return ChatOpenAI(model="gpt-4o",
                              api_key=os.getenv("OPENAI_API_KEY"),
                              temperature=0)
        elif provider == "bedrock":
            # 未來上 AWS 之後的配置
            return ChatBedrock(
                model_id=
                "anthropic.claude-3-5-sonnet-20240620-v1:0",  # 或 Llama 3
                region_name=os.getenv("AWS_REGION", "us-east-1"),
                model_kwargs={"temperature": 0})
        else:
            raise ValueError(f"不支援的 LLM Provider: {provider}")

    def _build_workflow(self):
        graph = StateGraph(AgentState)

        # 定義節點 (Nodes)
        graph.add_node("router", self.node_router)
        graph.add_node("device_expert", self.node_device_expert)
        graph.add_node("health_analyst", self.node_health_analyst)
        graph.add_node("emergency_advice", self.node_emergency_advice)
        graph.add_node("general_assistant", self.node_general_assistant)

        # 定義邊與條件 (Edges & Conditional Edges)
        graph.add_edge(START, "router")

        # 根據 router 的意圖決定去向
        graph.add_conditional_edges(
            "router", lambda state: state["intent"], {
                "device": "device_expert",
                "health": "health_analyst",
                "general": "general_assistant"
            })
        # 健康分析完後，判斷是否需要「緊急建議」
        graph.add_conditional_edges(
            "health_analyst", lambda state: "emergency"
            if state.get("is_emergency") else "normal", {
                "emergency": "emergency_advice",
                "normal": END
            })
        # 專家處理完後全部指向結束
        graph.add_edge("device_expert", END)
        graph.add_edge("emergency_advice", END)
        graph.add_edge("general_assistant", END)

        return graph

    # --- 節點邏輯實作 ---

    def node_router(self, state: AgentState):
        """意圖路由：決定該找哪位專家"""
        prompt = ("分析以下用戶訊息，判斷其意圖：\n"
                  "1. 如果詢問錯誤代碼(ERR)、操作、說明書，回傳 'device'\n"
                  "2. 如果詢問血壓數據、趨勢分析、健康紀錄，回傳 'health'\n"
                  "3. 其他通用寒暄，回傳 'general'\n"
                  f"用戶訊息：{state['input_message']}\n"
                  "僅回傳單詞，不要有其他文字。")
        res = self.llm.invoke(prompt)
        intent = res.content.strip().lower()
        return {
            "intent": intent if intent in ["device", "health"] else "general"
        }

    async def node_device_expert(self, state: AgentState):
        """硬體專家節點：專注於 RAG 檢索"""
        # 執行工具 (這部分可根據你的 search_device_manual 實作調整)
        raw_info = await search_device_manual.ainvoke(
            {"query": state["input_message"]})

        prompt = (f"### 專業執行細則 ###\n{self.skills['device']}\n\n"
                  f"### 檢索到的說明書資訊 ###\n{raw_info}\n\n"
                  f"請根據上述規範回答用戶：{state['input_message']}")
        res = await self.llm.ainvoke(prompt)
        return {"final_response": res.content}

    async def node_health_analyst(self, state: AgentState):
        """健康分析師節點：專注於數據處理"""
        # 調用工具獲取血壓數據
        raw_data = get_user_health_data.invoke({"user_id": state["user_id"]})

        prompt = (f"### 專業規範 ###\n{self.skills['health']}\n\n"
                  f"### 真實數據 ###\n{raw_data}\n\n"
                  f"### 用戶當前描述 ###\n{state['input_message']}\n\n"
                  "1. 請結合歷史數據與『用戶當前描述的數值』進行綜合分析。\n"
                  "2. 請根據規範分析數據。若出現任何一項『異常』(BP, SpO2, Temp)，"
                  "請在文末標註 [EMERGENCY]，否則標註 [NORMAL]。")
        res = await self.llm.ainvoke(prompt)

        data_list = json.loads(raw_data).get("history", [])
        can_visualize = len(data_list) >= 5

        is_emergency = "[EMERGENCY]" in res.content
        clean_content = res.content.replace("[EMERGENCY]",
                                            "").replace("[NORMAL]", "")
        if can_visualize:
            clean_content += "\n\n💡 **系統偵測到數據量充足，需要我為您繪製趨勢分析圖表嗎？**"
        return {"final_response": clean_content, "is_emergency": is_emergency}

    async def node_emergency_advice(self, state: AgentState):
        """緊急建議節點：臨床指引模式"""
        prompt = ("### 臨床風險警示 ###\n"
                  "當前檢測到用戶血壓數據已達臨床警戒水位。\n"
                  "請提供標準化的醫學建議：\n"
                  "1. 建議用戶保持平靜，靜坐 15 分鐘後重新測量。\n"
                  "2. 若伴隨頭痛、胸痛等症狀，建議立即尋求專業醫療協助或撥打緊急電話。")
        res = await self.llm.ainvoke(prompt)
        combined = f"{state['final_response']}\n\n--- ⚠️ 系統臨床建議 ---\n{res.content}"

        return {"final_response": combined}

    async def node_general_assistant(self, state: AgentState):
        """通用節點：處理範疇外問題"""
        res = await self.llm.ainvoke(
            f"你是一位禮貌的助手，請告知用戶你專注於健康數據分析或設備說明，無法回答以下問題：{state['input_message']}"
        )
        print(
            f"🧠 [Router Decision] 意圖辨識結果: {state['intent']} (原始訊息: {state['input_message']})"
        )
        return {"final_response": res.content}

    # --- API 進入點 ---

    async def handle_chat(self, user_id: str, message: str) -> str:
        # 取得歷史紀錄
        history = self.chat_history_map.get(user_id, [])
        initial_state = {
            "user_id": user_id,
            "input_message": message,
            "messages": history + [HumanMessage(content=message)],
        }
        try:
            # 啟動 LangGraph 生產線
            final_state = await self.app.ainvoke(initial_state)
            final_text = final_state["final_response"]
            mermaid_graph = self.app.get_graph().draw_mermaid()
            if final_state.get("is_emergency"):
                mermaid_graph += "\nclass emergency_advice activeEmergencyNode"
            # 格式化輸出（加上追蹤資訊，方便研究分析）
            debug_info = f"\n\n--- 🧠 Agent 路由追蹤 ---\n意圖：{final_state.get('intent')}\n節點路徑：Router -> {final_state.get('intent')}_expert"
            # 更新記憶體
            self._update_history(user_id, message, final_text)
            # 整理回傳結構
            response_data = {
                "text": final_text,
                "graph": mermaid_graph,
                "intent": final_state.get("intent", "general")
            }
            return response_data

        except Exception as e:
            print(f"Graph Execution Error: {e}")
            return "分析過程出現異常，請檢查設備連線。"

    def _update_history(self, user_id: str, user_msg: str, ai_msg: str):
        history = self.chat_history_map.get(user_id, [])
        history.append(HumanMessage(content=user_msg))
        history.append(AIMessage(content=ai_msg))
        self.chat_history_map[user_id] = history[-10:]


def save_graph_image(agent_service):
    try:
        # 取得編譯後的圖結構，並轉換為 Mermaid 格式的 PNG
        graph_image = agent_service.app.get_graph().draw_mermaid_png()

        with open("agent_workflow.png", "wb") as f:
            f.write(graph_image)
        print("✅ 流程圖已成功儲存為 agent_workflow.png")
    except Exception as e:
        print(f"無法產生圖片，請確保安裝了必要套件: {e}")
