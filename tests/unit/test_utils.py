import pytest
import json
import os
from app.utils.registry_loader import load_skills_registry, get_manifest_for_prompt, get_valid_ids

def test_load_skills_registry(tmp_path):
    # 建立一個暫時的 registry.json
    d = tmp_path / "skills"
    d.mkdir()
    p = d / "registry.json"
    mock_data = {
        "skills": [
            {"id": "skill1", "description": "desc1"},
            {"id": "skill2", "description": "desc2"}
        ]
    }
    p.write_text(json.dumps(mock_data), encoding="utf-8")
    
    # 測試載入功能
    # 因為 load_skills_registry 使用 os.getcwd()，我們需要模擬路徑或更改工作目錄
    # 這裡我們傳入相對路徑，並確保測試環境下能找到它
    
    # 為了測試，我們可以直接測試邏輯，或者稍微修改 load_skills_registry 接受完整路徑
    # 觀察原始碼，它接受 relative_path 並與 os.getcwd() 拼接
    
    import unittest.mock as mock
    with mock.patch("os.getcwd", return_value=str(tmp_path)):
        registry = load_skills_registry("skills/registry.json")
        assert len(registry["skills"]) == 2
        assert registry["skills"][0]["id"] == "skill1"

def test_get_manifest_for_prompt():
    registry = {
        "skills": [
            {"id": "skill1", "description": "desc1"},
            {"id": "skill2", "description": "desc2"}
        ]
    }
    manifest = get_manifest_for_prompt(registry)
    assert "- 'skill1': desc1" in manifest
    assert "- 'skill2': desc2" in manifest

def test_get_valid_ids():
    registry = {
        "skills": [
            {"id": "skill1", "description": "desc1"},
            {"id": "skill2", "description": "desc2"}
        ]
    }
    valid_ids = get_valid_ids(registry)
    assert valid_ids == ["skill1", "skill2"]

def test_load_skills_registry_error():
    # 測試檔案不存在的情況
    registry = load_skills_registry("non_existent_file.json")
    assert registry == {"skills": []}
