import os
from app.services.base import BaseAgent
from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, List
from datetime import datetime
from app.utils.logger import setup_logger
from app.services.tools.financial_tools import get_stock_price, get_market_news
from app.services.tools.system_tools import load_specialized_skill

logger = setup_logger("ApiRouter")


class FinanceState(TypedDict):
    symbol: str  # 股票代號
    data_raw: str  # 抓取到的原始數據
    analysis_report: str  # 分析師的評估
    risk_level: str  # 風險等級
    final_response: str  # 產出的最終建議內容


class FinancialAgentService(BaseAgent):

    def __init__(self):
        super().__init__("FinancialService")
        # 手動 LangGraph 實作
        self.workflow = self._build_workflow()
        self.manual_app = self.workflow.compile()
        # DeepAgents
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        skills_path = os.path.join(base_dir, "skills")
        logger.info(f"註冊官方技能路徑: {skills_path}")
        self.official_deep_agent = create_deep_agent(
            model=self.llm,
            backend=FilesystemBackend(root_dir=base_dir),
            tools=[get_stock_price, get_market_news],
            skills=["skills/"],
        )

    def _build_workflow(self):
        graph = StateGraph(FinanceState)

        # 定義金融特有節點
        graph.add_node("researcher", self.node_market_research)
        graph.add_node("analyst", self.node_risk_analysis)
        graph.add_node("decision_maker", self.node_final_decision)

        # 思考鏈：研究 -> 分析 -> 決策
        graph.add_edge(START, "researcher")
        graph.add_edge("researcher", "analyst")
        graph.add_edge("analyst", "decision_maker")
        graph.add_edge("decision_maker", END)

        return graph

    async def node_market_research(self, state):
        #"""研究節點：負責收集數據"""
        symbol = state["symbol"]
        logger.info(f"[Financial Agent] 正在研究: {symbol}")

        # 抓取股價 (呼叫 Tool)
        price_info = get_stock_price.invoke({"symbol": symbol})

        # 抓取新聞 (呼叫 Tool)
        news_info = get_market_news.invoke({"query": symbol})

        # 彙整原始數據存入狀態
        combined_data = f"【股價數據】\n{price_info}\n\n【市場新聞】\n{news_info}"
        return {"data_raw": combined_data}

    async def node_risk_analysis(self, state):
        logger.info("[Financial Agent] 正在進行風險評估...")
        skill_config = load_specialized_skill.invoke(
            {"skill_name": "financial_expert"})
        # 讓 LLM 閱讀數據
        prompt = (f"你現在扮演以下專業角色：\n"
                  f"{skill_config}\n\n"
                  f"請根據上述『執行細則』，分析以下原始數據並判斷風險等級：\n"
                  f"原始數據：\n{state['data_raw']}")
        res = await self.llm.ainvoke(prompt)
        risk = "中"
        if "高" in res.content: risk = "高"
        elif "低" in res.content: risk = "低"

        return {"risk_level": risk, "analysis_report": res.content}

    async def node_final_decision(self, state):
        """決策節點：產出最後報告"""
        logger.info("[Financial Agent] 正在產出最終決策...")
        skill_config = load_specialized_skill.invoke(
            {"skill_name": "financial_expert"})
        current_date = datetime.now().strftime("%Y-%m-%d")
        prompt = (f"今天是 {current_date}。\n"
                  f"請嚴格遵守以下【輸出規範】處理數據：\n\n"
                  f"{skill_config}\n\n"
                  f"【待處理數據】\n"
                  f"標的：{state['symbol']}\n"
                  f"數據：{state['data_raw']}\n"
                  f"風險分析：{state['analysis_report']}")
        res = await self.llm.ainvoke(prompt)
        return {"final_response": res.content}

    # 手動模式進入點
    async def run_manual_logic(self, symbol: str):
        logger.info(f"執行 [手動 LangGraph] 模式: {symbol}")
        initial_state = {
            "symbol": symbol,
            "data_raw": "",
            "analysis_report": "",
            "risk_level": "",
            "final_response": ""
        }
        return await self.manual_app.ainvoke(initial_state)

    # 官方 DeepAgents 模式進入點
    async def run_official_deep_logic(self, symbol: str):
        logger.info(f"執行 [官方 DeepAgents] 模式: {symbol}")
        # 官方封裝通常使用標準的訊息格式
        input_data = {
            "messages": [{
                "role":
                "user",
                "content":
                f"請啟動 financial_expert 專業技能，深度分析股票 {symbol} 並給予投資建議。"
            }]
        }
        result = await self.official_deep_agent.ainvoke(input_data)
        logger.debug(f"DEBUG OFFICIAL RESULT: {result}")
        # 提取最後一條訊息作為回應
        return {
            "final_response": result["messages"][-1].content,
            "steps": result.get("steps", [])
        }
