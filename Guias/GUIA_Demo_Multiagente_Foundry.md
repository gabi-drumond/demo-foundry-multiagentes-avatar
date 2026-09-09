# Guía — Demo multiagente con Microsoft Foundry (Voice/Avatar)

Demostración de un **sistema multiagente** construido con Microsoft Foundry y el **Microsoft
Agent Framework**, con una experiencia de **voz + avatar**. El objetivo es mostrar cómo varios
agentes especializados mantienen las respuestas **fundamentadas y gobernadas**, con una
experiencia digital propia.

Un mismo proyecto Foundry y un mismo par de bases de conocimiento sirven para dos sectores;
solo cambia la pregunta objetivo:

- **Banca:** fichas de servicios financieros y política de acceso (POL-SEG-007).
- **Farmacia:** fichas de medicamentos, política de descuentos (POL-COM-014) y política de
  autorización clínica (POL-IMG-001, escenario opcional).

> La demostración no incluye OpenTelemetry. El cierre de gobierno se apoya en evidencia de las
> fuentes, separación de responsabilidades, DLP, RBAC y Content Safety.

## Mensaje central

> Cuando una sola consulta necesita conocimiento de producto, interpretación de cumplimiento y una
> experiencia digital propia, pasamos de un agente a un sistema de agentes. Coordinamos
> especialistas en Microsoft Foundry y mantenemos el conocimiento y las decisiones dentro de
> límites gobernados.

---

# PARTE 1 — CONSTRUIR LA DEMO

## Arquitectura elegida — portal + Microsoft Agent Framework

- **Portal de Microsoft Foundry:** crea Foundry IQ y mantiene los agentes especialistas,
  sus instrucciones, modelos y herramientas de conocimiento.
- **Microsoft Agent Framework para Python:** coordina los especialistas desde una aplicación
  propia. No uses **Foundry Workflows (Preview)**: Microsoft anunció su retiro para el
  1 de diciembre de 2026.
- Los especialistas siguen siendo recursos administrados por Foundry. El código los invoca
  mediante `FoundryAgent`; no duplica sus PDFs, bases de conocimiento ni instrucciones.

## Preparación (varios días antes — no dejar para el último momento)

### P1. Validaciones de plataforma (CRÍTICO — confirmar antes de construir)

1. Suscripción de Azure con acceso a **Azure AI Foundry** (portal nuevo: ai.azure.com).
2. **Deploy de modelo:** `gpt-5` para chat y `text-embedding-3-small` para Foundry IQ.
3. **Voz:** un modelo compatible con Voice Live O un recurso de **Azure AI Speech** (TTS).
4. **Avatar en tiempo real (Azure AI Speech Text-to-Speech Avatar):** disponibilidad LIMITADA
   por región. CONFIRMA la región y la cuota — NO asumas East US 2. (Regiones típicas del
   avatar en tiempo real: West US 2, West Europe, Southeast Asia, Sweden Central — verifica
   la lista vigente en la doc de Speech antes de provisionar.)
5. Recurso de **Azure AI Speech** creado en la región correcta del avatar.

### P2. Crear el proyecto, el conocimiento y los especialistas en el portal

> En el portal actual, **Knowledge** ya no adjunta el PDF directamente al agente. Es normal que
> te redirija a **Foundry IQ**: primero se crea una fuente de conocimiento, luego una base de
> conocimiento y finalmente se conecta esa base al agente como herramienta.

#### P2.1. Crear el proyecto y desplegar los modelos

1. En **ai.azure.com**, crea un recurso de **Microsoft Foundry** y un proyecto nuevo en
  **East US 2**. Para Foundry IQ usa un proyecto nuevo basado en recurso; no uses un proyecto
  clásico basado en Hub.
2. En **Models + endpoints**, despliega:
  - Un modelo de chat disponible para los agentes y la síntesis de respuestas. Usa
    `gpt-5`, ya desplegado para esta demo. Si la latencia es alta, usa `gpt-5-mini` cuando esté
    disponible en la suscripción.
  - El modelo de embeddings `text-embedding-3-small`, suficiente para los pocos PDFs de la demo.
