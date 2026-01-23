from typing import List, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from app.core.config import settings
# 匯入抽離後的工具
from app.services.tools.system_tools import get_skill_content
from app.services.tools.medical_tools import search_device_manual, get_user_health_data


class AgentService:

    def __init__(self):
        # 初始化 LLM
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=settings.gemini_api_key,
            temperature=0)
        # 抽離後的載入邏輯
        medical_skill = get_skill_content("medical_expert")
        # 註冊工具清單
        self.tools = [search_device_manual, get_user_health_data]

        # 定義 Prompt 範本
        system_prompt = ("你是一位嚴謹的『血壓計技術支援與健康數據分析師』。你的作業規範如下：\n\n"
                         "1. 【禁止預設知識】：嚴禁使用內建知識回答錯誤代碼、儀器操作或用戶數據問題。\n"
                         "2. 【工具強制性】：\n"
                         "   - 提到代碼（如 ERR）時，必須執行 search_device_manual。\n"
                         "   - 詢問紀錄或分析時，必須執行 get_user_health_data。\n"
                         "3. 【沈默原則】：不輸出處理中預告（如：正在查詢...），直接輸出結果。\n"
                         "4. 【範疇限制】：僅回答與血壓計、高血壓衛教或用戶數據相關的問題。\n\n"
                         "--- 以下是你必須嚴格遵守的專業評估標準與任務指令 ---\n"
                         f"{medical_skill}")
        # 建立 Agent 執行器 (取代原本的 provider 邏輯)
        self.agent = create_agent(model=self.llm,
                                  tools=self.tools,
                                  system_prompt=system_prompt)
        # 簡單記憶體 (生產環境建議改用 Redis 或 DB)
        self.chat_history_map: Dict[str, List[Dict]] = {}

    async def handle_chat(self, user_id: str, message: str) -> str:
        # 取得歷史紀錄
        history = self.chat_history_map.get(user_id, [])
        try:
            # 這裡就是 Agent 的「決策中心」，它會自動決定要不要跑 RAG 或載入 Skill
            # 期望接收一個包含 "messages" 鍵值的 dict
            response = await self.agent.ainvoke({
                "messages":
                history + [{
                    "role": "user",
                    "content": message
                }],
                "user_id":
                user_id  # 額外參數會傳遞給 Tool
            })
            # 解析輸出 (最後一則訊息即為 AI 的回答)
            # response["messages"] 會包含完整的對話過程 (包括 Tool 的中途回應)
            print(response.keys())
            final_message = response["messages"][-1]
            final_text = final_message.content
            # 更新記憶體 (只存對話，不存檢索到的 Context 以節省 Token)
            self._update_history(user_id, message, final_text)
            return final_text
        except Exception as e:
            print(f"Service Error: {e}")
            return "系統暫時無法回應，請稍後再試。"

        except Exception as e:
            print(f"Vector Search Error: {e}")
            return ""

    def _update_history(self, user_id: str, user_msg: str, ai_msg: str):
        history = self.chat_history_map.get(user_id, [])
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": ai_msg})
        self.chat_history_map[user_id] = history[-10:]  # 只保留最近 5 輪對話
