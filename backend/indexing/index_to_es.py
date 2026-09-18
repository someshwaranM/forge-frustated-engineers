"""
Step 7 — Wipe and bulk-index into Elasticsearch.

Only runs if Step 6 (validation) passed with zero failures.
Every run starts from a clean, empty index (delete + recreate).
"""

import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import bulk

from backend.indexing.create_index import MAPPING, INDEX_NAME, get_es_client

logger = logging.getLogger(__name__)

CHUNKS_DIR = Path(__file__).resolve().parent / "chunks"


def _load_all_chunks() -> list:
    """Load all chunk documents from chunks/*.json files."""
    all_chunks = []
    for json_path in sorted(CHUNKS_DIR.glob("*.json")):
        with open(json_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        all_chunks.extend(chunks)
        logger.info(f"  Loaded {len(chunks)} chunks from {json_path.name}")
    return all_chunks


def wipe_and_index(es: Elasticsearch = None) -> int:
    """
    Wipe the 'regulations' index completely, recreate it with the mapping,
    then bulk-index every chunk document from chunks/*.json.

    Returns the total number of documents indexed.
    """
    if es is None:
        es = get_es_client()

    # 1. Delete existing index
    try:
        es.indices.delete(index=INDEX_NAME)
        print(f"  Deleted existing index '{INDEX_NAME}'.")
    except NotFoundError:
        print(f"  Index '{INDEX_NAME}' did not exist — creating fresh.")

    # 2. Recreate with mapping
    es.indices.create(index=INDEX_NAME, body=MAPPING)
    print(f"  Created index '{INDEX_NAME}' with mapping.")

    # 3. Load all chunks
    all_chunks = _load_all_chunks()
    if not all_chunks:
        print("  [WARN]  No chunks found to index.")
        return 0

    print(f"  Bulk-indexing {len(all_chunks)} documents…")

    # 4. Bulk index
    def _gen_actions():
        for chunk in all_chunks:
            yield {
                "_index": INDEX_NAME,
                "_id": chunk["chunk_id"],
                "_source": chunk,
            }

    success, errors = bulk(es, _gen_actions(), raise_on_error=False,
                           chunk_size=50, request_timeout=180)
    if errors:
        logger.error(f"  Bulk indexing errors: {len(errors)}")
        for err in errors[:10]:
            logger.error(f"    {err}")
        raise RuntimeError(f"Bulk indexing failed with {len(errors)} errors")

    print(f"  [PASS] Successfully indexed {success} documents.")

    # 5. Refresh to make searchable
    es.indices.refresh(index=INDEX_NAME)

    return success


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("=" * 60)
    print("STEP 7 — Wipe & Bulk Index to Elasticsearch")
    print("=" * 60)
    count = wipe_and_index()
    print(f"\n  Total indexed: {count}\n")


if __name__ == "__main__":
    main()