3. Si el portal solicita crear el recurso de **Foundry IQ / Azure AI Search** y muestra que
  **East US 2** no acepta recursos nuevos por falta de capacidad, cambia únicamente la región
  de ese recurso a **South Central US**. No es necesario recrear el grupo de recursos, el
  proyecto ni los modelos ya desplegados en East US 2.
  - Orden de fallback recomendado: **South Central US**, **Sweden Central**, **Southeast Asia**.
  - Evita **West US 2** como primer fallback: también puede estar en alta demanda para recursos
    nuevos de Azure AI Search.
  - Usa el nivel más bajo que admita las funciones solicitadas; con identidad administrada,
    Foundry IQ puede requerir **Basic** o superior.
  - La disponibilidad de capacidad es dinámica. En el asistente, el criterio final es que no
    aparezca la alerta de capacidad y que el botón **Create** quede habilitado.

#### P2.2. Crear las bases de conocimiento en Foundry IQ

1. Abre **Foundry IQ** en el menú del proyecto. Si llegaste allí desde **Agents → Knowledge**,
  continúa en esa pantalla; la redirección es el comportamiento esperado.
2. Crea una base para productos:
  - **Knowledge base name:** `kb-productos-demo`
  - **Description:** `Fichas de productos para la demostración multiagente.`
  - Carga las cuatro fichas: `Ficha_Credito_Pyme.pdf` y `Ficha_Cuenta_Empresarial.pdf`
    (Banca); `Ficha_Producto_Contoso_CardioMax.pdf` y
    `Ficha_Producto_Contoso_DermaCare.pdf` (Farmacia).
3. Dentro de la base, selecciona **Add knowledge source / Add source** y elige la opción para
  archivos o **Azure Blob Storage**, según lo que muestre el tenant:
  - Si aparece **Upload files**, carga primero una sola ficha PDF y continúa con el asistente.
  - Si solo aparece **Azure Blob Storage**, crea o selecciona una cuenta de Storage y un
    contenedor, por ejemplo `documentos-demo`; carga allí los PDFs y selecciona ese contenedor
    como fuente.
  - Si aparece **File upload processing failed**, selecciona **Dismiss**, no **Retry**, y prueba
    un archivo por vez. Usa un `.txt` corto como control:
    - Si el `.txt` funciona, vuelve a guardar el PDF desde el navegador o usa **Imprimir →
      Guardar como PDF**. Comprueba que el archivo abra localmente, contenga texto seleccionable,
      no tenga contraseña ni cifrado y use un nombre corto sin acentos ni caracteres especiales.
    - Si el `.txt` también falla, revisa el recurso de Azure AI Search en Azure Portal:
      1. Debe usar un nivel dedicado, no **Serverless**.
      2. En **Identity**, habilita la identidad administrada asignada por el sistema.
      3. En el recurso Foundry que contiene `text-embedding-3-small`, asigna el rol **Cognitive
         Services User** a la identidad administrada del servicio Azure AI Search.
      4. En Azure AI Search, asigna **Search Service Contributor** a tu usuario. Para una fuente
         directa de tipo **File**, este es el rol requerido para crear la fuente y cargar archivos.
      5. Espera la propagación de RBAC, actualiza el portal y vuelve a cargar un solo `.txt`.
    - La fuente directa `ks-file-*` almacena el contenido dentro de Azure AI Search; por eso no
      requiere permisos de Blob Storage. **Storage Blob Data Reader** solo se aplica cuando eliges
      **Azure Blob Storage** como fuente alternativa.
4. Cuando el asistente lo pida, selecciona el servicio de **Azure AI Search**, el modelo de chat
  y el modelo de embeddings desplegados en P2.1. Mantén la extracción estándar y la
  vectorización habilitadas.
5. Crea una segunda base para cumplimiento:
  - **Knowledge base name:** `kb-cumplimiento-demo`
  - **Description:** `Políticas de seguridad, acceso y cumplimiento para la demostración.`
  - Carga las tres políticas: `Politica_Acceso_Datos_y_Cambios_Bank.pdf` (POL-SEG-007, Banca),
    `Politica_Descuentos_Comerciales_Pharma.pdf` (POL-COM-014, Farmacia) y
    `Politica_Autorizacion_Medical.pdf` (POL-IMG-001, Farmacia clínico — opcional).
