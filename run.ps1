# run.ps1
docker compose down
docker compose build --no-cache agent
docker compose up -d
docker logs -f python_agent_service