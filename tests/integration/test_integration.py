import yaml
import os
import json
from datetime import datetime
from app.services.medical.service import MedicalAgentService

# 確保測試環境變數
os.environ["TESTING"] = "true"


def load_test_cases():
    """讀取 YAML 檔案中的所有測試案例"""
    base_path = os.path.dirname(__file__)
    path = os.path.join(base_path, "test_cases.yaml")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ------------------------------------------------------------------
# 核心執行邏輯：對應你的 Service 參數定義
# ------------------------------------------------------------------
async def run_scenario(case):
    """執行單個測試劇本並回傳報告"""
    service = MedicalAgentService()

    # 注意：根據你的代碼，Service 內部會將 user_id 當作 thread_id 使用
    # 這裡我們加上時間戳記確保每次測試是獨立的 session
    test_user_id = f"qa_{datetime.now().strftime('%H%M%S')}"

    report = {"scenario_name": case["name"], "status": "PASS", "steps": []}

    for step in case["steps"]:
        step_result = {
            "input": step["user_input"],
            "actual_intent": None,
            "actual_response": None,
            "is_emergency": False,
            "errors": []
        }

        try:
            # 修正：handle_chat 現在是 async generator，需要迭代獲取最終結果
            async for event in service.handle_chat(user_id=test_user_id,
                                               message=step["user_input"]):
                if event["type"] == "final":
                    result = event["data"]
                    # 你的 Service 回傳的是 response_data 字典
                    step_result["actual_intent"] = result.get("intent")
                    step_result["actual_response"] = result.get("text", "")
                    step_result["is_emergency"] = result.get("is_emergency", False)

            # 驗證意圖
            if "expected_intent" in step and step_result[
                    "actual_intent"] != step["expected_intent"]:
                step_result["errors"].append(
                    f"意圖錯誤: 預期 {step['expected_intent']} 實際為 {step_result['actual_intent']}"
                )

            # 驗證關鍵字
            for word in step.get("expect_contains", []):
                if word not in (step_result["actual_response"] or ""):
                    step_result["errors"].append(f"缺少關鍵字: '{word}'")

            # 驗證緊急標記
            if step.get(
                    "expect_emergency") and not step_result["is_emergency"]:
                step_result["errors"].append("未觸發緊急標記")

        except Exception as e:
            step_result["errors"].append(f"執行異常: {str(e)}")

        if step_result["errors"]:
            report["status"] = "FAIL"

        report["steps"].append(step_result)

    return report


# ------------------------------------------------------------------
# Pytest 介面：使用 try-except 保護，防止在正式環境啟動失敗
# ------------------------------------------------------------------
try:
    import pytest

    @pytest.mark.parametrize("case",
                             load_test_cases(),
                             ids=lambda c: c["name"])
    @pytest.mark.asyncio
    async def test_scenarios_automated(case):
        """
        供 pytest 執行的進入點。
        只有當環境有安裝 pytest 時，這段代碼才會生效。
        """
        report = await run_scenario(case)
        if report["status"] == "FAIL":
            error_msg = json.dumps(report, indent=2, ensure_ascii=False)
            pytest.fail(f"劇本測試失敗：\n{error_msg}")
except (ImportError, ModuleNotFoundError):
    # 如果沒有安裝 pytest（例如在 Docker 正式環境），則略過此段定義
    pass