6. Espera a que la ingestión de ambas fuentes termine en **Succeeded / Ready**. Si aparece
  **Partial success** o **Failed**, abre los detalles del indexador antes de continuar.
7. Prueba cada base desde el panel de consulta de Foundry IQ:
  - Productos: formula una pregunta cuya respuesta esté explícitamente en una ficha.
  - Cumplimiento: pregunta qué indica una regla concreta y confirma que la respuesta incluya
    referencias a la fuente.

#### P2.2.1. Autorizar el acceso de los agentes a Foundry IQ

La carga de archivos y la recuperación durante la ejecución usan identidades diferentes. Una
carga exitosa no garantiza que un agente pueda consultar la base de conocimiento.

1. En el proyecto de Microsoft Foundry, abre **Identity**, habilita **System assigned** y guarda.
2. En el servicio de **Azure AI Search**, abre **Access control (IAM)** y agrega la asignación:
  - **Role:** `Search Index Data Reader`.
  - **Member:** la identidad administrada del **proyecto Foundry**, no tu usuario ni la identidad
    del servicio Azure AI Search.
  - **Scope:** el servicio Azure AI Search utilizado por las bases de conocimiento.
3. No agregues `Search Index Data Contributor` para esta demo. Solo se necesita si el agente
  también debe escribir documentos en los índices.
4. Confirma que la autenticación de Azure AI Search permita **Role-based access control**. Si
  está configurada como keyless, `disableLocalAuth: true` también es válido.
5. Espera la propagación de RBAC, actualiza el portal y abre un hilo nuevo en el playground.

El sentido de cada asignación es importante:

```text
Proyecto Foundry -- Search Index Data Reader --> Azure AI Search
Azure AI Search -- Cognitive Services User --> Recurso Foundry/modelos
```

Si el playground muestra `HTTP 403 Forbidden` al enumerar la herramienta MCP de la base:

1. Comprueba que `Search Index Data Reader` esté asignado al `principalId` de la identidad del
  proyecto Foundry en el servicio Search.
2. Comprueba que la conexión de proyecto use `ProjectManagedIdentity`, categoría `RemoteTool` y
  audiencia `https://search.azure.com/`.
3. Verifica que la URL apunte a la base correcta con el formato
  `https://<search>.search.windows.net/knowledgebases/<base>/mcp?api-version=<versión>`.
4. Confirma que tu usuario tenga `Foundry User` o `Foundry Project Manager` para usar la
  herramienta. `Search Service Contributor` en tu usuario permite administrar objetos, pero no
  concede a la identidad del agente acceso de lectura a la base.

#### P2.3. Crear los agentes especialistas

1. Regresa a **Agents** y crea el **Agente Producto**:
  - **Instructions:** `Respondes sobre productos usando únicamente la base de conocimiento. Si
    la información no está en las fuentes, indícalo. Incluye las referencias recuperadas.`
  - En **Tools / Knowledge**, selecciona **Foundry IQ knowledge base** y conecta
    `kb-productos-demo`. En algunas versiones aparece como una herramienta MCP llamada
    `knowledge_base_retrieve`.
2. Crea el **Agente Cumplimiento/Riesgo**:
  - **Instructions:** `Validas el caso únicamente contra la política recuperada. Responde
    Cumple o No cumple, explica las desviaciones y cita la regla y la fuente. Si falta
    información, solicítala y no inventes reglas.`
  - Conecta `kb-cumplimiento-demo` como herramienta de conocimiento.
3. Prueba cada especialista por separado y confirma que la respuesta cite el PDF exacto de su
  base de conocimiento. Si responde sin evidencia, refuerza en las instrucciones que debe usar la
  herramienta y responder `No encontrado en las fuentes` cuando no haya información recuperada.
