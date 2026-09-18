"""
Vigil — Phase 9: Elastic Agent Builder Tools Definitions & Integrations
(backend/agents/agent_builder_tools.py)

Contains the Agent Builder tool declarations matching Kibana Agent Builder's schema
and provides direct integration references to backend/agents/chat_tools.py.

Kibana / Elastic Agent Builder Tools in this configuration:
- search_calls: Index-search tool over 'calls' index with hybrid text/semantic + metadata filters.
- search_regulations: Index-search tool over 'regulations' index with hybrid BM25 + semantic search.
- get_rm_history: Aggregation tool over 'compliance_findings' index.
- get_customer_profile: Application lookup tool against MySQL customer profile.
- get_product_details: Application lookup tool against MySQL product table.
- get_transactions: Application lookup tool against MySQL transaction table.
"""

from typing import Dict, Any, List
from backend.agents.chat_tools import (
    search_calls,
    search_regulations,
    get_rm_history,
    get_customer_profile,
    get_product_details,
    get_transactions,
    BEDROCK_TOOL_CONFIG,
    TOOL_REGISTRY,
    ALL_TOOLS,
)

# Agent Builder Tool definitions for Kibana / Elastic Cloud deployment
AGENT_BUILDER_TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "search_calls",
        "type": "index_search",
        "description": "Searches recorded RM-customer calls in Elasticsearch by semantic transcript query, RM ID, Customer ID, severity, or date range.",
        "configuration": {
            "index": "calls",
            "search_fields": ["transcript_english_text", "transcript_semantic"],
            "filter_fields": ["rm_id", "customer_id", "date_time", "has_violation"],
            "max_results": 25,
            "default_limit": 10,
        },
    },
    {
        "name": "search_regulations",
        "type": "index_search",
        "description": "Searches regulatory clauses from SEBI Master Circulars and AMFI Code of Ethics using hybrid BM25 and semantic search.",
        "configuration": {
            "index": "regulations",
            "search_fields": ["chunk_text", "chunk_text_semantic"],
            "max_results": 25,
            "default_limit": 10,
        },
    },
    {
        "name": "get_rm_history",
        "type": "esql_or_agg",
        "description": "Aggregates and retrieves prior confirmed compliance violations from compliance_findings index for a given RM ID or across all RMs.",
        "configuration": {
            "index": "compliance_findings",
            "group_by": ["category", "severity"],
            "date_filter_supported": True,
        },
    },
    {
        "name": "get_customer_profile",
        "type": "database_lookup",
        "description": "Retrieves investor risk profile, investment experience, and KYC status from MySQL database.",
        "configuration": {
            "table": "customer",
            "primary_key": "customer_id",
            "read_only": True,
        },
    },
    {
        "name": "get_product_details",
        "type": "database_lookup",
        "description": "Retrieves product risk classification, suitable investor profiles, and disclosure mandates from MySQL database.",
        "configuration": {
            "table": "product",
            "primary_key": "product_id",
            "read_only": True,
        },
    },
    {
        "name": "get_transactions",
        "type": "database_lookup",
        "description": "Retrieves recent transactions for customer or RM from MySQL database with deterministic ordering.",
        "configuration": {
            "table": "transaction",
            "filter_fields": ["customer_id", "rm_id"],
            "max_results": 25,
            "read_only": True,
        },
    },
]

__all__ = [
    "search_calls",
    "search_regulations",
    "get_rm_history",
    "get_customer_profile",
    "get_product_details",
    "get_transactions",
    "BEDROCK_TOOL_CONFIG",
    "TOOL_REGISTRY",
    "ALL_TOOLS",
    "AGENT_BUILDER_TOOL_DEFINITIONS",
]
