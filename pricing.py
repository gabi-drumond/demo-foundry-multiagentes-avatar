"""Resolución de precios de tokens desde la Azure Retail Prices API (con fallback).

- Fuente real: https://prices.azure.com/api/retail/prices (pública, sin auth),
  servicio "Foundry Models". Devuelve el precio de LISTA por token del modelo.
- Si la API no responde o el meter no se resuelve, cae a los precios del .env.
- Cachea el resultado 24h (los precios cambian rara vez).

Nota: es precio de LISTA (retail), no el precio EA/negociado. El costo facturado
real (actuals) vive en Azure Cost Management, con retraso de horas.
"""
from __future__ import annotations

import os
import time

import httpx

RETAIL_URL = "https://prices.azure.com/api/retail/prices"

# Fallback (por 1M de tokens, USD). Coinciden con la tarifa pública de gpt-5.
FALLBACK_INPUT_PER_1M = float(os.getenv("FINOPS_PRICE_INPUT_PER_1M", "1.25"))
FALLBACK_OUTPUT_PER_1M = float(os.getenv("FINOPS_PRICE_OUTPUT_PER_1M", "10.0"))

# "retail" = intentar precio real de Azure; "fixed" = usar solo los del .env.
PRICE_SOURCE = os.getenv("FINOPS_PRICE_SOURCE", "retail").lower()

# Substrings de meter (Foundry Models). Los meters glbl de la familia gpt-5
# resuelven a la tarifa real del modelo (input $1.25/1M, output $10/1M).
METER_INPUT = os.getenv("FINOPS_METER_INPUT", "gpt-5-codex-inp-glbl")
METER_OUTPUT = os.getenv("FINOPS_METER_OUTPUT", "gpt-5-codex-out-glbl")

_TTL_SECONDS = 24 * 3600
_cache: dict[str, object] = {"ts": 0.0, "input": None, "output": None, "source": "fixed"}


async def _fetch_meter_per_1m(client: httpx.AsyncClient, meter_substr: str) -> float | None:
    params = {"$filter": f"contains(meterName, '{meter_substr}')", "$top": "50"}
    response = await client.get(RETAIL_URL, params=params, timeout=15)
    response.raise_for_status()
    for item in response.json().get("Items", []):
        name = item.get("meterName", "")
        price = item.get("retailPrice")
        if meter_substr in name and price is not None:
            uom = str(item.get("unitOfMeasure", "1K"))
            multiplier = 1000 if uom.startswith("1K") else 1
            return float(price) * multiplier
    return None


async def resolve_prices() -> tuple[float, float, str]:
    """Devuelve (input_por_1M, output_por_1M, source) con cache de 24h."""
    now = time.time()
    if _cache["input"] is not None and now - float(_cache["ts"]) < _TTL_SECONDS:
        return float(_cache["input"]), float(_cache["output"]), str(_cache["source"])

    input_price, output_price, source = FALLBACK_INPUT_PER_1M, FALLBACK_OUTPUT_PER_1M, "fixed"
    if PRICE_SOURCE == "retail":
        try:
            async with httpx.AsyncClient() as client:
                fetched_in = await _fetch_meter_per_1m(client, METER_INPUT)
                fetched_out = await _fetch_meter_per_1m(client, METER_OUTPUT)
            if fetched_in and fetched_out:
                input_price, output_price, source = fetched_in, fetched_out, "retail"
        except Exception:
            pass  # red/API caída → fallback seguro

    _cache.update({"ts": now, "input": input_price, "output": output_price, "source": source})
    return input_price, output_price, source
