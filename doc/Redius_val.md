先啟動vllm(記得切環境)

啟動langfuse(langfuse-redius port 6379)
cd /home/danny/AI-agent/langfuse
docker compose up -d

啟動本地redius(6380)
sudo docker run -d   --name agent-valkey   -p 6380:6379   --restart always   valkey/valkey:latest
sudo docker exec -it agent-valkey valkey-cli ping