# Self-hosted LLM via Ollama + ngrok

Setup completo pra rodar modelos locais (Qwen 3.5, Gemma 4) na própria GPU
e expor opcionalmente via ngrok pro Observer Agent no Databricks alcançar.

---

## Pré-requisitos

### Hardware
- GPU NVIDIA com ≥6GB VRAM (testado em RTX 3070 8GB)
- 16GB RAM sistema (Ollama mantém modelo em VRAM, mas tem overhead)
- Disco: 20GB livres (cada modelo Q4 ocupa 5-9GB)

### Software
- Docker Desktop (Windows/Mac) ou Docker Engine (Linux)
- WSL2 (Windows only) com Ubuntu/Debian
- NVIDIA driver Windows 542+ (ou Linux equivalente)
- NVIDIA Container Toolkit dentro do WSL2

### Validação GPU passthrough

```bash
# Deve listar tua GPU
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

Se isso falhar:
- Windows: verificar Docker Desktop → Settings → Resources → WSL Integration
- Linux: `sudo apt install nvidia-container-toolkit && sudo systemctl restart docker`

---

## Modelos recomendados (RTX 3070 8GB)

| Modelo | Tag Ollama | VRAM | Tok/s | Use case |
|--------|-----------|------|-------|----------|
| **Qwen 3.5 9B** | `qwen3.5:9b` | 6.6 GB | 25-35 | **Recomendado generalist** — multimodal + 256K context |
| **Gemma 4 e2b** | `gemma4:e2b` | 5.1 GB | 50-70 | **Recomendado agentic** — tools nativos + multimodal |
| **Gemma 4 e4b** | `gemma4:e4b` | 8 GB | 25-35 | Tools mais fortes, tight em context grande |
| **Qwen 3.5 4b** | `qwen3.5:4b` | 3.4 GB | 50-70 | Fallback rápido |

**Não viáveis:** Qwen 3.6 (menor é 17GB), Gemma 4 26B/31B, Qwen 3.5 27B+.

---

## Setup local básico (sem ngrok)

### 1. Atualizar `.env`
Adicione (já está no template):
```
NGROK_AUTHTOKEN=seu_token_ngrok_aqui  # opcional, só pra fase B
```

### 2. Subir stack com profile gpu
```bash
cd platform/backend
docker compose --profile gpu up -d
```

Isso sobe:
- `flowertex-ollama` (porta 11434)
- `flowertex-ollama-init` — pull automático de `qwen3.5:9b` + `gemma4:e2b` (rodada única, ~10GB download)
- Demais services (backend, frontend, postgres, redis, omni)

### 3. Aguardar pull terminar (~10min na primeira vez)
```bash
docker logs -f flowertex-ollama-init
# Quando aparecer "init done" = OK
```

### 4. Confirmar Ollama up
```bash
curl http://localhost:11434/v1/models
# Deve retornar JSON com qwen3.5:9b + gemma4:e2b
```

### 5. Cadastrar endpoint na plataforma
- Login `localhost:3000`
- `/settings` → seção **Endpoints LLM customizados**
- **Adicionar endpoint customizado**
  - Nome: `Ollama Local`
  - Base URL: `http://ollama:11434/v1`  (← internal Docker DNS)
  - API Key: deixar vazio
  - **Testar conexão** → deve mostrar 2 models descobertos
  - Marcar checkboxes nos models que quer usar
  - **Criar**

### 6. Selecionar como provider padrão (opcional)
- Volta no topo da `/settings`
- Provider radio: **Custom: Ollama Local**
- Model dropdown: escolher `qwen3.5:9b`

Pronto — chat web local agora usa Qwen 3.5.

---

## Setup com ngrok (Observer Databricks → Ollama local)

### Por que precisa
Observer Agent roda no cluster Databricks (na nuvem AWS). Cluster **não consegue alcançar** `localhost:11434` da tua máquina. Solução: tunnel ngrok expõe Ollama via URL pública.

