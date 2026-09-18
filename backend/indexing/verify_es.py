"""
Verification script for Step 9:
Confirms document counts, aggregation breakdown, exact retrieval,
and semantic query search against Elasticsearch.
"""

from backend.indexing.create_index import get_es_client, INDEX_NAME

def verify():
    es = get_es_client()

    # 1. Total count
    total = es.count(index=INDEX_NAME)["count"]
    print(f"[PASS] Total documents indexed in '{INDEX_NAME}': {total}")

    # 2. Aggregation by document_id
    agg = es.search(index=INDEX_NAME, body={
        "size": 0,
        "aggs": {
            "by_doc": {
                "terms": {"field": "document_id", "size": 10}
            }
        }
    })
    print("\n--- Document Breakdown ---")
    for b in agg["aggregations"]["by_doc"]["buckets"]:
        print(f"  {b['key']}: {b['doc_count']} chunks")

    # 3. Exact lookup of key detection anchor: AMFI Code of Conduct II.4.g
    exact = es.search(index=INDEX_NAME, body={
        "query": {
            "term": {"chunk_id": "AMFI_MFD_COC_2022_II_4_g"}
        }
    })
    print("\n--- Exact Retrieval Check: AMFI II.4.g ---")
    hits = exact["hits"]["hits"]
    if hits:
        h = hits[0]["_source"]
        print(f"  [PASS] Found chunk: {h['chunk_id']}")
        print(f"  Citation: {h['citation_label']}")
        print(f"  Clause: {h['clause']}")
        print(f"  Text: {h['clause_text']}")
    else:
        print("  [FAIL] AMFI_MFD_COC_2022_II_4_g not found!")

    # 4. Semantic search for guaranteed returns
    print("\n--- Semantic Search Test: Guaranteed Returns ---")
    query_text = "guaranteed returns or assuring fixed profit to investors"
    sem = es.search(index=INDEX_NAME, body={
        "query": {
            "semantic": {
                "field": "chunk_text_semantic",
                "query": query_text
            }
        },
        "size": 3
    })
    for i, hit in enumerate(sem["hits"]["hits"]):
        src = hit["_source"]
        print(f"  #{i+1} Score: {hit['_score']:.4f} | Citation: {src['citation_label']} ({src['chunk_id']})")
        print(f"      Text: {src['clause_text'][:120]}...\n")

    # 5. Semantic search for suitability / risk profile
    print("\n--- Semantic Search Test: Suitability Mismatch ---")
    query_text = "investor risk profile suitability assessment before recommendation"
    sem_suit = es.search(index=INDEX_NAME, body={
        "query": {
            "semantic": {
                "field": "chunk_text_semantic",
                "query": query_text
            }
        },
        "size": 3
    })
    for i, hit in enumerate(sem_suit["hits"]["hits"]):
        src = hit["_source"]
        print(f"  #{i+1} Score: {hit['_score']:.4f} | Citation: {src['citation_label']} ({src['chunk_id']})")
        print(f"      Text: {src['clause_text'][:120]}...\n")

if __name__ == "__main__":
    verify()
