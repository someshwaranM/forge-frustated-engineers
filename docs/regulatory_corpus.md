# Vigil — Regulatory Corpus Specification

## 1. Purpose & Legal Grounding

In financial compliance surveillance, an AI finding without a precise statutory citation cannot withstand an internal audit or defense before regulators. Vigil grounds every compliance detection in an indexed corpus of statutory regulations and ethical codes issued by the **Securities and Exchange Board of India (SEBI)** and the **Association of Mutual Funds in India (AMFI)**.

When Vigil's Investigator Agent confirms a violation, it does not invent an abstract justification; it binds the finding to a specific, immutable clause chunk stored in Elasticsearch. This grounding forms the statutory pillar of the 9-point **Evidence Chain**.

---

## 2. The 5 Foundational Source Documents

The regulatory knowledge base is compiled from 5 authoritative PDFs stored under `RegulatoryDocs/`:

```
RegulatoryDocs/
├── AMFI/
│   ├── AMFI_Codeof_Ethics_2026.pdf
│   └── Revised_Codeof_Conductfor_Mutual_Fund_Distributors_April2022.pdf
└── SEBI/
    ├── master-circular-for-mutual-funds.pdf
    ├── securities-and-exchange-board-of-india-mutual-funds-regulations-1996-last-amended-on-february-07-2023.pdf
    └── securities-and-exchange-board-of-india-mutual-funds-regulations-2026-last-amended-on-july-7-2026.pdf
```

### Detailed Document Manifest

