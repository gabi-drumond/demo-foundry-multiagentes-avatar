# Guión de demo — Multiagente + AI Gateway + AI FinOps (Banca)

> Documento de demostración. Datos, empresa ("Contoso"), fichas y políticas son ficticios.
> Todos los números que se muestran en pantalla son **reales** (tokens, costo, cuota), salvo la
> **tabla de precios**, que es ilustrativa y editable.

---

## 1. Objetivo (30 segundos)

Mostrar un asistente **multiagente gobernado** para banca que:

- Responde **solo con evidencia** (citas a fichas y políticas) y **no inventa**.
- Separa responsabilidades: un agente de **Producto** y un agente de **Cumplimiento/Riesgo**.
- Pasa el tráfico del modelo por un **AI Gateway (Azure API Management)** con:
  - **Managed Identity** (sin llaves al modelo),
  - **Content Safety** (filtro de contenido),
  - **cuota de tokens por unidad de negocio** (gobernanza),
  - **telemetría de tokens/costo** (AI FinOps).

Frase de apertura sugerida:
> "Voy a mostrar cómo Azure AI Foundry resuelve una consulta de banca con dos agentes
> especializados, y cómo **gobernamos y medimos** ese consumo con un AI Gateway y FinOps —
> todo con evidencia y sin exponer llaves del modelo."

---

## 2. Arquitectura (1 minuto)

```
Navegador (voz + avatar)
        │  REST /api/ask
        ▼
FastAPI  (voice_avatar_app.py)
        ▼
Orquestador (demo_b_orquestador.py) — Microsoft Agent Framework
   │ asyncio.gather (en paralelo)
   ├── agente-producto              → Foundry IQ (fichas)
   └── agente-cumplimiento-riesgo   → Foundry IQ (políticas)
        │
        ▼  SÍNTESIS
   ┌─────────────────────────────────────────────┐
   │ AI Gateway (APIM)  →  Managed Identity  →  gpt-5 (Foundry)
   │  • azure-openai-token-limit (cuota por BU)
   │  • Content Safety
   └─────────────────────────────────────────────┘
```

- Los **dos especialistas** son agentes publicados en el portal de Foundry (`ai.azure.com`),
  cada uno con su base de conocimiento (Foundry IQ). Se ejecutan **server-side**.
- La **síntesis final** del orquestador pasa por **APIM** (el AI Gateway). Es ahí donde
  aplicamos gobernanza y capturamos la telemetría que ves en los paneles.

---

## 3. Guión paso a paso

### Paso 0 — Preparar (antes de presentar)
- Servidor arriba: `python -m uvicorn voice_avatar_app:app --host 127.0.0.1 --port 8010 --env-file .env`
- Abrir `http://127.0.0.1:8010` (Ctrl+F5).
- Limpiar acumulados: `POST http://127.0.0.1:8010/api/finops/reset` (o reiniciar el servidor).
- Confirmar que la política de APIM está en `tokens-per-minute="20000"` (demo normal).

### Paso 1 — Evidencia y separación de agentes (el "qué")
1. Unidad de negocio: **Banca PyME**.
2. Clic en el chip **"🏦 Ficha PyME + DLP"** → **Consultar**.
3. Mientras responde, señalar el pipeline: **01 Producto · 02 Cumplimiento · 03 Síntesis**
   (los dos especialistas trabajan **en paralelo**).
4. Al terminar, mostrar la respuesta:
   - Dictamen **No cumple** (exportar expediente a correo personal),
   - Cita **`POL-SEG-007 R3`** (DLP),
   - Sección **"Fuentes"** con el nombre exacto del `.pdf`.

Mensaje: *"Responde con evidencia y termina con la fuente. No inventa."*

### Paso 2 — AI Gateway + AI FinOps (el "cómo lo gobernamos")
Con la misma respuesta en pantalla, señalar los paneles de la derecha:

- **⚡ AI Gateway · última llamada**
  - *Unidad de negocio*: la BU seleccionada.
  - *Caché AI Gateway*: HIT/MISS.
  - *Latencia* y *Estado*.
  - Nota **"Origen: APIM (AI Gateway real)"** + **"Cuota BU restante: N tok"**.
- **💰 AI FinOps · tokens y costo**
  - Tokens (prompt / respuesta / total), Costo estimado, Ahorro por caché,
    Acumulado sesión, Ahorro acumulado.

Mensaje: *"Cada llamada al modelo pasa por APIM. Medimos tokens y costo por consumidor,
y la llave/cuota es por unidad de negocio."*

