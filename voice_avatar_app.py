import os
from pathlib import Path

import httpx
from azure.identity.aio import DefaultAzureCredential
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from demo_b_orquestador import orchestrate


ROOT = Path(__file__).resolve().parent
app = FastAPI(title="Asistente Multiagente con Avatar")


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


def required_environment(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise HTTPException(
            status_code=503,
            detail=f"Falta la variable de entorno {name} en el servidor.",
        )
    return value


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(ROOT / "voice_avatar.html")


@app.get("/api/health")
async def health() -> dict[str, bool]:
    return {
        "foundryConfigured": bool(os.getenv("FOUNDRY_PROJECT_ENDPOINT")),
        "speechConfigured": all(
            os.getenv(name) for name in ("SPEECH_REGION", "SPEECH_ENDPOINT")
        ),
    }


@app.get("/api/speech/session")
async def speech_session() -> dict[str, object]:
    speech_region = required_environment("SPEECH_REGION")
    speech_endpoint = required_environment("SPEECH_ENDPOINT").rstrip("/")
    speech_key = os.getenv("SPEECH_KEY")
    if speech_key:
        headers = {"Ocp-Apim-Subscription-Key": speech_key}
    else:
        async with DefaultAzureCredential() as credential:
            access_token = await credential.get_token(
                "https://cognitiveservices.azure.com/.default"
            )
        headers = {"Authorization": f"Bearer {access_token.token}"}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            token_response = await client.post(
                f"{speech_endpoint}/sts/v1.0/issueToken",
                headers=headers,
            )
            token_response.raise_for_status()
            relay_response = await client.get(
                f"{speech_endpoint}/tts/cognitiveservices/avatar/relay/token/v1",
                headers=headers,
            )
            relay_response.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail=f"No fue posible iniciar Azure Speech: {error}",
        ) from error

    return {
        "token": token_response.text,
        "region": speech_region,
        "relay": relay_response.json(),
        "voice": os.getenv("SPEECH_VOICE", "es-MX-DaliaNeural"),
        "avatarCharacter": os.getenv("AVATAR_CHARACTER", "lisa"),
        "avatarStyle": os.getenv("AVATAR_STYLE", "casual-sitting"),
    }


@app.post("/api/ask")
async def ask(request: AskRequest) -> dict[str, str]:
    try:
        return await orchestrate(request.question.strip())
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
