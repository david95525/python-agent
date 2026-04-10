import os
import yaml
from langchain_core.prompts import ChatPromptTemplate
from app.utils.logger import setup_logger

logger = setup_logger("PromptManager")

class PromptManager:
    _instance = None
    _prompts = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PromptManager, cls).__new__(cls)
            cls._instance._load_prompts()
        return cls._instance

    def _load_prompts(self):
        """載入 YAML 格式的 Prompt 設定"""
        # 取得專案根目錄 (假設此檔案在 app/utils/)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompt_path = os.path.join(base_dir, "core", "prompts.yaml")
        
        try:
            if not os.path.exists(prompt_path):
                logger.error(f"[PromptManager] 找不到 Prompt 設定檔: {prompt_path}")
                return

            with open(prompt_path, "r", encoding="utf-8") as f:
                self._prompts = yaml.safe_load(f)
            logger.info(f"[PromptManager] 成功載入 Prompt 設定於: {prompt_path}")
        except Exception as e:
            logger.error(f"[PromptManager] 載入失敗: {e}")
            self._prompts = {}

    def get_template(self, node_name: str) -> ChatPromptTemplate:
        """根據節點名稱取得 ChatPromptTemplate"""
        node_prompt = self._prompts.get(node_name)
        if not node_prompt:
            logger.warning(f"[PromptManager] 找不到節點 {node_name} 的 Prompt，返回空模板")
            return ChatPromptTemplate.from_template("{input_message}")

        messages = []
        if "system" in node_prompt:
            messages.append(("system", node_prompt["system"]))
        if "human" in node_prompt:
            messages.append(("human", node_prompt["human"]))
        
        return ChatPromptTemplate.from_messages(messages)

# 全域單例物件
prompt_manager = PromptManager()
