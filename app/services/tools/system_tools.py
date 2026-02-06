from langchain.tools import tool
import os
import yaml
from app.utils.logger import setup_logger

logger = setup_logger("SystemTools")


@tool
def load_specialized_skill(skill_name: str) -> str:
    """
    載入專業技能模組。當需要特定的專業領域知識時調用。
    skill_name 應為技能資料夾名稱，例如 'financial_expert'。
    """
    # 簡化路徑計算：從當前檔案位置出發，找到專案根目錄下的 skills
    # 假設此檔案在 app/services/tools/ 內，向上跳三層到根目錄
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(current_dir, "../../../"))

    # 根據官方規範，路徑應為：skills/{skill_name}/SKILL.md
    skill_file_path = os.path.join(base_dir, "skills", skill_name, "SKILL.md")

    logger.debug(f"[Skill Loader] 嘗試搜尋路徑: {skill_file_path}")

    try:
        if not os.path.exists(skill_file_path):
            logger.warning(f"⚠️ [Skill Loader] 找不到技能檔案: {skill_file_path}")
            return f"錯誤：找不到名為 {skill_name} 的技能資料夾或其內部的 SKILL.md。"

        with open(skill_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 這裡的 YAML 解析邏輯保持不變，非常專業
        if content.startswith("---"):
            try:
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    body = parts[2]
                    metadata = yaml.safe_load(frontmatter)
                    logger.info(f"[Skill Loader] 成功解析技能: {skill_name}")
                    return f"專業規範中繼資料: {metadata}\n\n執行細則內容:\n{body.strip()}"
            except Exception as yaml_err:
                logger.error(f"[Skill Loader] YAML 解析失敗: {yaml_err}")
                return content.strip()
        logger.info(f"[Skill Loader] 成功載入純文字技能: {skill_name}")
        return content.strip()

    except Exception as e:
        logger.error(f"🚨 [Skill Loader] 系統異常: {str(e)}")
        return f"加載技能時發生異常: {str(e)}"