4. Después de conectar la base y guardar las instrucciones, **publica una nueva versión** de
  cada agente. Anota el número visible en **Agents → Versions**. El script invoca una versión
  publicada; cambios que solo estén en el borrador del playground no se aplican a esa llamada.

#### P2.4. Crear y probar la orquestación con Microsoft Agent Framework

1. No crees la coordinación en **Foundry Workflows** ni busques los especialistas en
  **Add tool**. El catálogo de herramientas del portal no es un selector de agentes del
  mismo proyecto.
2. En la terminal, autentícate y prepara Python:
  ```powershell
  az login
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  python -m pip install -r requirements.txt
  ```
3. En **Project overview**, copia el **project endpoint**. Configura estas variables en la
  misma terminal; usa los nombres y versiones exactos publicados en **Agents**:
  ```powershell
  $env:FOUNDRY_PROJECT_ENDPOINT = "https://<recurso>.services.ai.azure.com/api/projects/<proyecto>"
  $env:FOUNDRY_MODEL = "gpt-5"
  $env:AGENTE_PRODUCTO = "agente-producto"
  $env:AGENTE_PRODUCTO_VERSION = "1"
  $env:AGENTE_CUMPLIMIENTO = "agente-cumplimiento-riesgo"
  $env:AGENTE_CUMPLIMIENTO_VERSION = "1"
  ```
4. Ejecuta `python demo_b_orquestador.py`. Cuando aparezca `Pregunta para el sistema
  multiagente:`, escribe solamente la pregunta, no vuelvas a pegar el comando `python`.
  También puedes pasar la pregunta directamente entre comillas:
  ```powershell
  python .\demo_b_orquestador.py "Explícame el Crédito PyME y valida la política aplicable."
  ```
  La aplicación conecta los dos Prompt Agents existentes como `FoundryAgent`, ejecuta ambos
  especialistas en paralelo con prompts de alcance separados y usa un agente administrador
  para sintetizar las dos respuestas.
5. Prueba con la pregunta objetivo de esta guía y confirma:
  - intervención del especialista de Producto;
  - intervención del especialista de Cumplimiento/Riesgo;
  - recuperación desde las dos bases de Foundry IQ;
  - respuesta final con referencias y sin contenido inventado.
6. Para reducir riesgo en vivo, deja el entorno instalado, una ejecución validada y la
  pregunta copiada antes de la demo. No cambies versiones de agentes durante la demo.

### P3. Conectar voz + avatar

1. Crea un recurso **Azure AI Speech** de nivel **Standard S0** en una región compatible con
  avatar en tiempo real. Valida primero el personaje y la latencia en **Speech Studio → Text to
  speech avatar → Real-time avatar**.
2. La implementación local usa:
  - `voice_avatar.html`: micrófono, interfaz y vídeo WebRTC del avatar.
  - `voice_avatar_app.py`: API que protege la clave de Speech y llama al Agent Framework.
  - `demo_b_orquestador.py`: especialistas en paralelo y síntesis fundamentada.
3. Configura las variables en PowerShell. La aplicación usa `DefaultAzureCredential` y el inicio
  de sesión de Azure CLI; no requiere una clave local:
  ```powershell
  $env:SPEECH_REGION = "<región-sin-espacios>"
  $env:SPEECH_ENDPOINT = "https://<recurso-speech>.cognitiveservices.azure.com"
  $env:SPEECH_VOICE = "es-MX-DaliaNeural"
  $env:AVATAR_CHARACTER = "lisa"
  $env:AVATAR_STYLE = "casual-sitting"
  ```
  La identidad necesita **Cognitive Services Speech User** en el recurso. Si un entorno aislado
  exige autenticación local, `SPEECH_KEY` sigue siendo compatible, pero nunca se guarda en HTML.
4. En esa misma terminal, conserva las variables de Foundry y ejecuta:
  ```powershell
  python -m uvicorn voice_avatar_app:app --host 127.0.0.1 --port 8010
  ```
5. Abre `http://127.0.0.1:8010` en Edge o Chrome. Selecciona **Conectar avatar**, permite el
  micrófono, dicta la pregunta y selecciona **Consultar**. El avatar reproduce únicamente la
  síntesis final; las respuestas de los especialistas permanecen como evidencia interna.
