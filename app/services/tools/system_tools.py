# app/services/tools/system_tools.py
import os


def get_skill_content(skill_name: str) -> str:
    """
    根據技能名稱讀取對應的 .md 檔案內容，並移除 YAML frontmatter。
    """
    # 取得專案根目錄 (假設此檔案在 app/services/tools/ 下)
    base_dir = os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    skill_path = os.path.join(base_dir, "skills", f"{skill_name}.md")

    try:
        if not os.path.exists(skill_path):
            raise FileNotFoundError(f"找不到檔案: {skill_path}")

        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()
            # 處理 YAML Frontmatter (--- ... ---)
            if content.startswith("---"):
                parts = content.split("---")
                # parts[0] 是空的, parts[1] 是 YAML, parts[2] 是內容
                skill_content = parts[-1].strip()
            else:
                skill_content = content.strip()

            print(f"✅ [System] 成功載入技能: {skill_name}")
            return skill_content

    except Exception as e:
        print(f"❌ [System] 載入技能 {skill_name} 失敗: {e}")
        return ""
