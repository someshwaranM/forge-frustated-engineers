import os
from pathlib import Path
from dotenv import load_dotenv
from urllib.request import Request, urlopen

load_dotenv(Path(__file__).resolve().parents[2] / "backend" / ".env")

try:
    elastic_url = os.environ.get("ELASTICSEARCH_URL", "")
    api_key = os.environ.get("ELASTICSEARCH_API_KEY", "")
    if not elastic_url or "<REPLACE_ME>" in elastic_url:
        raise ValueError("ELASTICSEARCH_URL is missing or still set to <REPLACE_ME>")
    if api_key and "<REPLACE_ME>" in api_key:
        raise ValueError("ELASTICSEARCH_API_KEY still contains a placeholder value")

    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"
    # Elastic Cloud Serverless does not expose /_cluster/* APIs and returns
    # HTTP 410 for them. The root endpoint is supported and proves that the
    # Elasticsearch endpoint and API key are valid.
    endpoint = elastic_url.rstrip("/") + "/"
    request = Request(endpoint, headers=headers)
    with urlopen(request) as response:
        info = response.read().decode("utf-8")
    import json
    details = json.loads(info)
    build_flavor = details.get("version", {}).get("build_flavor", "unknown")
    print(f"build flavor: {build_flavor}")
    print("[PASS] Elasticsearch connection OK")
except Exception as exc:
    print(f"[FAIL] Elasticsearch connection failed: {exc}")
    if "ELASTICSEARCH_URL" in os.environ:
        print(f"Endpoint used: {os.environ['ELASTICSEARCH_URL']}")