6. Si WebRTC está bloqueado, permite salida a `relay.communication.microsoft.com` por UDP 3478
  o TCP 443. La página usa voz local como contingencia si el avatar no está conectado.
7. **GRABA UN VIDEO** de la demo funcionando de punta a punta (es el respaldo #1).

### P4. Guardrails (para el cierre)

#### Content Safety

1. Los deployments `gpt-5` y `text-embedding-3-small` ya tienen asociada la política
  `Microsoft.DefaultV2`. Esta política aplica filtros predeterminados y no debe desactivarse.
2. Para comprobarlo por CLI:
  ```powershell
  az cognitiveservices account deployment list `
    --name <recurso-foundry> `
    --resource-group <grupo-de-recursos> `
    --query "[].{deployment:name,policy:properties.raiPolicyName}" -o table
  ```
3. Si necesitas una política personalizada, abre **Foundry → proyecto → Models + endpoints**,
  selecciona el deployment `gpt-5`, elige **Edit** y asocia el filtro. En Foundry classic, la
  creación está en **Guardrails + controls → Content filters → Create content filter**.
4. Para esta demo conserva, como mínimo, violencia, odio, contenido sexual y autolesión en el
  umbral predeterminado; mantén **Prompt Shields** activo. No uses `No filters` ni `Annotate only`.

### P5. Conocimiento por sector (preparado antes de la demo)

Opción elegida: un solo par de bases sirve a los dos sectores. No se recargan archivos
entre escenarios; solo cambia la pregunta objetivo.

- **kb-productos-demo:** `Ficha_Credito_Pyme.pdf` y `Ficha_Cuenta_Empresarial.pdf` (Banca);
  `Ficha_Producto_Contoso_CardioMax.pdf` y `Ficha_Producto_Contoso_DermaCare.pdf` (Farmacia).
- **kb-cumplimiento-demo:** `Politica_Acceso_Datos_y_Cambios_Bank.pdf` (POL-SEG-007, Banca);
  `Politica_Descuentos_Comerciales_Pharma.pdf` (POL-COM-014, Farmacia comercial);
  `Politica_Autorizacion_Medical.pdf` (POL-IMG-001, Farmacia clínico — escenario opcional).

## Arranque del servidor local (método definitivo `.env`)

Procedimiento oficial para conectar el servidor el día de la demo. Usa el archivo `.env`
(en la carpeta del proyecto) en lugar de variables `$env:` sueltas.

**Requisito de carpeta:** todos los comandos se ejecutan desde la carpeta que contiene los
`.py` — la raíz del proyecto — **no** desde la subcarpeta `Guias`.

1. **Abre una terminal PowerShell en la carpeta del proyecto:**
  ```powershell
  cd "<ruta-a-la-carpeta-del-proyecto>"
  ```
2. **Confirma que el archivo `.env` existe y tiene los valores** (a partir de `.env.example`):
  ```powershell
  Get-Content .\.env
  ```
  Debe contener, como mínimo:
  ```dotenv
  FOUNDRY_PROJECT_ENDPOINT=https://<recurso-foundry>.services.ai.azure.com/api/projects/<proyecto>
  SPEECH_REGION=<region>
  SPEECH_ENDPOINT=https://<recurso-speech>.cognitiveservices.azure.com
  ```
3. **Inicia sesión en Azure** (el orquestador usa `AzureCliCredential` y la app usa
  `DefaultAzureCredential`; sin esto, las consultas fallan con 401):
  ```powershell
  az login
  ```
  Tu identidad necesita **Cognitive Services Speech User** en el recurso de Speech y acceso al
  proyecto de Foundry.
4. **Libera el puerto 8010** por si quedó un servidor anterior encendido (evita `Errno 10048`):
  ```powershell
  Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -Expand OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force }
  ```
5. **Levanta el servidor cargando el `.env`** (el flag `--env-file` es lo que hace que la app
  vea las variables; la app no lee `.env` por sí sola):
  ```powershell
  python -m uvicorn voice_avatar_app:app --host 127.0.0.1 --port 8010 --env-file .env
  ```
  Espera la línea `Uvicorn running on http://127.0.0.1:8010`.
