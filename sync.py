import os
import time
import requests

LM_STUDIO_BASE = os.environ["LM_STUDIO_BASE"].rstrip("/")
LITELLM_BASE = os.environ["LITELLM_BASE"].rstrip("/")

LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY", "lm-studio")
LITELLM_MASTER_KEY = os.environ["LITELLM_MASTER_KEY"]

SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "60"))

lm_headers = {
    "Authorization": f"Bearer {LM_STUDIO_API_KEY}",
}

litellm_headers = {
    "Authorization": f"Bearer {LITELLM_MASTER_KEY}",
    "Content-Type": "application/json",
}


def extract_model_names(payload: dict) -> set[str]:
    names = set()

    for item in payload.get("data", []):
        if isinstance(item, str):
            names.add(item)
            continue

        if not isinstance(item, dict):
            continue

        name = item.get("model_name") or item.get("id")
        if name:
            names.add(name)

    return names


def get_existing_litellm_models() -> set[str]:
    for endpoint in ("/model/info", "/models"):
        response = requests.get(
            f"{LITELLM_BASE}{endpoint}",
            headers=litellm_headers,
            timeout=20,
        )

        if response.ok:
            return extract_model_names(response.json())

        if endpoint == "/model/info" and response.status_code >= 500:
            print(
                f"LiteLLM {endpoint} failed with HTTP {response.status_code}; "
                "falling back to /models",
                flush=True,
            )
            continue

        response.raise_for_status()

    return set()


def synchronize() -> None:
    response = requests.get(
        f"{LM_STUDIO_BASE}/models",
        headers=lm_headers,
        timeout=20,
    )
    response.raise_for_status()

    upstream_models = {
        item["id"]
        for item in response.json().get("data", [])
        if item.get("id")
    }

    existing_models = get_existing_litellm_models()

    for upstream_id in sorted(upstream_models):
        public_name = f"lmstudio/{upstream_id}"

        if public_name in existing_models:
            continue

        payload = {
            "model_name": public_name,
            "litellm_params": {
                "model": f"openai/{upstream_id}",
                "api_base": LM_STUDIO_BASE,
                "api_key": LM_STUDIO_API_KEY,
            },
            "model_info": {
                "source": "lm-studio",
                "upstream_model_id": upstream_id,
            },
        }

        response = requests.post(
            f"{LITELLM_BASE}/model/new",
            headers=litellm_headers,
            json=payload,
            timeout=20,
        )
        response.raise_for_status()

        print(f"Added {public_name}", flush=True)


while True:
    try:
        synchronize()
    except Exception as exc:
        print(f"Synchronization failed: {exc}", flush=True)

    time.sleep(SYNC_INTERVAL)
