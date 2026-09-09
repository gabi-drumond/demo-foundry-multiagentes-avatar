import asyncio
import os
import re
import sys
from collections.abc import Iterable
from typing import Any

from agent_framework import Agent
from agent_framework.foundry import FoundryAgent, FoundryChatClient
from azure.identity.aio import AzureCliCredential


def required_environment(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Falta la variable de entorno {name}.")
    return value


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


async def orchestrate(task: str) -> dict[str, str]:
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

    async with AzureCliCredential() as credential:
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
            instructions=(
                "Coordina una consulta que necesita evidencia de producto y de "
                "cumplimiento. Selecciona producto y cumplimiento_riesgo una sola vez "
                "cada uno. Cuando ambos hayan respondido, termina y redacta en "
                "final_message una síntesis clara en español. Conserva sus citas, "
                "separa hechos de inferencias y no inventes información ausente."
            ),
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

        product_response, compliance_response = await asyncio.gather(
            product_agent.run(product_prompt),
            compliance_agent.run(compliance_prompt),
        )
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
        final_response = await manager.run(synthesis_prompt)
        final_text = render_output(final_response)
        if has_blank_source(final_text):
            raise RuntimeError(
                "La síntesis generó una cita vacía. Repite la consulta para conservar "
                "los nombres exactos de los archivos recuperados."
            )

        return {
            "product": product_text,
            "compliance": compliance_text,
            "final": final_text,
        }


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