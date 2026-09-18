"""
Vigil — Elasticsearch Client Provider (backend/elastic/client.py)
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

_es_client: Elasticsearch | None = None


def get_es_client() -> Elasticsearch:
    """Return a connected Elasticsearch client using credentials from backend/.env."""
    global _es_client
    if _es_client is not None:
        return _es_client

    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)
    url = os.getenv("ELASTICSEARCH_URL")
    api_key = os.getenv("ELASTICSEARCH_API_KEY")
    if not url or not api_key:
        raise RuntimeError("ELASTICSEARCH_URL / ELASTICSEARCH_API_KEY not set in .env")

    _es_client = Elasticsearch(url, api_key=api_key, request_timeout=120)
    return _es_client
