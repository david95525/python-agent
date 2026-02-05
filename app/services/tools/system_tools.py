from langchain.tools import tool
import os
import yaml
from app.utils.logger import setup_logger

# 建議在這裡獨立定義 logger，名稱可以叫 SystemTools
logger = setup_logger("SystemTools")


@tool
def load_specialized_skill(skill_name: str) -> str:
    """
    載入專業技能模組。當需要特定的專業領域知識時調用。
    """
    # 這裡的路徑計算邏輯稍微複雜，建議增加 Debug Log 記錄最終路徑
    base_dir = os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    skill_path = os.path.join(base_dir, "skills", f"{skill_name}.md")

    logger.debug(f"[Skill Loader] 嘗試載入路徑: {skill_path}")

    try:
        if not os.path.exists(skill_path):
            logger.warning(f"⚠️ [Skill Loader] 找不到技能檔案: {skill_name}.md")
            return f"錯誤：找不到名為 {skill_name} 的技能檔案。"

        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        if content.startswith("---"):
            try:
                # 處理可能的 YAML 解析錯誤
                _, frontmatter, body = content.split("---", 2)
                metadata = yaml.safe_load(frontmatter)

                logger.info(
                    f"[Skill Loader] 成功解析技能: {skill_name} (Version: {metadata.get('version', 'N/A')})"
                )
                return f"技能中繼資料: {metadata}\n\n專業規範內容:\n{body.strip()}"
            except Exception as yaml_err:
                logger.error(
                    f"[Skill Loader] YAML 解析失敗 ({skill_name}): {yaml_err}")
                # 解析失敗也沒關係，至少回傳原始內容，不讓 Graph 掛掉
                return content.strip()

        logger.info(f"[Skill Loader] 成功載入純文字技能: {skill_name}")
        return content.strip()

    except Exception as e:
        logger.error(f"🚨 [Skill Loader] 系統異常 ({skill_name}): {str(e)}",
                     exc_info=True)
        return f"加載技能時發生異常: {str(e)}"
