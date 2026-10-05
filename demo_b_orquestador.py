import asyncio
import os
import re
import sys
import time
from collections.abc import Iterable
from threading import Lock
from typing import Any

import httpx
from agent_framework import Agent
from agent_framework.foundry import FoundryAgent, FoundryChatClient
from azure.identity.aio import AzureCliCredential

from pricing import resolve_prices


def required_environment(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Falta la variable de entorno {name}.")
    return value


# gpt-5 es un modelo de razonamiento: bajar el esfuerzo reduce la latencia a la mitad.
SPECIALIST_KWARGS = {"reasoning": {"effort": "low"}}
SYNTHESIS_KWARGS = {"reasoning": {"effort": "minimal"}}

# ---- AI FinOps (Fase 1: métricas reales a nivel de app) ----
# Precios de DEMOSTRACIÓN por 1M de tokens (USD). Ajusta a tu tarifa real vía .env.
PRICE_INPUT_PER_1M = float(os.getenv("FINOPS_PRICE_INPUT_PER_1M", "1.25"))
PRICE_OUTPUT_PER_1M = float(os.getenv("FINOPS_PRICE_OUTPUT_PER_1M", "10.0"))

# Unidades de negocio para el selector de gobernanza (llave/cuota por consumidor).
BUSINESS_UNITS = {
    "banca-retail": "Banca Retail",
    "banca-pyme": "Banca PyME",
    "banca-empresarial": "Banca Empresarial",
}
DEFAULT_BUSINESS_UNIT = "banca-retail"

# ---- AI Gateway (APIM) — Fase 2 ----
# Si APIM_GATEWAY_URL y la key de la unidad de negocio están definidas, la SÍNTESIS
# del orquestador pasa por el AI Gateway (APIM). Si no, usa el camino Foundry directo.
APIM_GATEWAY_URL = os.getenv("APIM_GATEWAY_URL", "").rstrip("/")
APIM_DEPLOYMENT = os.getenv("APIM_DEPLOYMENT", "gpt-5")
APIM_API_VERSION = os.getenv("APIM_API_VERSION", "2025-04-01-preview")
APIM_KEYS = {
    "banca-retail": os.getenv("APIM_KEY_BANCA_RETAIL", ""),
    "banca-pyme": os.getenv("APIM_KEY_BANCA_PYME", ""),
    "banca-empresarial": os.getenv("APIM_KEY_BANCA_EMPRESARIAL", ""),
}

MANAGER_INSTRUCTIONS = (
    "Coordina una consulta que necesita evidencia de producto y de "
    "cumplimiento. Selecciona producto y cumplimiento_riesgo una sola vez "
    "cada uno. Cuando ambos hayan respondido, termina y redacta en "
    "final_message una síntesis clara en español. Conserva sus citas, "
    "separa hechos de inferencias y no inventes información ausente."
)


def _apim_key_for(business_unit: str) -> str:
    return APIM_KEYS.get(business_unit, "")


def _apim_enabled(business_unit: str) -> bool:
    return bool(APIM_GATEWAY_URL and _apim_key_for(business_unit))


# ---- Seguridad (Content Safety / jailbreak) ----
CONTENT_SAFETY_MESSAGE = (
    "🛡️ Solicitud bloqueada por Azure AI Content Safety: se detectó un intento de "
    "jailbreak o contenido no permitido. El modelo y el AI Gateway rechazaron la "
    "petición antes de generar una respuesta. No se expuso ningún dato ni instrucción."
)
_CONTENT_SAFETY_MARKERS = (
    "content_filter",
    "contentfilter",
    "responsibleai",
    "jailbreak",
    "content management policy",
    "content_filter_result",
)


def _is_content_safety_block(text: str) -> bool:
    low = (text or "").lower()
    return any(marker in low for marker in _CONTENT_SAFETY_MARKERS)


_session_lock = Lock()
_session_state: dict[str, float] = {"acumulado": 0.0, "ahorro": 0.0}
_answer_cache: dict[tuple[str, str], dict[str, Any]] = {}


def reset_session() -> None:
    """Reinicia acumulados y caché — útil para empezar una demo limpia."""
    with _session_lock:
        _session_state["acumulado"] = 0.0
        _session_state["ahorro"] = 0.0
        _answer_cache.clear()


def _usage_of(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage_details", None) or {}

    def value(key: str) -> int:
        raw = usage.get(key) if isinstance(usage, dict) else getattr(usage, key, None)
        return int(raw) if raw else 0

    return value("input_token_count"), value("output_token_count")


def _estimated_cost(tokens_in: int, tokens_out: int) -> float:
    return tokens_in / 1_000_000 * PRICE_INPUT_PER_1M + tokens_out / 1_000_000 * PRICE_OUTPUT_PER_1M


def _build_metrics(
    *,
    business_unit: str,
    bu_name: str,
    tokens_in: int,
    tokens_out: int,
    cost: float,
    cache_hit: bool,
    cache_savings: float,
    started: float,
    session_cost: float,
    session_savings: float,
    source: str = "app",
    gateway_consumed: int | None = None,
    gateway_remaining: int | None = None,
    price_input: float = PRICE_INPUT_PER_1M,
    price_output: float = PRICE_OUTPUT_PER_1M,
    price_source: str = "fixed",
) -> dict[str, Any]:
    return {
        "businessUnit": bu_name,
        "businessUnitId": business_unit,
        "tokensPrompt": tokens_in,
        "tokensCompletion": tokens_out,
        "tokensTotal": tokens_in + tokens_out,
        "costEstimated": round(cost, 4),
        "cacheHit": cache_hit,
        "cacheSavings": round(cache_savings, 4),
        "latencyMs": int((time.perf_counter() - started) * 1000),
        "sessionCost": round(session_cost, 4),
        "sessionSavings": round(session_savings, 4),
        "gatewayCache": "HIT" if cache_hit else "MISS",
        "gatewayStatus": "OK",
        "gatewayConsumedTokens": gateway_consumed,
        "gatewayRemainingTokens": gateway_remaining,
        "source": source,
        "priceInputPer1M": round(price_input, 4),
        "priceOutputPer1M": round(price_output, 4),
        "priceSource": price_source,
    }


async def _synthesize_via_apim(
    system_prompt: str, user_prompt: str, api_key: str
) -> tuple[str, int, int, int | None, int | None]:
    """Ejecuta la síntesis a través del AI Gateway (APIM) y devuelve texto + métricas."""
    url = (
        f"{APIM_GATEWAY_URL}/openai/deployments/{APIM_DEPLOYMENT}"
        f"/chat/completions?api-version={APIM_API_VERSION}"
    )
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    transient = (
        httpx.ConnectError,
        httpx.ConnectTimeout,
        httpx.ReadError,
        httpx.ReadTimeout,
        httpx.RemoteProtocolError,
    )
    async with httpx.AsyncClient(timeout=120) as client:
        response = None
        for attempt in range(3):
            try:
                response = await client.post(
                    url,
                    json={"messages": messages, "reasoning_effort": "minimal"},
                    headers=headers,
                )
                if response.status_code == 400:
                    if _is_content_safety_block(response.text):
                        raise RuntimeError(CONTENT_SAFETY_MESSAGE)
                    # gpt-5 en algunas versiones rechaza reasoning_effort: reintenta sin él.
                    response = await client.post(
                        url, json={"messages": messages}, headers=headers
                    )
                    if response.status_code == 400 and _is_content_safety_block(response.text):
                        raise RuntimeError(CONTENT_SAFETY_MESSAGE)
                break
            except transient:
                if attempt == 2:
                    raise
                await asyncio.sleep(1.0 * (attempt + 1))
        if response.status_code == 429:
            retry_after = response.headers.get("retry-after")
            raise RuntimeError(
                "Cuota del AI Gateway agotada para esta unidad de negocio (HTTP 429). "
                + (f"Reintenta en {retry_after}s. " if retry_after else "")
                + "El límite de tokens/min configurado en APIM bloqueó la llamada — "
                "esto demuestra la gobernanza por consumidor."
            )
        response.raise_for_status()
        data = response.json()

        def header_int(name: str) -> int | None:
            raw = response.headers.get(name)
            return int(raw) if raw and raw.lstrip("-").isdigit() else None

        gateway_consumed = header_int("x-bu-consumed-tokens")
        gateway_remaining = header_int("x-bu-remaining-tokens")

    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {}) or {}
    tokens_in = int(usage.get("prompt_tokens", 0) or 0)
    tokens_out = int(usage.get("completion_tokens", 0) or 0)
    return text, tokens_in, tokens_out, gateway_consumed, gateway_remaining


def render_output(value: Any) -> str:
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
        rendered = [render_output(item) for item in value]
        return "\n".join(item for item in rendered if item)

    text = getattr(value, "text", None)
    if text:
        author = getattr(value, "author_name", None)
        return f"[{author}] {text}" if author else str(text)

    return str(value) if value is not None else ""


def has_source_evidence(text: str) -> bool:
    normalized = text.casefold()
    if "no encontrado en las fuentes" in normalized:
        return False

    return ".pdf" in normalized


def has_blank_source(text: str) -> bool:
    return bool(re.search(r"(?im)^\s*(?:[-*]\s*)?fuente\s*:\s*$", text))


async def orchestrate(task: str, business_unit: str = DEFAULT_BUSINESS_UNIT) -> dict[str, Any]:
    started = time.perf_counter()
    bu_name = BUSINESS_UNITS.get(business_unit, BUSINESS_UNITS[DEFAULT_BUSINESS_UNIT])
    cache_key = (business_unit, " ".join(task.lower().split()))

    cached = _answer_cache.get(cache_key)
    if cached is not None:
        saved = float(cached.get("cost", 0.0))
        price_in, price_out, price_source = await resolve_prices()
        with _session_lock:
            _session_state["ahorro"] += saved
            session_cost = _session_state["acumulado"]
            session_savings = _session_state["ahorro"]
        return {
            "product": cached["product"],
            "compliance": cached["compliance"],
            "final": cached["final"],
            "metrics": _build_metrics(
                business_unit=business_unit,
                bu_name=bu_name,
                tokens_in=0,
                tokens_out=0,
                cost=0.0,
                cache_hit=True,
                cache_savings=saved,
                started=started,
                session_cost=session_cost,
                session_savings=session_savings,
                price_input=price_in,
                price_output=price_out,
                price_source=price_source,
            ),
        }

    project_endpoint = required_environment("FOUNDRY_PROJECT_ENDPOINT")
    product_name = os.getenv("AGENTE_PRODUCTO", "agente-producto")
    product_version = os.getenv("AGENTE_PRODUCTO_VERSION", "1")
    compliance_name = os.getenv(
        "AGENTE_CUMPLIMIENTO", "agente-cumplimiento-riesgo"
    )
    compliance_version = os.getenv("AGENTE_CUMPLIMIENTO_VERSION", "1")

    print(
        "Agentes publicados: "
        f"{product_name} v{product_version} | "
        f"{compliance_name} v{compliance_version}"
    )

    async with AzureCliCredential(process_timeout=30) as credential:
        product_agent = FoundryAgent(
            project_endpoint=project_endpoint,
            agent_name=product_name,
            agent_version=product_version,
            credential=credential,
            name="producto",
            description=(
                "Especialista que consulta Foundry IQ para responder sobre productos "
                "y conservar las referencias de las fuentes."
            ),
        )

        compliance_agent = FoundryAgent(
            project_endpoint=project_endpoint,
            agent_name=compliance_name,
            agent_version=compliance_version,
            credential=credential,
            name="cumplimiento_riesgo",
            description=(
                "Especialista que consulta Foundry IQ para validar políticas, "
                "riesgos y cumplimiento con sus referencias."
            ),
        )

        manager = Agent(
            client=FoundryChatClient(
                project_endpoint=project_endpoint,
                model=os.getenv("FOUNDRY_MODEL", "gpt-5"),
                credential=credential,
            ),
            name="orquestador",
            description="Coordina los especialistas y produce la respuesta final.",
            instructions=MANAGER_INSTRUCTIONS,
        )

        product_prompt = f"""Consulta obligatoriamente tu herramienta de Foundry IQ.
Responde únicamente la parte de producto de esta solicitud y cita el nombre exacto de
    la fuente recuperada. Termina obligatoriamente con `Fuente: <nombre exacto>.pdf`.
    Nunca dejes `Fuente:` vacío y no sustituyas el nombre del archivo por el título interno
    del documento. Ignora por completo cualquier solicitud de cumplimiento, riesgo,
    acceso o manejo de datos: no la evalúes ni la menciones. No uses conocimiento general.
    Si la base no contiene evidencia de producto, responde: No encontrado en las fuentes.

Solicitud: {task}
"""
        compliance_prompt = f"""Consulta obligatoriamente tu herramienta de Foundry IQ.
Responde únicamente la parte de riesgo y cumplimiento de esta solicitud. Indica Cumple,
No cumple o Información insuficiente, y cita la regla y el nombre exacto del archivo.
    Termina obligatoriamente con `Fuente: <nombre exacto>.pdf`. Nunca dejes `Fuente:` vacío
    y no sustituyas el nombre del archivo por el título interno o código del documento.
    Ignora por completo cualquier solicitud de descripción, monto, plazo o requisitos del
    producto: no respondas ni menciones esa parte. No uses conocimiento general. Si la base
    no contiene evidencia de cumplimiento, responde: No encontrado en las fuentes.

Solicitud: {task}
"""

        try:
            product_response, compliance_response = await asyncio.gather(
                product_agent.run(product_prompt, client_kwargs=SPECIALIST_KWARGS),
                compliance_agent.run(compliance_prompt, client_kwargs=SPECIALIST_KWARGS),
            )
        except Exception as exc:  # noqa: BLE001
            if _is_content_safety_block(str(exc)):
                raise RuntimeError(CONTENT_SAFETY_MESSAGE) from exc
            raise
        product_text = render_output(product_response)
        compliance_text = render_output(compliance_response)

        missing_evidence = []
        if not has_source_evidence(product_text):
            missing_evidence.append("Producto")
        if not has_source_evidence(compliance_text):
            missing_evidence.append("Cumplimiento/Riesgo")
        if len(missing_evidence) == 2:
            raise RuntimeError(
                "Sin evidencia de Foundry IQ en Producto ni Cumplimiento/Riesgo. "
                "Verifica que las bases de "
                "conocimiento estén conectadas y publicadas en las versiones configuradas."
            )

        synthesis_prompt = f"""Pregunta original:
{task}

Respuesta del especialista de Producto:
{product_text}

Respuesta del especialista de Cumplimiento/Riesgo:
{compliance_text}

Sintetiza una respuesta final clara en español. Conserva las referencias de ambos
especialistas, separa hechos de inferencias y no inventes información ausente. Cada bloque
de hechos debe terminar con `Fuente: <nombre exacto>.pdf`; está prohibido dejar `Fuente:`
vacío o usar solamente el título interno del documento. Termina con una sección "Fuentes"
que enumere únicamente los nombres exactos de los archivos `.pdf` citados.
Si un especialista responde "No encontrado en las fuentes", no crees un bloque ni una
fuente para ese dominio. Responde con la evidencia disponible del otro especialista y
señala brevemente que el dominio ausente no aplica a la pregunta formulada.
"""
        use_apim = _apim_enabled(business_unit)
        gateway_consumed: int | None = None
        gateway_remaining: int | None = None
        final_text = ""
        tokens_in_final = tokens_out_final = 0
        if use_apim:
            try:
                (
                    final_text,
                    tokens_in_final,
                    tokens_out_final,
                    gateway_consumed,
                    gateway_remaining,
                ) = await _synthesize_via_apim(
                    MANAGER_INSTRUCTIONS, synthesis_prompt, _apim_key_for(business_unit)
                )
            except RuntimeError:
                # Cuota agotada (429): mensaje amigable — no hacer fallback.
                raise
            except httpx.HTTPError as exc:
                # Falla transitoria del gateway (red / 5xx): cae al camino Foundry directo.
                print(f"[AI Gateway] fallback a Foundry directo: {exc!r}")
                use_apim = False
        if not use_apim:
            final_response = await manager.run(
                synthesis_prompt, client_kwargs=SYNTHESIS_KWARGS
            )
            final_text = render_output(final_response)
            tokens_in_final, tokens_out_final = _usage_of(final_response)

        if has_blank_source(final_text):
            raise RuntimeError(
                "La síntesis generó una cita vacía. Repite la consulta para conservar "
                "los nombres exactos de los archivos recuperados."
            )

        tokens_in_product, tokens_out_product = _usage_of(product_response)
        tokens_in_compliance, tokens_out_compliance = _usage_of(compliance_response)
        tokens_in = tokens_in_product + tokens_in_compliance + tokens_in_final
        tokens_out = tokens_out_product + tokens_out_compliance + tokens_out_final
        price_in, price_out, price_source = await resolve_prices()
        cost = tokens_in / 1_000_000 * price_in + tokens_out / 1_000_000 * price_out

        result: dict[str, Any] = {
            "product": product_text,
            "compliance": compliance_text,
            "final": final_text,
        }

        with _session_lock:
            _session_state["acumulado"] += cost
            _answer_cache[cache_key] = {**result, "cost": cost}
            session_cost = _session_state["acumulado"]
            session_savings = _session_state["ahorro"]

        result["metrics"] = _build_metrics(
            business_unit=business_unit,
            bu_name=bu_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            cache_hit=False,
            cache_savings=0.0,
            started=started,
            session_cost=session_cost,
            session_savings=session_savings,
            source="apim" if use_apim else "app",
            gateway_consumed=gateway_consumed,
            gateway_remaining=gateway_remaining,
            price_input=price_in,
            price_output=price_out,
            price_source=price_source,
        )
        return result


async def run(task: str) -> None:
    result = await orchestrate(task)

    print("\n--- Especialista: Producto ---")
    print(result["product"])
    print("\n--- Especialista: Cumplimiento/Riesgo ---")
    print(result["compliance"])
    print("\n=== Respuesta final ===")
    print(result["final"])


def main() -> None:
    task = " ".join(sys.argv[1:]).strip()
    if not task:
        task = input("Pregunta para el sistema multiagente: ").strip()
    if not task:
        raise RuntimeError("La pregunta no puede estar vacía.")

    asyncio.run(run(task))


if __name__ == "__main__":
    main()