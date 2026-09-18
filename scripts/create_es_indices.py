"""
Vigil — Create Elasticsearch Indices.

Applies the authoritative Elasticsearch mappings from data/schemas/es_mappings/:
- regulations (regulations_mapping.json)
- calls (calls_mapping.json)
- compliance_findings (compliance_findings_mapping.json)
"""

import json
import logging
import sys
from pathlib import Path
from elasticsearch import Elasticsearch, NotFoundError

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.indexing.create_index import get_es_client

logger = logging.getLogger(__name__)

MAPPINGS_DIR = PROJECT_ROOT / "data" / "schemas" / "es_mappings"

INDEX_CONFIGS = [
    ("regulations", MAPPINGS_DIR / "regulations_mapping.json"),
    ("calls", MAPPINGS_DIR / "calls_mapping.json"),
    ("compliance_findings", MAPPINGS_DIR / "compliance_findings_mapping.json"),
]


def create_all_indices(es: Elasticsearch = None, *, force: bool = False) -> None:
    if es is None:
        es = get_es_client()

    print("=" * 60)
    print("Applying Elasticsearch Mappings from data/schemas/es_mappings/")
    print("=" * 60)

    for index_name, mapping_file in INDEX_CONFIGS:
        if not mapping_file.exists():
            raise FileNotFoundError(f"Mapping file not found: {mapping_file}")

        with open(mapping_file, "r", encoding="utf-8") as f:
            mapping_body = json.load(f)

        if es.indices.exists(index=index_name):
            if force:
                logger.info(f"Deleting existing index '{index_name}'...")
                es.indices.delete(index=index_name)
                print(f"  [DELETED] Existing index '{index_name}'")
            else:
                print(f"  [SKIPPED] Index '{index_name}' already exists. Use --force to recreate.")
                continue

        logger.info(f"Creating index '{index_name}'...")
        es.indices.create(index=index_name, body=mapping_body)
        print(f"  [CREATED] Index '{index_name}' successfully created from {mapping_file.name}")

    print("\nAll indices processed successfully.\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    force_recreate = "--force" in sys.argv or "-f" in sys.argv
    create_all_indices(force=force_recreate)
