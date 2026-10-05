# Governed Multi-Agent Demo with Microsoft Foundry, Voice, and Avatar

This repository contains a presentation-ready demo of a governed multi-agent application built
with **Microsoft Foundry**, **Microsoft Agent Framework**, **Azure AI Speech**, and an optional
**Azure API Management (APIM) AI Gateway**.

The application sends the same question to two specialized agents in parallel:

- a **Product** agent that answers only from synthetic product sheets;
- a **Compliance and Risk** agent that evaluates only against synthetic policies.

The orchestrator then creates one evidence-based response, preserves source citations, and presents
it through a browser UI with speech input and a real-time avatar.

> [!IMPORTANT]
> All companies, products, policies, prices, scenarios, and questions in this repository are
> fictional and intended only for demonstration. The repository contains no customer data.
> Never upload customer documents, production credentials, real tenant identifiers, or confidential
> deal information to this demo.

## What the demo shows

- **Multi-agent specialization:** product and compliance knowledge stay in separate scopes.
- **Parallel orchestration:** both agents run concurrently with `asyncio.gather`.
- **Grounded answers:** the final response must preserve exact PDF source names.
- **Voice and avatar:** Azure AI Speech provides speech-to-text, text-to-speech, and the avatar.
- **Responsible AI:** Foundry content filters and Prompt Shields block unsafe requests.
- **Optional AI Gateway:** APIM can apply per-consumer token quotas and managed-identity access.
- **AI FinOps:** the UI displays tokens, estimated list-price cost, latency, and cache savings.

## Architecture

```text
Browser (text, microphone, and avatar)
                  |
                  v
FastAPI - voice_avatar_app.py
                  |
                  v
Orchestrator - demo_b_orquestador.py
        |                         |
        | asyncio.gather          |
        v                         v
Product agent              Compliance/Risk agent
Foundry IQ products KB     Foundry IQ policies KB
        |                         |
        +------------+------------+
                     |
                     v
              Final synthesis
                     |
        +------------+------------+
        |                         |
        v                         v
Direct Foundry model       Optional APIM AI Gateway
                          (quota, telemetry, identity)
```

The two specialists are published Foundry agents. The orchestrator is application code in this
repository; it is not a Foundry Workflow.

## Repository contents

| Path | Purpose |
|---|---|
| `voice_avatar_app.py` | FastAPI server, Speech token exchange, health endpoint, and `/api/ask`. |
| `voice_avatar.html` | Browser UI, microphone input, avatar connection, and FinOps panels. |
| `demo_b_orquestador.py` | Parallel specialist execution, synthesis, APIM routing, cache, and metrics. |
| `pricing.py` | Azure Retail Prices lookup with configurable fallback prices. |
| `Fichas/` | Synthetic product sheets used by the Product knowledge base. |
| `Politicas/` | Synthetic policies used by the Compliance and Risk knowledge base. |
| `Guias/GUIA_Demo_Multiagente_Foundry.md` | Detailed Spanish build and presentation guide. |
| `Guias/GUION_Demo_AI_Gateway_FinOps.md` | Detailed Spanish APIM and FinOps presentation script. |
| `.env.example` | Sanitized configuration template with placeholders only. |

## Prerequisites

### Local tools

- Python 3.10 or later
- Azure CLI
- Git
- Microsoft Edge or Google Chrome
- An Azure subscription where you can create resources and assign RBAC roles

### Azure resources

Required:

1. A resource-based Microsoft Foundry project.
2. A chat model deployment for the agents and synthesis. The sample defaults to `gpt-5`.
3. An embeddings deployment for Foundry IQ. `text-embedding-3-small` is sufficient for the sample.
4. An Azure AI Search resource supported by Foundry IQ.
5. An Azure AI Speech resource in a region that supports real-time avatars.

Optional:

6. An Azure API Management instance configured as an AI Gateway.

Resource availability, supported model versions, and avatar regions change over time. Confirm the
current options in the Azure portal before provisioning.

## 1. Clone and create the Python environment

