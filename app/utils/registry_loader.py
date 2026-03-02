import os
import json
import logging

logger = logging.getLogger("AgentService")


def load_skills_registry(relative_path: str = "skills/registry.json") -> dict:
    """從指定的 JSON 路徑載入技能註冊表"""
    # 這裡建議使用絕對路徑防止路徑偏移問題
    base_path = os.getcwd()
    path = os.path.join(base_path, relative_path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.info(f"[Registry] 成功載入 {len(data.get('skills', []))} 個模組")
            return data
    except Exception as e:
        logger.error(f"[Registry] 載入失敗: {e}")
        return {"skills": []}


def get_manifest_for_prompt(registry: dict) -> str:
    """將註冊表字典轉換為 LLM Prompt 格式的字串"""
    manifest = []
    skills = registry.get("skills", [])

    for skill in skills:
        manifest.append(f"- '{skill['id']}': {skill['description']}")

    return "\n".join(manifest)


def get_valid_ids(registry: dict) -> list:
    """從註冊表提取所有合法的意圖 ID"""
    return [skill["id"] for skill in registry.get("skills", [])]