### Paso 3 — Ahorro por caché (FinOps)
1. Repetir **la misma pregunta** (mismo chip) → **Consultar**.
2. La respuesta vuelve al instante: **Caché HIT**, **Ahorro por caché** con valor,
   **Ahorro acumulado** sube.

Mensaje: *"Consultas repetidas no vuelven a pagar el modelo — ahorro medible."*

### Paso 4 — Honestidad (anti-alucinación)
1. Clic en el chip **"🚫 Anti-alucinación"** (`¿cashback del 5%?`) → **Consultar**.
2. El agente de Producto responde **"No encontrado en las fuentes"** y no crea una fuente falsa.

### Paso 4b — Seguridad (jailbreak bloqueado)
1. Clic en el chip **"🛡️ Jailbreak (bloqueado)"** → **Consultar**.
2. Aparece un **banner rojo**: *"🛡️ Solicitud bloqueada por Azure AI Content Safety…"*.
3. Mensaje: *"El intento de jailbreak (estilo DAN, + contenido dañino) es detectado por
   **Content Safety + Prompt Shields**. El modelo y el gateway **rechazan la petición antes
   de generar respuesta** — no se expone el prompt de sistema ni ningún dato."*
   - Detalle técnico: la respuesta del modelo es `400 content_filter` con
     `jailbreak: {detected: true, filtered: true}`. La app lo convierte en un mensaje de
     seguridad claro (no un error genérico).

### Paso 5 — Prueba para arquitecto (portal APIM) — opcional
1. Portal → `<apim-resource>` → **APIs** → `<foundry-api>` → **Test**.
2. Enviar un chat completion y mostrar los **headers de respuesta**:
   - `x-ms-served-model: gpt-5-...` (llegó al modelo correcto),
   - `content_filter_results ... "severity":"safe"` (**Content Safety**),
   - `x-bu-consumed-tokens` / `x-bu-remaining-tokens` (**cuota por BU**).
3. Recalcar: **no se envía llave del modelo** — APIM usa **Managed Identity**.

### Paso 6 — Gobernanza en vivo: bloqueo de cota (429) — opcional
1. En APIM → API → **Design** → **All operations** → policy → bajar
   `tokens-per-minute` a **500** → **Save**.
2. En la app: elegir una BU, hacer **una** pregunta (pasa y agota la cuota),
   luego **otra pregunta diferente** en la **misma BU** dentro del minuto.
3. Aparece el mensaje amigable: *"Cuota del AI Gateway agotada para esta unidad de negocio
   (HTTP 429)…"*.
4. Cambiar a **otra BU** → sigue funcionando (cuota **aislada por consumidor**).
5. Al terminar, **volver `tokens-per-minute` a 20000**.

---

## 4. ¿De dónde viene cada dato? (procedencia — clave para preguntas técnicas)

| Dato en pantalla | Origen real | Dónde en el código |
|---|---|---|
| **Tokens (prompt/respuesta/total)** | Campo `usage` de las respuestas del modelo: `usage_details` de los 2 agentes Foundry + `usage` de la respuesta de chat completions del APIM. Se **suman** las 3 llamadas. | `_usage_of()` y `_synthesize_via_apim()` en `demo_b_orquestador.py`; se suman en `orchestrate()`. |
| **Costo estimado** | `tokens × precio`. El **precio es real**: se resuelve desde la **Azure Retail Prices API** (servicio "Foundry Models", meter de input/output del modelo). Fallback a `.env` si la API no responde. | `pricing.py` → `resolve_prices()` (cache 24h); `demo_b_orquestador.py` usa el precio resuelto. |
| **Precio (in/out por 1M)** | **Azure Retail (precio de lista real)** o `fallback .env`. El panel muestra la fuente. | `metrics.priceSource` (`retail`/`fixed`) + `priceInputPer1M`/`priceOutputPer1M`. |
| **Acumulado sesión** | Suma en memoria del costo de cada consulta de la sesión. | `_session_state["acumulado"]`; se reinicia con `POST /api/finops/reset`. |
| **Ahorro por caché** | Al repetir la **misma** (BU + pregunta), se sirve de un caché en memoria y el ahorro = costo que **habría** tenido esa llamada. | `_answer_cache` en `demo_b_orquestador.py`. |
| **Ahorro acumulado** | Suma de los ahorros por caché de la sesión. | `_session_state["ahorro"]`. |
| **Caché AI Gateway (HIT/MISS)** | Estado del caché **de la app** para esa consulta (Fase 1). | `metrics.gatewayCache`. |
| **Latencia** | Medida en la app (tiempo de la orquestación completa). | `time.perf_counter()` en `_build_metrics()`. |
| **Origen (APIM vs app)** | `"apim"` cuando la síntesis pasó por el gateway; `"app"` si hubo *fallback* a Foundry directo (p. ej. blip de red). | `metrics.source` en `orchestrate()`. |
| **Cuota BU restante / consumida** | **Headers reales del APIM**: `x-bu-remaining-tokens` / `x-bu-consumed-tokens`, emitidos por la política `azure-openai-token-limit`. | Se leen en `_synthesize_via_apim()`; nombres definidos en la policy del APIM. |
| **Content Safety** | Filtro de contenido de Azure AI: `content_filter_results` y `x-ms-rai-invoked` en la respuesta del modelo. | Configurado en el recurso Foundry; visible en el **Test** del APIM. |
| **"Sin llave al modelo"** | APIM autentica al backend con **Managed Identity** (System-assigned) con rol *Cognitive Services OpenAI User* sobre el recurso Foundry. Las **llaves del recurso están deshabilitadas**. | RBAC en `<foundry-resource>`; backend del APIM con Managed Identity. |
| **Cuota por unidad de negocio** | Cada BU es un **Product** de APIM con su **subscription key**. La policy cuenta por `context.Subscription.Id` → contador **aislado por BU**. | Products `banca-retail/pyme/empresarial`; keys en `.env` (`APIM_KEY_BANCA_*`). |