### 1. Pegar token ngrok
- Conta gratuita em https://dashboard.ngrok.com
- Authtoken em `Your Authtoken` (sidebar)
- Adicionar no `.env`:
  ```
  NGROK_AUTHTOKEN=seu_token_aqui
  ```

### 2. Subir com profile tunnel
```bash
docker compose --profile gpu --profile tunnel up -d
```

### 3. Pegar URL pública
- Browser: `http://localhost:4040` (ngrok inspector)
- Ou: `docker logs flowertex-ngrok | grep "url=https"`
- URL será tipo: `https://abc123-def-456.ngrok-free.app`

### 4. Cadastrar endpoint na plataforma (substituindo URL)
- `/settings` → **Adicionar endpoint customizado**
  - Nome: `Ollama via ngrok`
  - Base URL: `https://abc123-def-456.ngrok-free.app/v1`
  - API Key: vazio
  - Testar → confirmar models descobertos

### 5. Override Observer no wizard de pipeline
- Marketplace → Pipeline WhatsApp → Deploy
- Step Config → expandir **Avançado**
- **LLM do Observer Agent** → selecionar `Custom: Ollama via ngrok`
- Modelo: `qwen3.5:9b`
- Deploy

---

## Runtime LLM update (sem redeploy)

### Pipeline em produção
```bash
curl -X PATCH http://localhost:8000/api/v1/pipelines/{pipeline_id}/llm \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"provider": "custom:abc-uuid", "model": "qwen3.5:9b"}'
```

Próximo run do chat ou Observer usa LLM novo. **Sem deploy, sem restart.**

### Voltar pro default empresa
```bash
curl -X PATCH http://localhost:8000/api/v1/pipelines/{pipeline_id}/llm \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"provider": "", "model": ""}'
```

---

## Hierarquia de resolução LLM

```
1. Override explícito (chat header / wizard) ← maior precedência
2. pipeline.preferred_provider/model
3. session.preferred_provider/model (chat)
4. omni_instance.preferred_provider/model (canais externos)
5. company.preferred_provider/model           ← menor precedência
```

---

## Troubleshooting

### `nvidia-smi` não funciona dentro do container
Indica que NVIDIA Container Toolkit não está configurado. Veja seção pré-requisitos.

### Modelo não cabe (OOM ao pullar/rodar)
- Tente quantização menor (q4 ao invés de q5/q8)
- Use modelo menor (`gemma4:e2b` ao invés de `e4b`)
- Reduza `OLLAMA_KEEP_ALIVE` no docker-compose pra `0` (descarrega VRAM imediato)

### Streaming travado/lento
- Verifique logs `docker logs flowertex-ollama` — pode estar fazendo CPU offload
- Se modelo cabe na VRAM mas tá lento, valide GPU passthrough

### ngrok URL muda toda vez
- Conta gratuita: URL randomica a cada restart. Plano paid = subdomínio fixo.
- Solução: re-cadastrar endpoint no `/settings` quando URL mudar (ou usar `cloudflared` que tem subdomínio gratuito)

### Tools não funcionam (Observer não consegue chamar funções)
- Gemma 3 tinha tools fracos; Gemma 4 tem nativo
- Qwen 3.5 tem tools sólidos
- Se ainda assim falhar, rever logs do Ollama — alguns prompts complexos quebram parsers menores

### Chat retorna texto vazio
- Modelo pequeno pode não ter sido carregado (cold start ~10s)
- Primeira request num modelo novo é lenta — espera

---

## Referências

- Ollama OpenAI compatibility: https://github.com/ollama/ollama/blob/main/docs/openai.md
- Qwen 3.5 model card: https://ollama.com/library/qwen3.5
- Gemma 4 model card: https://ollama.com/library/gemma4
- ngrok docs: https://ngrok.com/docs/getting-started/
