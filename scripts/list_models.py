"""List the Gemini models available to the configured API key.

    python scripts/list_models.py
    python scripts/list_models.py --probe gemini-2.5-flash

Use it to confirm the key works and to pick a model id for GEMINI_MODEL.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_config  # noqa: E402
from services.gemini_client import GeminiClient, GeminiError, build_client  # noqa: E402

INTERESTING = ("flash", "pro", "lite", "vision", "image")


def main() -> int:
    config = get_config()
    client = build_client(config)

    if not client.available:
        print(f"Gemini is not available. Status: {client.status}")
        print("Set GEMINI_API_KEY in .env (see .env.example).")
        return 1

    print(f"SDK: {client._sdk}   configured model: {client.model}\n")
    try:
        models = client.list_models()
    except GeminiError as exc:
        print(f"Could not list models: {exc}")
        return 1

    if not models:
        print("No models returned for this key.")
        return 1

    print(f"{len(models)} models available:\n")
    for model in sorted(models, key=lambda m: m["name"]):
        name = model["name"]
        flag = "  <- configured" if name.split("/")[-1] == client.model else ""
        highlight = " *" if any(word in name.lower() for word in INTERESTING) else ""
        print(f"  {name}{highlight}{flag}")

    if len(sys.argv) > 1 and sys.argv[1] == "--probe":
        probe = build_client(type("C", (), {
            "GEMINI_API_KEY": config.GEMINI_API_KEY,
            "GEMINI_MODEL": sys.argv[2] if len(sys.argv) > 2 else client.model,
            "GEMINI_TEMPERATURE": 0.0,
            "GEMINI_MAX_OUTPUT_TOKENS": 256,
            "GEMINI_TIMEOUT": 30,
            "GEMINI_MAX_RETRIES": 1,
        })())
        print(f"\nProbing {probe.model} with a tiny JSON request...")
        try:
            print("  OK ->", probe.generate_json('Reply with only: {"ok": true}'))
        except GeminiError as exc:
            print("  FAILED ->", exc)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