```powershell
git clone <repository-url>
Set-Location demo-foundry-multiagentes-avatar

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 2. Deploy the Foundry models

In your Foundry project, deploy:

- a chat model, such as `gpt-5`;
- `text-embedding-3-small` for Foundry IQ.

If you use a different chat deployment name, set `FOUNDRY_MODEL` in `.env` to that deployment.

## 3. Create the Foundry IQ knowledge bases

Create two knowledge bases:

### Product knowledge base

Suggested name: `kb-productos-demo`

Upload every PDF from `Fichas/`.

### Compliance and Risk knowledge base

Suggested name: `kb-cumplimiento-demo`

Upload every PDF from `Politicas/`.

Wait until ingestion finishes successfully, then test each knowledge base from the Foundry IQ query
experience. The sample relies on the exact PDF file names being returned in citations.

## 4. Create and publish the specialist agents

Create two prompt agents in the same Foundry project:

1. `agente-producto`
   - Connect `kb-productos-demo`.
   - Instruct it to answer only product questions.
   - Require the exact source PDF name in every grounded answer.

2. `agente-cumplimiento-riesgo`
   - Connect `kb-cumplimiento-demo`.
   - Instruct it to answer only policy, compliance, and risk questions.
   - Require a verdict and the exact policy PDF name.

Publish both agents and note their published version numbers. Draft changes in the playground are not
used until a new version is published.

## 5. Configure authentication and RBAC

Sign in locally:

```powershell
az login
az account show
```

The signed-in identity needs:

- access to the Foundry project and its published agents;
- **Cognitive Services Speech User** on the Speech resource;
- the Foundry IQ and Azure AI Search permissions required to create and query the knowledge bases.

The application uses Azure credentials when `SPEECH_KEY` is empty. A Speech key is supported only as
a local fallback and must never be committed.

## 6. Create the local configuration

```powershell
Copy-Item .env.example .env
```

Edit `.env` and replace placeholders with values from your own demo environment:

```dotenv
FOUNDRY_PROJECT_ENDPOINT=https://<foundry-resource>.services.ai.azure.com/api/projects/<project-name>
AGENTE_PRODUCTO=agente-producto
AGENTE_PRODUCTO_VERSION=1
AGENTE_CUMPLIMIENTO=agente-cumplimiento-riesgo
AGENTE_CUMPLIMIENTO_VERSION=1
FOUNDRY_MODEL=gpt-5

SPEECH_REGION=<region>
SPEECH_ENDPOINT=https://<speech-resource>.cognitiveservices.azure.com
SPEECH_KEY=
SPEECH_VOICE=es-MX-DaliaNeural
AVATAR_CHARACTER=lisa
AVATAR_STYLE=casual-sitting
```

`.env` is ignored by Git. Do not paste its contents into issues, chat messages, screenshots, or
shared archives.

## 7. Run without APIM

The APIM configuration is optional. With `APIM_GATEWAY_URL` empty, specialist calls and final
synthesis use Foundry directly.

```powershell
python -m uvicorn voice_avatar_app:app --host 127.0.0.1 --port 8010 --env-file .env
```

Open `http://127.0.0.1:8010` in Edge or Chrome.

Validate configuration:

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/health
```

Expected result:

```json
{
  "foundryConfigured": true,
  "speechConfigured": true
}
```

Allow microphone access, connect the avatar, and submit one of the synthetic sample questions.

## 8. Optional: configure the APIM AI Gateway

Use APIM only if you want to demonstrate consumer isolation, token quotas, managed identity, and
gateway telemetry.

At a minimum:

1. Import or expose the Foundry chat-completions endpoint through APIM.
2. Enable the APIM system-assigned managed identity.
3. Grant that identity **Cognitive Services OpenAI User** on the Foundry model resource.
4. Create one APIM product/subscription per synthetic business unit.
5. Apply an `azure-openai-token-limit` policy keyed by `context.Subscription.Id`.
6. Return `x-bu-consumed-tokens` and `x-bu-remaining-tokens` headers if you want the UI to display
   quota telemetry.
7. Set the following values in `.env`:

```dotenv
APIM_GATEWAY_URL=https://<apim-resource>.azure-api.net/<api-path>
APIM_DEPLOYMENT=gpt-5
APIM_API_VERSION=2025-04-01-preview
APIM_KEY_BANCA_RETAIL=<local-apim-subscription-key>
APIM_KEY_BANCA_PYME=<local-apim-subscription-key>
APIM_KEY_BANCA_EMPRESARIAL=<local-apim-subscription-key>
```

These are APIM subscription keys, not Foundry model keys. Keep them local. If APIM variables are
empty, the application safely returns to the direct Foundry path.

## 9. Optional: configure AI FinOps pricing

By default, `pricing.py` queries the public Azure Retail Prices API and uses configurable fallback
values if the lookup is unavailable:

```dotenv
FINOPS_PRICE_SOURCE=retail
FINOPS_PRICE_INPUT_PER_1M=1.25
FINOPS_PRICE_OUTPUT_PER_1M=10.0
FINOPS_METER_INPUT=gpt-5-codex-inp-glbl
FINOPS_METER_OUTPUT=gpt-5-codex-out-glbl
```

Review the meter names and fallback prices before presenting. They are list-price estimates, not
invoice actuals or negotiated enterprise pricing.

Reset in-memory demo totals before a presentation:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8010/api/finops/reset
```