6. **Verifica la configuración** en otra terminal (o en el navegador) abriendo
  `http://127.0.0.1:8010/api/health`. El objetivo es:
  ```json
  {"foundryConfigured": true, "speechConfigured": true}
  ```
  Si algún valor es `false`, revisa el `.env` y reinicia el servidor.
7. **Abre `http://127.0.0.1:8010`** en Edge o Chrome. Selecciona **Conectar avatar**, permite el
  micrófono, dicta la pregunta objetivo y selecciona **Consultar**.
8. **Para detener el servidor:** `Ctrl + C` en la terminal donde corre uvicorn.

**Solución rápida de problemas:**

- `ERR_CONNECTION_REFUSED` → el servidor no está corriendo; repite el paso 5.
- `503 Falta la variable de entorno ...` → arrancaste sin `--env-file .env` o el `.env` está
  incompleto; detén (Ctrl+C) y vuelve a lanzar con el paso 5.
- `401 / credencial` en la consulta → falta `az login` (paso 3) o falta el rol Speech User.
- El avatar no conecta → usa la voz local como contingencia y ten listo el video de respaldo.

---

# PARTE 2 — PRESENTAR LA DEMO

## Resumen operativo — qué mostrar y cómo

Vista de una sola mirada. Cada fila es un momento de la demo: qué pantalla abres, qué haces y
qué debe verse. Las preguntas objetivo por sector están más abajo.

| # | Momento | Pantalla | Qué haces | Resultado que se debe ver |
|---|---|---|---|---|
| 1 | Apertura | Pantalla inicial | Presentas el sistema de agentes especializados | El cliente entiende: un agente vs. varios especialistas coordinados |
| 2 | Enmarcar Foundry | Proyecto Foundry + `asyncio.gather` | Muestras `agente-producto` (kb-productos) y `agente-cumplimiento-riesgo` (kb-cumplimiento) | Dos especialistas separados + orquestador |
| 3 | Demo — voz (Banca) | `http://127.0.0.1:8010` | Dictas Crédito PyME + exportar expediente | **No cumple** + citas `Ficha_Credito_Pyme.pdf` y `Politica_Acceso_Datos_y_Cambios_Bank.pdf` |
| 4 | Variante Farmacia | Misma página | Dictas CardioMax + 25% de descuento | **No cumple** (>20%) + cita **POL-COM-014 R1** |
| 5 | Clínico (opcional) | Misma página | Dictas TAC con contraste sin creatinina | **No cumple** + cita **POL-IMG-001 R2/R6** |
| 6 | Gobierno | Deployment / Content Safety | Muestras RBAC, DLP, `Microsoft.DefaultV2` y Prompt Shields | Gobierno por arquitectura, sin métricas no configuradas |
| 7 | Cierre | Pantalla de la demo | Cierras con el mensaje central | Escalar a multiagente sin perder trazabilidad |

> Antes de empezar, revisa el **Checklist antes de entrar** al final. Si algo falla en vivo,
> usa el **Plan B**. El servidor debe estar levantado siguiendo **Parte 1 → Arranque del
> servidor local** antes de compartir pantalla.

## Pregunta objetivo por sector

- **Banca (gobierno):** "¿Un analista puede exportar el expediente de un Crédito PyME a su
  correo personal?" → Producto ubica el crédito y Riesgo/Cumplimiento responde que no, conforme
  a DLP / POL-SEG-007 R3, citando `Ficha_Credito_Pyme.pdf` y
  `Politica_Acceso_Datos_y_Cambios_Bank.pdf`.
- **Farmacia (comercial):** "Dame la ficha de CardioMax y dime si aplica un 25% de descuento a
  un cliente que está al corriente." → Producto entrega la ficha y Cumplimiento responde que un
  25% supera el 20% y requiere autorización de Dirección Comercial, conforme a POL-COM-014 R1,
  citando `Ficha_Producto_Contoso_CardioMax.pdf` y `Politica_Descuentos_Comerciales_Pharma.pdf`.
