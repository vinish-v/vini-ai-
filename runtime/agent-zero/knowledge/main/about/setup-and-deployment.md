# Vini AI Setup And Deployment

Docker image:

```bash
docker pull agent0ai/vini-ai
docker run -p 50001:80 agent0ai/vini-ai
```

Persist user data by mounting `/a0/usr`:

```bash
docker run -p 50001:80 -v /path/on/host:/a0/usr agent0ai/vini-ai
```

After first start, configure API keys, chat model, utility model, and embedding model in Settings. Embeddings are required for memory and knowledge recall.

For local development:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements2.txt
python run_ui.py
```

Typical troubleshooting:
- Web UI unreachable: check `docker ps`, port mapping, and startup logs.
- Model errors: verify provider, model name, and API key.
- Memory/knowledge not recalling: verify embedding config and reindex if needed.
- Host-local access: use Vini AI CLI connector tools, not Docker tools.