## Sample questions

The UI and knowledge documents are intentionally in Spanish for a LATAM presentation scenario.

- Product plus compliance:
  `Dame la ficha del Credito PyME y dime si un analista puede exportar el expediente a su correo personal.`
- Product only:
  `Cual es el monto y plazo del Credito PyME?`
- Anti-hallucination:
  `El Credito PyME ofrece cashback del 5%?`
- Synthetic pharmaceutical scenario:
  `Dame la ficha de CardioMax y dime si aplica un 25% de descuento a un cliente que esta al corriente.`

## Troubleshooting

### Health endpoint reports `false`

- Confirm that Uvicorn was started with `--env-file .env`.
- Verify the variable names in `.env`.
- Restart Uvicorn after changing configuration.

### Foundry returns `401` or cannot find the project

- Run `az login`.
- Confirm the selected subscription with `az account show`.
- Verify access to the Foundry project and published agent versions.

### Speech or avatar fails

- Confirm `SPEECH_REGION` and `SPEECH_ENDPOINT`.
- Verify the **Cognitive Services Speech User** role assignment.
- Confirm the region supports real-time avatars.
- Allow outbound WebRTC traffic to `relay.communication.microsoft.com` over UDP 3478 or TCP 443.
- If necessary, set a local `SPEECH_KEY`; never commit it.

### Knowledge answers have no PDF citation

- Confirm both knowledge sources completed ingestion.
- Test the knowledge bases directly in Foundry IQ.
- Publish a new agent version after changing knowledge or instructions.
- Ensure the configured agent version matches the published version.

### APIM shows `401`

- Confirm the app is sending the APIM subscription key in the `api-key` header.
- Verify the APIM subscription belongs to the selected synthetic business unit.

### APIM shows `429`

- Increase the demo token quota or wait for the configured renewal period.
- Use a different synthetic business unit to demonstrate isolated quotas.

## Security and sharing checklist

Run this checklist before sharing, publishing, or creating a ZIP:

- [ ] Delete the local `.env` file from the copy being shared.
- [ ] Confirm `.env`, keys, certificates, and Python caches are not tracked.
- [ ] Run `git status --short` and review every untracked file.
- [ ] Search for e-mail addresses, tenant IDs, subscription IDs, GUIDs, and real Azure resource names.
- [ ] Inspect screenshots, recordings, terminal output, and PDF metadata.
- [ ] Keep only the synthetic PDFs in `Fichas/` and `Politicas/`.
- [ ] Do not include `.venv/`, `__pycache__/`, logs, exports, or local IDE history.
- [ ] Rotate any credential that may have been committed previously; deleting it from the latest
      commit does not remove it from Git history.

Useful checks:

```powershell
git status --short
git ls-files .env "*.key" "*.pem" "*.pfx"
git grep -n -I -E "(@|subscription|tenant|client[_-]?id|api[_-]?key|secret)"
```

For public distribution, create an archive from tracked files instead of zipping the working
directory:

```powershell
git archive --format=zip --output demo-foundry-share.zip HEAD
```

## Demo data notice

The names `Contoso`, `CardioMax`, and `DermaCare`, along with all policy identifiers and business
scenarios in the sample documents, are synthetic. They do not represent actual products, customers,
prices, legal advice, medical advice, or financial policy.

## License

See `LICENSE`.