### Resumen de "qué es real vs. ilustrativo"
- **Reales (medidos):** tokens, latencia, cuota restante/consumida (headers del APIM), HIT/MISS de caché, dictámenes con citas.
- **Precio real:** la tarifa por token viene de la **Azure Retail Prices API** (precio de lista). El **costo** = tokens reales × precio real. (Sigue siendo "estimado" porque es precio de lista, no EA negociado; los **actuals facturados** están en Cost Management, con retraso.)
- **Seguridad real:** el jailbreak lo bloquea **Azure AI Content Safety + Prompt Shields** (`400 content_filter`, `jailbreak: detected/filtered`) — no es una simulación.
- **Narrativa (no integrado en el app):** gobernanza de agentes tipo *Agent 365* (registry/Purview/Defender) — se explica en el portal M365, no es una llamada del app.

---

## 5. Rutas de datos (para el equipo técnico)

- **Especialistas → Foundry IQ:** los agentes `agente-producto` y `agente-cumplimiento-riesgo`
  consultan sus bases de conocimiento (fichas / políticas) publicadas en el proyecto Foundry.
- **Síntesis → APIM → Foundry:** `POST {APIM_GATEWAY_URL}/openai/deployments/gpt-5/chat/completions`
  con header `api-key: <APIM subscription key de la BU>`. APIM valida la key (cuota por BU),
  aplica Content Safety y llama al modelo con **Managed Identity**.
- **Resiliencia:** la llamada al gateway tiene **reintentos (3x con backoff)** ante blips de red;
  si el gateway falla por red, el app hace **fallback** a Foundry directo (la demo no se rompe,
  y el panel muestra `Origen: app`). Un **429** de cota se muestra como mensaje de gobernanza.

---

## 6. Variables de entorno relevantes (`.env`, no se versiona)

