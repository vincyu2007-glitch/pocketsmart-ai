"""Google Gemini client.

Supports both the current unified SDK (``google-genai``) and the legacy
``google-generativeai`` package, preferring the former. Adds:

* automatic JSON extraction from noisy model output (markdown fences, prose),
* schema-driven coercion + validation of the response,
* bounded exponential backoff on transient API errors,
* a model-listing helper used by the "model research" tooling.
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from typing import Any

log = logging.getLogger(__name__)

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_TRANSIENT = (
    "429",
    "500",
    "502",
    "503",
    "504",
    "rate limit",
    "quota",
    "resource_exhausted",
    "unavailable",
    "deadline",
    "overloaded",
    "timeout",
    "timed out",
    "connection",
    "temporarily",
)


class GeminiError(RuntimeError):
    """Any failure while talking to the Gemini API."""


class GeminiNotConfigured(GeminiError):
    """Raised when no API key is available."""


def extract_json(text: str) -> Any:
    """Pull the first JSON value out of arbitrary model output."""
    if not text:
        raise GeminiError("Empty response from the model.")

    candidates = [text.strip()]

    fenced = _JSON_FENCE.search(text)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())

    for opening, closing in (("{", "}"), ("[", "]")):
        start = text.find(opening)
        while start != -1:
            depth = 0
            in_string = False
            escaped = False
            for index in range(start, len(text)):
                char = text[index]
                if in_string:
                    if escaped:
                        escaped = False
                    elif char == "\\":
                        escaped = True
                    elif char == '"':
                        in_string = False
                    continue
                if char == '"':
                    in_string = True
                elif char == opening:
                    depth += 1
                elif char == closing:
                    depth -= 1
                    if depth == 0:
                        candidates.append(text[start : index + 1])
                        break
            start = text.find(opening, start + 1)

    for candidate in candidates:
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # Last resort: strip trailing commas.
            repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                continue

    raise GeminiError("The model did not return parsable JSON.")


def _is_transient(error: Exception) -> bool:
    message = f"{type(error).__name__}: {error}".lower()
    return any(token in message for token in _TRANSIENT)


def coerce_number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        try:
            if value != value or value in (float("inf"), float("-inf")):
                return default
        except TypeError:  # pragma: no cover - defensive
            return default
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d.\-]", "", value)
        if cleaned in ("", "-", ".", "-."):
            return default
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


def coerce_int(value: Any, default: int = 0) -> int:
    return int(round(coerce_number(value, default)))


def coerce_str_list(value: Any, limit: int = 6) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            out.append(text[:160])
        if len(out) >= limit:
            break
    return out


def normalise_response(
    raw: Any, *, plan_type: str, budget: float
) -> dict[str, Any]:
    """Force the model's output into the shape the UI renders.

    The model is asked for this schema, but LLMs drift - this function makes
    the render path total (never raises on missing keys).
    """
    if not isinstance(raw, dict):
        raise GeminiError("Model response was not a JSON object.")
    data = raw.get("data") if isinstance(raw.get("data"), dict) else raw

    def pick(key: str, default: Any = None) -> Any:
        value = data.get(key, default)
        return default if value is None else value

    breakdown = []
    for item in pick("budget_breakdown", []) or []:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category", "")).strip()
        breakdown.append(
            {
                "category": category or "General",
                "amount": max(coerce_int(item.get("amount"), 0), 0),
                "percentage": round(coerce_number(item.get("percentage"), 0.0), 1),
                "priority": "high" if str(item.get("priority", "")).lower() == "high" else "standard",
                "notes": str(item.get("notes", "")).strip()[:280],
            }
        )

    products = []
    for item in pick("products", []) or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        products.append(
            {
                "name": name[:120],
                "category": str(item.get("category", "")).strip() or "General",
                "price": max(coerce_int(item.get("price"), 0), 0),
                "quantity": max(coerce_int(item.get("quantity"), 1), 1),
                "platform": str(item.get("platform", "")).strip()[:60],
                "search_terms": str(item.get("search_terms", "")).strip()[:160] or name,
                "why": str(item.get("why", "")).strip()[:400],
                "features": coerce_str_list(item.get("features"), 5),
                "alternatives": coerce_str_list(item.get("alternatives"), 3),
            }
        )

    cost_breakdown = []
    for item in pick("cost_breakdown", []) or []:
        if not isinstance(item, dict):
            continue
        cost_breakdown.append(
            {
                "label": str(item.get("label", "")).strip()[:100] or "Item",
                "amount": max(coerce_int(item.get("amount"), 0), 0),
                "note": str(item.get("note", "")).strip()[:200],
            }
        )

    return {
        "summary": str(pick("summary", "")).strip()[:2000]
        or "Here is a budget plan built for the inputs you provided.",
        "total_budget": coerce_int(data.get("total_budget"), int(budget)) or int(budget),
        "currency": "INR",
        "budget_breakdown": breakdown,
        "products": products,
        "cost_breakdown": cost_breakdown,
        "suggestions": coerce_str_list(pick("suggestions", []), 8),
        "warnings": coerce_str_list(pick("warnings", []), 5),
        "plan_type": plan_type,
    }


class GeminiClient:
    """Thin, defensive wrapper around the Gemini REST SDKs."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
        *,
        temperature: float = 0.4,
        max_output_tokens: int = 8192,
        timeout: int = 60,
        max_retries: int = 3,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.model = model
        self.temperature = float(temperature)
        self.max_output_tokens = int(max_output_tokens)
        self.timeout = int(timeout)
        self.max_retries = max(int(max_retries), 1)
        self._sdk = self._detect_sdk()

    # -- setup --------------------------------------------------------------
    def _detect_sdk(self) -> str | None:
        try:  # current unified SDK
            import google.genai  # noqa: F401

            return "genai"
        except ImportError:
            pass
        try:  # legacy SDK
            import google.generativeai  # noqa: F401

            return "legacy"
        except ImportError:
            return None

    @property
    def available(self) -> bool:
        return bool(self.api_key) and self._sdk is not None

    @property
    def status(self) -> dict[str, Any]:
        return {
            "configured": bool(self.api_key),
            "sdk": self._sdk or "none",
            "model": self.model,
            "available": self.available,
        }

    # -- generation ---------------------------------------------------------
    def generate_text(self, prompt: str, image: bytes | None = None, mime_type: str = "image/jpeg") -> str:
        if not self.api_key:
            raise GeminiNotConfigured(
                "GEMINI_API_KEY is not set. Add it to your .env file - see .env.example."
            )
        if self._sdk is None:
            raise GeminiNotConfigured(
                "No Gemini SDK installed. Run: pip install google-genai"
            )

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                text = self._call(prompt, image, mime_type)
                if text and text.strip():
                    return text
                raise GeminiError("The model returned an empty response.")
            except Exception as exc:  # noqa: BLE001 - re-raised below
                last_error = exc
                transient = _is_transient(exc)
                log.warning(
                    "Gemini call failed (attempt %s/%s, transient=%s): %s",
                    attempt + 1, self.max_retries, transient, exc,
                )
                if not transient or attempt == self.max_retries - 1:
                    break
                time.sleep(min(2 ** attempt + random.random(), 8))

        raise GeminiError(f"Gemini request failed: {last_error}") from last_error

    def generate_json(self, prompt: str, image: bytes | None = None, mime_type: str = "image/jpeg") -> Any:
        return extract_json(self.generate_text(prompt, image, mime_type))

    def _call(self, prompt: str, image: bytes | None, mime_type: str) -> str:
        if self._sdk == "genai":
            return self._call_genai(prompt, image, mime_type)
        return self._call_legacy(prompt, image, mime_type)

    def _call_genai(self, prompt: str, image: bytes | None, mime_type: str) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        parts = [types.Part.from_text(text=prompt)]
        if image:
            parts.append(types.Part.from_bytes(data=image, mime_type=mime_type))

        config = types.GenerateContentConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            response_mime_type="application/json",
            system_instruction=(
                "You are PocketSmart AI, an expert budget planner for the Indian "
                "market. You always answer with a single valid JSON object and "
                "never wrap it in markdown."
            ),
        )
        response = client.models.generate_content(
            model=self.model,
            contents=[types.Content(role="user", parts=parts)],
            config=config,
        )
        text = getattr(response, "text", None)
        if not text:
            raise GeminiError(_finish_reason_text(response))
        return text

    def _call_legacy(self, prompt: str, image: bytes | None, mime_type: str) -> str:
        import google.generativeai as legacy

        legacy.configure(api_key=self.api_key)
        model = legacy.GenerativeModel(
            model_name=self.model,
            system_instruction=(
                "You are PocketSmart AI, an expert budget planner for the Indian "
                "market. You always answer with a single valid JSON object and "
                "never wrap it in markdown."
            ),
        )
        parts: list[Any] = [prompt]
        if image:
            parts.append({"mime_type": mime_type, "data": image})
        response = model.generate_content(
            parts,
            generation_config={
                "temperature": self.temperature,
                "max_output_tokens": self.max_output_tokens,
                "response_mime_type": "application/json",
            },
        )
        text = getattr(response, "text", None)
        if not text:
            raise GeminiError(_finish_reason_text(response))
        return text

    # -- discovery ----------------------------------------------------------
    def list_models(self) -> list[dict[str, Any]]:
        """List models the key can use - used by scripts/list_models.py."""
        if not self.api_key:
            raise GeminiNotConfigured("GEMINI_API_KEY is not set.")
        if self._sdk == "genai":
            from google import genai

            client = genai.Client(api_key=self.api_key)
            return [
                {"name": m.name, "display_name": m.display_name}
                for m in client.models.list()
            ]
        import google.generativeai as legacy

        legacy.configure(api_key=self.api_key)
        return [{"name": m.name, "display_name": m.display_name} for m in legacy.list_models()]


def _finish_reason_text(response: Any) -> str:
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        reason = getattr(candidate, "finish_reason", None)
        if reason:
            return f"Model stopped early (finish_reason={reason})."
    return "Model returned no content."


_CLIENT_CACHE: dict[tuple, "GeminiClient"] = {}


def build_client(config) -> GeminiClient:
    """Build (and memoise) a client for the given Flask config."""
    key = (
        getattr(config, "GEMINI_API_KEY", ""),
        getattr(config, "GEMINI_MODEL", "gemini-2.5-flash"),
        float(getattr(config, "GEMINI_TEMPERATURE", 0.4)),
        int(getattr(config, "GEMINI_MAX_OUTPUT_TOKENS", 8192)),
        int(getattr(config, "GEMINI_TIMEOUT", 60)),
        int(getattr(config, "GEMINI_MAX_RETRIES", 3)),
    )
    client = _CLIENT_CACHE.get(key)
    if client is None:
        client = GeminiClient(
            api_key=key[0],
            model=key[1],
            temperature=key[2],
            max_output_tokens=key[3],
            timeout=key[4],
            max_retries=key[5],
        )
        _CLIENT_CACHE[key] = client
    return client
