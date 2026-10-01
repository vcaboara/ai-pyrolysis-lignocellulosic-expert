# Utilities

This folder holds small helper scripts for local AI setup.

## Docker + Ollama helper

Run from the repo root:

```powershell
py .\utils\docker_ollama.py up
py .\utils\docker_ollama.py pull llama3.1:8b
py .\utils\docker_ollama.py status
```

Commands:

- `up` starts configured containers
- `down` stops them
- `logs` shows container logs
- `pull <model>` downloads an Ollama model
- `list` lists installed Ollama models
- `status` prints compose status and installed models

You can also use the Docker Compose file directly:

```powershell
docker compose up -d ollama
docker compose exec ollama ollama pull llama3.1:8b
docker compose --profile ui up -d
```