| Document Name | Issuing Authority | Type & Status | Key Compliance Scope | Direct PDF Source |
|---|---|---|---|---|
| **SEBI (Mutual Funds) Regulations, 2026** | SEBI | Principal Regulation (`current`) | Foundational statutory authority governing mutual funds, scheme structures, AMC obligations, and advertising codes. Current primary citation source. | [SEBI 2026 Regulations](https://www.sebi.gov.in/legal/regulations/jul-2026/securities-and-exchange-board-of-india-mutual-funds-regulations-2026-last-amended-on-july-7-2026-_102780.html) |
| **SEBI (Mutual Funds) Regulations, 1996** | SEBI | Principal Regulation (`legacy`) | Historical regulation amended through Feb 07, 2023. Retained in Elasticsearch with `status: "legacy"` for historical reference and backward audit compatibility. | [SEBI 1996 Regulations](https://www.sebi.gov.in/legal/regulations/feb-2023/securities-and-exchange-board-of-india-mutual-funds-regulations-1996-last-amended-on-february-07-2023-_69213.html) |
| **Master Circular for Mutual Funds (2026)** | SEBI | Master Circular (`current`) | Consolidated operational circular covering practical compliance: scheme categorization, risk-o-meter disclosures, performance advertising norms, and investor disclosures. | [SEBI Master Circular](https://www.sebi.gov.in/legal/master-circulars/mar-2026/master-circular-for-mutual-funds_100491.html) |
| **AMFI Code of Conduct for Mutual Fund Distributors (2022)** | AMFI | Code of Conduct (`current`) | Direct professional obligations binding AMFI-registered distributors (ARNs) and RMs. Contains the most direct, quotable prohibitions against guaranteed returns and unsuitable selling. | [AMFI Distributor Code](https://www.amfiindia.com/uploads/Revised_Codeof_Conductfor_Mutual_Fund_Distributors_April2022_57d91fe1c4.pdf) |
| **AMFI Code of Ethics (2026)** | AMFI | Industry Code (`current`) | AMC member ethics code mandating fairness, risk disclosure, suitability assessments, and non-misleading communications. | [AMFI Code of Ethics](https://www.amfiindia.com/uploads/AMFI_Codeof_Ethics_2026_c9e1d12ba1.pdf) |

---

## 3. Mapping Statutory Clauses to Detection Categories

| Vigil Detection Category | Primary Source Clauses | Regulatory Rationale |
|---|---|---|
| **Guaranteed-Return / Capital Protection Claims** | • **AMFI Distributor Code §II.4.g**: MFDs shall not provide indicative yields or returns and must abstain from assuring returns.<br>• **AMFI Distributor Code §II.4.h**: Explicit notice that MF schemes are not guaranteed return products.<br>• **SEBI Master Circular §Advertising Code**: Prohibition on misleading yield claims. | Mutual fund investments carry principal risk. Assuring a fixed return (e.g. "15% guaranteed") violates basic fiduciary selling norms. |
| **Suitability Mismatch** | • **AMFI Distributor Code §II.2.d**: MFDs must assess investor financial status, investment experience, and objectives before recommending a scheme.<br>• **AMFI Distributor Code §II.1.e.v**: Explicit prohibition on selling unsuitable products.<br>• **AMFI Code of Ethics §6.3**: Product recommendation alignment. | Recommending high-volatility sectoral or small-cap equity funds to a Conservative, low-experience investor breaches suitability mandates. |
| **Missing / Inadequate Risk Disclosures** | • **AMFI Distributor Code §II.4.b**: MFDs must highlight risk factors and avoid concealing associated risks.<br>• **SEBI Master Circular §Risk-o-meter Norms**: Mandatory disclosure of fund risk classification during sales pitch. | RMs must verbally state statutory disclaimers during calls to prevent deceptive omissions. |
| **Exaggerated / Misleading Performance** | • **AMFI Code of Ethics §6.4**: Communications must not create unrealistic expectations or misrepresent products by omission.<br>• **AMFI Distributor Code §II.1.c**: Financial incentives must not drive scheme recommendations. | Projecting past high returns as continuous future yields deceives retail investors. |

---

## 4. Text Extraction & Header/Footer Stripping Pipeline

PDF text extraction is handled by `backend/indexing/extract.py` using **PyMuPDF (`fitz`)**.

### Header/Footer Removal Mechanics
Regulatory PDFs contain repetitive running headers, department names, and page footers that degrade embedding quality if ingested into vector indices. Vigil implements an automated statistical filter:
1. **Physical Page Iteration:** PyMuPDF iterates block-by-block through physical pages (`page.number + 1`), preserving true document order.
2. **Line Normalization:** Lines are stripped of whitespace and page digits using regex patterns (e.g., `Page \d+ of \d+`).
3. **Statistical Recurrence Tracking:** A line frequency distribution is computed across the document. Any line that recurs across non-adjacent pages with a frequency exceeding `RECURRENCE_THRESHOLD = 0.60` (60% of pages) is classified as running chrome.
4. **Stripping & Boundary Offsets:** Identified running headers/footers are excised, while physical page start character offsets are preserved in `PageBoundary` objects for downstream citation tracking.
5. **Quality Verification Gate:** Cleaned pages are scanned for extraction corruption. Pages with fewer than 5 characters or an alphabetic ratio below 15% are flagged for manual verification.

---

## 5. Chunking Architecture & Semantic Strategy

Document chunking is handled by `backend/indexing/chunk.py`. Regulatory documents are broken down hierarchically into discrete clauses rather than arbitrary token blocks.

### The `chunk_text` vs. `chunk_text_semantic` Distinction

Every indexed regulatory chunk produces two deliberately different textual representations:

```
+---------------------------------------------------------------------------------------------+
|                                    RAW REGULATORY CLAUSE                                    |
| "MFDs shall not provide any indicative portfolio or indicative yield or indicative return   |
|  for any particular scheme or transaction and shall abstain from indicating or assuring     |
|  returns for any particular scheme or transaction."                                         |
+---------------------------------------------------------------------------------------------+
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
+------------------------------------+   +----------------------------------------------------+
|            chunk_text              |   |               chunk_text_semantic                  |
+------------------------------------+   +----------------------------------------------------+
| Heading: Clause 4.g - Client       |   | AMFI Code of Conduct for Mutual Fund Distributors  |
| related obligations                |   | Section: II. Obligations of the MFDs               |
|                                    |   | Clause: II.4.g                                     |
| Text: MFDs shall not provide any   |   | Heading: Client related obligations                |
| indicative portfolio or indicative |   |                                                    |
| yield or indicative return...      |   | Text: MFDs shall not provide any indicative        |
|                                    |   | portfolio or indicative yield or return...         |
| [Optimized for BM25 exact keyword  |   | Broader Context: Obligations regarding fiduciary  |
|  matching and verbatim evidence]   |   | duty, fair dealing, and performance disclosures.   |
|                                    |   | [Optimized for dense vector embeddings via ELSER]  |
+------------------------------------+   +----------------------------------------------------+
```

### Why They Are Deliberately Different
- **`chunk_text` (BM25 Precision):** Kept clean, tight, and verbatim. It includes only the heading and clause text. Adding extraneous text to this field would dilute term frequencies (TF/IDF) and introduce keyword noise during exact search queries.
- **`chunk_text_semantic` (Dense Embedding Quality):** In legal texts, individual clauses are frequently terse or reference abstract pronouns (e.g. "They shall ensure compliance with the above"). Without hierarchical context, vector embedding models fail to capture the regulatory authority, issuing body, or section theme. Prepending document titles and chapter breadcrumbs injects essential semantic anchors into the embedding space, significantly improving kNN retrieval accuracy.

---

## 6. Pre-Indexing Validation Gate (`backend/indexing/validate.py`)

Before any chunk can be indexed into the Elasticsearch `regulations` index, it must pass an automated, non-negotiable **7-Point Validation Gate**. If a single chunk in any file fails any check, the indexing script halts immediately, reporting the file, chunk ID, and exact validation failure.

### The 7 Validation Checks
1. **Non-Empty Clause Text:** `clause_text` must contain non-empty string content whenever a `clause` identifier is specified.
2. **Mandatory Clause in Code of Conduct:** In the AMFI Code of Conduct (`Revised_Codeof_Conductfor_Mutual_Fund_Distributors_April2022`), every chunk must possess a non-empty `clause` tag.
3. **Physical Page Validity:** `page_number` must be an integer >= 1.
4. **Source URL Grounding:** `source_url` must be present and contain a valid URL string pointing to the official regulatory release.
5. **Global Chunk ID Uniqueness:** Every `chunk_id` must be globally unique across all 5 indexed documents. Collisions cause immediate pipeline termination.
6. **Mandatory Metadata Presence:** Metadata fields (`document_id`, `document_name`, `regulator`, `document_type`, `status`, `source_file_hash`, `indexed_at`) must not be null.
7. **Anti-Garbage Quality Check:** `chunk_text` and `chunk_text_semantic` are verified against minimum character length (>= 5) and printable alphabetic thresholds to guarantee that extraction artifacts are never indexed.

---
*Vigil Regulatory Corpus Documentation — SEBI & AMFI Grounding Architecture*
