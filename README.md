# Demo multiagente con Azure AI Foundry (voz + avatar)

Demo lista para presentar que muestra cómo **coordinar varios agentes especializados** en
Azure AI Foundry para resolver una consulta compleja: conocimiento de producto, evaluación de
cumplimiento y una **experiencia de voz con avatar**. El hilo conductor es responder **con
evidencia (citas a las fuentes) y no inventar** cuando falta información.

> Todos los datos son **ficticios** (empresa "Contoso"). Las fichas de producto y las políticas
> incluidas sirven solo como base de conocimiento de demostración.

## Qué demuestra

- **Separación de responsabilidades:** un agente responde solo desde las fichas de producto y
  otro evalúa solo contra las políticas, evitando que una ficha comercial se use como si fuera
  una política (o viceversa).
- **Orquestación en código:** un orquestador construido con **Microsoft Agent Framework**
  consulta a ambos especialistas **en paralelo** (`asyncio.gather`) y **sintetiza** una única
  respuesta conservando las citas.
- **Experiencia de voz/avatar:** entrada por voz (speech-to-text) y respuesta hablada mediante
  un avatar de Azure AI Speech.
- **Gobierno por arquitectura:** identidades administradas + RBAC para acceder al conocimiento,
  DLP como regla de negocio y filtros de contenido en los modelos.

Dos sectores de ejemplo: **Banca** (gobierno de datos, `POL-SEG-007`) y **Farmacia**
(descuentos comerciales `POL-COM-014` y autorización clínica opcional `POL-IMG-001`).

## Arquitectura

```
                 Navegador (voz + avatar)
                          │
                 FastAPI  │  voice_avatar_app.py  (127.0.0.1:8010)
                          ▼
                 demo_b_orquestador.py  (orquestador — Microsoft Agent Framework)
                          │  asyncio.gather (en paralelo)
            ┌─────────────┴─────────────┐
            ▼                           ▼
   agente-producto             agente-cumplimiento-riesgo
   (kb-productos-demo)         (kb-cumplimiento-demo)
            └─────────────┬─────────────┘
                          ▼
              síntesis final (con citas)
```

- Los **dos especialistas** (`agente-producto`, `agente-cumplimiento-riesgo`) se publican en el
  portal de Foundry (`ai.azure.com`), cada uno conectado a su base de conocimiento (Foundry IQ).
- El **orquestador no es un objeto del portal**: vive en el código (`demo_b_orquestador.py`) y es
  la aplicación que coordina y sintetiza.

## Requisitos previos

- Python 3.11+
- Un proyecto de **Azure AI Foundry** con los dos agentes publicados y sus bases de conocimiento.
- Un recurso de **Azure AI Speech** (para voz/avatar).
- **Azure CLI** (`az login`) — el app usa `DefaultAzureCredential` (no requiere claves si tienes
  sesión iniciada). Alternativamente, puedes definir `SPEECH_KEY`.

## Configuración

1. Copia la plantilla de variables de entorno:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Edita `.env` con los valores de tu entorno (endpoint de Foundry, región/endpoint de Speech,
   etc.). El archivo `.env` está en `.gitignore` y **no se versiona**.

3. Instala las dependencias:

   ```powershell
   python -m pip install -r requirements.txt
   ```

## Ejecución

```powershell
az login
python -m uvicorn voice_avatar_app:app --host 127.0.0.1 --port 8010 --env-file .env
```

Abre `http://127.0.0.1:8010`. Verifica el estado con `http://127.0.0.1:8010/api/health`, que
debe devolver:

```json
{ "foundryConfigured": true, "speechConfigured": true }
```

## Preguntas de ejemplo

- **Banca:** "¿Un analista puede exportar el expediente de un Crédito PyME a su correo personal?"
  → **No cumple** (DLP / `POL-SEG-007 R3`).
- **Farmacia:** "Dame la ficha de CardioMax y dime si aplica un 25% de descuento a un cliente que
  está al corriente." → **No cumple** (>20% requiere autorización, `POL-COM-014 R1`).
- **Clínico (opcional):** "¿Puedo autorizar una TAC con contraste sin creatinina previa?"
  → **No cumple** (`POL-IMG-001 R2/R6`).

## Estructura del repositorio

| Ruta | Descripción |
|---|---|
| `voice_avatar_app.py` | Servidor FastAPI: sirve la UI, gestiona el token de Speech y expone `/api/ask`. |
| `demo_b_orquestador.py` | Orquestador: consulta a los dos especialistas en paralelo y sintetiza la respuesta. |
| `voice_avatar.html` | Interfaz de voz + avatar en el navegador. |
| `Fichas/` | Fichas de producto ficticias (base de conocimiento del agente de producto). |
| `Politicas/` | Políticas ficticias (base de conocimiento del agente de cumplimiento). |
| `Guias/GUIA_Demo_Multiagente_Foundry.md` | Guía para construir y presentar la demo. |
| `.env.example` | Plantilla de variables de entorno. |

## Guía completa

Para el paso a paso de construcción y presentación, consulta
[`Guias/GUIA_Demo_Multiagente_Foundry.md`](Guias/GUIA_Demo_Multiagente_Foundry.md).

## Aviso

Repositorio de **demostración**. Datos, empresas ("Contoso"), fichas y políticas son ficticios y
no representan productos, precios ni normativas reales.