| Variable | Para qué |
|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` | Proyecto Foundry (agentes + modelo de síntesis por defecto). |
| `AGENTE_PRODUCTO` / `AGENTE_CUMPLIMIENTO` (+ `_VERSION`) | Nombres/versiones de los agentes publicados. |
| `FINOPS_PRICE_SOURCE` | `retail` (precio real de Azure) o `fixed` (usar solo `.env`). Default `retail`. |
| `FINOPS_METER_INPUT` / `FINOPS_METER_OUTPUT` | Substring del meter (Foundry Models) para input/output. |
| `FINOPS_PRICE_INPUT_PER_1M` / `FINOPS_PRICE_OUTPUT_PER_1M` | Precios de **fallback** por 1M tokens si la Retail API no responde. |
| `APIM_GATEWAY_URL` | Base del AI Gateway (si está vacío, el app usa Foundry directo). |
| `APIM_DEPLOYMENT` / `APIM_API_VERSION` | Deployment (`gpt-5`) y versión de API en el APIM. |
| `APIM_KEY_BANCA_RETAIL` / `_PYME` / `_EMPRESARIAL` | Subscription keys por unidad de negocio. |
| `SPEECH_REGION` / `SPEECH_ENDPOINT` / `SPEECH_KEY` | Voz/avatar (Azure AI Speech). |

> Si se borran las líneas `APIM_*`, el app vuelve automáticamente al camino Foundry directo.

---

## 7. Troubleshooting rápido

| Síntoma | Causa probable | Acción |
|---|---|---|
| `Origen: app` cuando esperabas `apim` | Blip de red/TLS → *fallback* automático | Reintentar; el retry suele resolverlo. |
| Mensaje de **429** en la primera pregunta | `tokens-per-minute` muy bajo (p. ej. 500) | Subir a `20000` en la policy del APIM. |
| `401` al llamar el gateway | Header equivocado | El APIM (import Foundry) usa header **`api-key`**, no `Ocp-Apim-Subscription-Key`. |
| `WorkspaceNotFound` en Foundry | Suscripción `az` incorrecta | `az account set --subscription <la de la demo>`. |
| Caracteres raros en consola | Encoding | `-e PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8`. |

---

## 8. FinOps enterprise — Application Insights + Log Analytics

Además de los paneles del app (en memoria), la telemetría de tokens/costo se envía a
**Azure Monitor**, alimentada por el propio APIM. Dos vías complementarias:

### Recursos y wiring (ya creados)
- **Log Analytics workspace:** `log-multiagente-demo-mx`
- **Application Insights (workspace-based):** `appi-multiagente-demo-mx` (Custom metrics *With dimensions* habilitado)
- **APIM logger + diagnostic** (`metrics: true`) apuntando a App Insights
- **Política** `azure-openai-emit-token-metric` (namespace `finops-llm`, dimensiones **BU** y **Deployment**)
- **Diagnostic setting** del APIM → Log Analytics (categorías `GatewayLlmLogs` + `GatewayLogs`)

### Vista A — Metrics explorer (gráfico de tokens por unidad de negocio)
1. Portal → `appi-multiagente-demo-mx` → **Monitoring** → **Metrics**.
2. **Metric namespace:** `finops-llm`.
3. **Metric:** `Total Tokens` (o `Prompt Tokens` / `Completion Tokens`), **Aggregation:** Sum.
4. **Apply splitting** → dimensión **BU** → una línea por unidad de negocio.
   (Opcional: filtrar por **Deployment** = `gpt-5`.)
> Los datos aparecen **1–3 min** después de generar tráfico.

### Vista B — Log Analytics (KQL: tokens y costo por deployment/BU)
Portal → `log-multiagente-demo-mx` → **Logs**. Ejemplo (ajusta los precios a los reales):

```kusto
let precioInput  = 1.25 / 1000000.0;   // USD por token (prompt)
let precioOutput = 10.0 / 1000000.0;   // USD por token (respuesta)
ApiManagementGatewayLlmLog
| where TimeGenerated > ago(1h)
| summarize
    PromptTokens     = sum(PromptTokens),
    CompletionTokens = sum(CompletionTokens),
    TotalTokens      = sum(TotalTokens)
    by DeploymentName
| extend CostoEstimadoUSD = round(PromptTokens*precioInput + CompletionTokens*precioOutput, 4)
| order by TotalTokens desc
```

> La tabla `ApiManagementGatewayLlmLog` se llena tras habilitar `GatewayLlmLogs` (ya hecho) y
> generar tráfico por el gateway. Tarda unos minutos en aparecer la primera vez.

### Vista C — Workbook integrado de "Language model" (APIM)
Portal → `<apim-resource>` → **Monitoring** → **Insights** (o **APIs** → menú de la API
LLM → analítica) → workbook de consumo de tokens por API/modelo.

### Generar tráfico para poblar las vistas
- Lo más simple: hacer varias preguntas en el app (la síntesis pasa por APIM → emite métrica/log).
- Nota: si la red corporativa resetea TLS de forma intermitente, algunas llamadas caen en
  *fallback* (no emiten métrica del gateway). Repite hasta ver `Origen: apim`.

---

## 9. Cierre (mensaje de valor)

> "Con Azure AI Foundry entregamos respuestas **con evidencia y sin alucinar**, y con el
> **AI Gateway** de APIM las **gobernamos** (identidad administrada, content safety, cuota por
> unidad de negocio) y las **medimos** (tokens, costo, ahorro). Es IA lista para banca:
> **útil, gobernada y con costos visibles**."