- **Farmacia (clínico, opcional):** "¿Puedo autorizar una TAC con contraste sin creatinina
  previa?" → escenario solo de cumplimiento (sin ficha de producto): responde No cumple y cita
  POL-IMG-001 R2/R6 desde `Politica_Autorizacion_Medical.pdf`.

## Versión corta

- **1 min:** mensaje central y contexto.
- **1 min:** enmarcar Foundry (dos especialistas y el orquestador).
- **3 min:** Foundry con una pregunta de voz (Banca) y las dos citas PDF.
- **1 min:** variante Farmacia con la cita de POL-COM-014.
- **1 min:** gobierno y guardrails.

Omite el recorrido por el código y el escenario clínico opcional. No omitas las fuentes de la
respuesta final.

## Preguntas probables del cliente

### ¿El modelo aprende con nuestros documentos?

> En esta solución los documentos se recuperan como conocimiento para fundamentar la consulta. No
> debemos afirmar que se usan para reentrenar el modelo. La retención y el uso de datos dependen de
> la configuración y de los términos del servicio aplicables.

### ¿Qué evita que el agente invente?

> Combinamos instrucciones restrictivas, recuperación desde fuentes autorizadas, separación de
> responsabilidades y validación de citas. Esto reduce el riesgo, pero no elimina la necesidad de
> evaluación, monitoreo y revisión humana en decisiones de alto impacto.

### ¿El avatar toma decisiones?

> No. El avatar es la interfaz de voz y video. La respuesta viene del orquestador y de los agentes
> especialistas.

### ¿Esto reemplaza a un analista de cumplimiento?

> No en decisiones de alto impacto. Puede acelerar el análisis preliminar, aplicar criterios de
> forma consistente y escalar excepciones, manteniendo supervisión humana.

### ¿Por qué no mostrarán OpenTelemetry?

> No forma parte del alcance de esta demostración. Preferimos mostrar únicamente controles que
> están configurados y validados. En una implementación productiva, la estrategia de monitoreo y
> auditoría se define según los requisitos operativos y regulatorios.

## Checklist antes de entrar

- [ ] Dejar las preguntas de voz preparadas en un bloc para pegarlas si falla el micrófono.
- [ ] Abrir Foundry en los agentes y bases correctos.
- [ ] Liberar el puerto 8010, iniciar `uvicorn` con `--env-file .env` y validar `http://127.0.0.1:8010/api/health` en `true/true`.
- [ ] Abrir la página local y conectar el avatar antes de compartir pantalla.
- [ ] Confirmar `Microsoft.DefaultV2` y Prompt Shields.
- [ ] Tener video, capturas y respuestas exitosas como respaldo.
- [ ] Cerrar pestañas, notificaciones y datos no relacionados con la demo.

## Plan B

- Si el avatar falla, continúa con texto o voz sin avatar; la arquitectura no cambia.
- Si el micrófono falla, pega la pregunta preparada y selecciona **Consultar**.
- Si Foundry no responde, muestra el video y luego abre los especialistas por separado.
- Si la voz en tiempo real no está disponible en la región, el agente responde **texto** y luego
   lo pasas por **TTS**.
- Si la red del cliente bloquea el WebSocket del avatar, prueba en sitio con antelación o usa
   hotspot; si no, usa el video.
- Si la página local rechaza la conexión o aparece `Errno 10048` (puerto ocupado), libera el
   puerto 8010 (`Get-NetTCPConnection -LocalPort 8010 ... | Stop-Process`) y reinicia Uvicorn con `--env-file .env`.

## Frases que conviene evitar

- "El agente nunca alucina". Usa: "reducimos el riesgo y exigimos evidencia".
- "Los datos nunca salen de Azure" sin revisar la arquitectura completa y el contrato aplicable.
- "DLP ya está aplicado técnicamente en toda la solución". En la demo, DLP es una política
   consultada por el agente de cumplimiento.
- "El avatar es el agente". El avatar es solamente la interfaz.
- "Esto automatiza decisiones regulatorias". Usa: "asiste el análisis y mantiene supervisión
   humana".
