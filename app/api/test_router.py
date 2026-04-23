from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import yaml
from tests.integration.test_integration import run_scenario

router = APIRouter()


class ScenarioResponse(BaseModel):
    scenario_name: str
    status: str
    steps: List[dict]


@router.get("/scenarios")
async def get_all_scenarios():
    """讓網頁儀表板取得所有的測試劇本清單"""
    path = "tests/integration/test_cases.yaml"
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@router.post("/run-test", response_model=ScenarioResponse)
async def execute_test(case: dict):
    """
    接收網頁傳來的劇本內容，
    呼叫 test_integration.py 裡的核心邏輯進行測試。
    """
    try:
        report = await run_scenario(case)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
