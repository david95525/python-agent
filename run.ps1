# run.ps1
docker compose down

# 構建並啟動
docker compose build --no-cache agent
docker compose up -d

# --- 核心修正：自動清理虛懸鏡像 ---
# -f 是強制執行（不需要再手動輸入 Y 進行確認）
docker image prune -f

docker logs -f python_agent_service