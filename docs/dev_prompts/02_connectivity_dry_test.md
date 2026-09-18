# Vigil — Phase 2 Dev Prompt: Connectivity Test Scripts
`docs/dev_prompts/02_connectivity_dry_test.md`

---

## What this phase is

Five small, independent, run-it-yourself test scripts — one per external dependency. Each one connects, does the smallest possible real operation, and prints PASS or FAIL straight to the terminal. No shared runner, no report file, no aggregation — just `python scripts/tests/test_mysql.py` and you immediately see whether that one thing works.

---

## The prompt (paste this verbatim to Codex / Claude Code / Antigravity)

````
You are running Phase 2 of the Vigil build. Create 5 standalone, independently
runnable Python test scripts under scripts/tests/ — one per external
dependency. Do NOT build a shared config loader, a shared runner, or any
aggregated report. Do NOT implement any pipeline, detection, or agent logic.
Each script is self-contained: it reads whatever env vars it needs directly
(via os.environ / python-dotenv), performs the smallest real operation that
proves connectivity, and prints the result to the terminal only. Nothing is
written to a file or returned as an object for another script to consume.

Create exactly these 5 files:

scripts/tests/
├── test_mysql.py
├── test_elasticsearch.py
├── test_bedrock.py
├── test_gemini.py
└── test_sarvam.py

Each script must follow this exact behavior:

1. test_mysql.py
   - Connect to MySQL using MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
     MYSQL_PASSWORD, MYSQL_DATABASE from backend/.env.
   - Open a connection and run SELECT DATABASE(); to confirm the database is reachable.
   - Print the active database name and then the final PASS/FAIL line.
   - Print a final line: "[PASS] MySQL connection OK" or
     "[FAIL] MySQL connection failed: <reason>".
   - Do not assume any application tables exist yet; this phase checks connectivity only.

2. test_elasticsearch.py
   - Connect to Elasticsearch using ELASTICSEARCH_URL and
     ELASTICSEARCH_API_KEY from backend/.env.
   - Use the root endpoint (not /_cluster/health) when the service is Elastic Cloud serverless, because that endpoint may return HTTP 410 even though the endpoint and key are valid.
   - Print the returned service/build metadata and then the final PASS/FAIL line.
   - Print "[PASS] Elasticsearch connection OK" or
     "[FAIL] Elasticsearch connection failed: <reason>".

3. test_bedrock.py
   - Call AWS Bedrock (using AWS_REGION and AWS_BEDROCK_MODEL_ID from backend/.env,
     plus the AWS credential env vars) with one trivial prompt, e.g.
     "Reply with the single word: OK".
   - Print the raw response text.
   - Print "[PASS] Bedrock connection OK" or
     "[FAIL] Bedrock connection failed: <reason>" — if the failure is an auth
     or access error, say so explicitly in <reason> rather than printing a
     raw stack trace.
   - Check for placeholder values like <REPLACE_ME> before making the call so the script fails cleanly when config is incomplete.

4. test_gemini.py
   - Call the Gemini API (using GEMINI_API_KEY and GEMINI_MODEL_ID from backend/.env)
     with the same trivial prompt used in test_bedrock.py.
   - Accept either a plain model string like gemini-2.5-flash or a resource-style value such as models/gemini-2.5-flash.
   - Print the raw response text.
   - Print "[PASS] Gemini connection OK" or
     "[FAIL] Gemini connection failed: <reason>".

5. test_sarvam.py
   - Call the Sarvam STT API (using SARVAM_API_KEY from backend/.env) against one
     short local test audio file at scripts/tests/sample_audio/test_clip.wav
     (create this folder; note in a code comment that a real short clip must
     be dropped in here manually before running this test — do not use any
     of the real prepared RM call recordings for this).
   - Print the returned transcript text.
   - Print "[PASS] Sarvam connection OK" or
     "[FAIL] Sarvam connection failed: <reason>".

RULES FOR ALL 5 SCRIPTS:
- Each script must be runnable on its own: `python scripts/tests/test_x.py`
  with no arguments and no dependency on the other 4 scripts.
- Wrap the actual API/DB call in a single try/except so a failure prints a
  clean one-line [FAIL] message instead of a raw traceback.
- Print only to stdout — no logging to file, no JSON output, no return value
  consumed elsewhere.
- Keep each script under ~40 lines. This phase proves connectivity, nothing
  more — no retries, no timeouts tuning, no config abstraction.
- All 5 scripts read credentials directly from environment variables already
  defined in .env.example (root) — do not invent new env var names beyond
  MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE,
  ELASTICSEARCH_URL, ELASTICSEARCH_API_KEY, AWS_REGION, AWS_BEDROCK_MODEL_ID,
  GEMINI_API_KEY, GEMINI_MODEL_ID, SARVAM_API_KEY.

Stop once all 5 scripts exist and each one, run individually, prints a clear
PASS or FAIL line. Report back the actual terminal output of each script when
you run them — not hypothetical output.
````

---

## What "good" looks like

Running each script individually should give you one clean, unambiguous PASS/FAIL result, for example:

```
$ python scripts/tests/test_mysql.py
Connected to MySQL database: vigil
[PASS] MySQL connection OK

$ python scripts/tests/test_bedrock.py
OK
[PASS] Bedrock connection OK
```

For Elasticsearch and Gemini, the script may print service metadata or HTTP details when the environment is not yet valid, but the expected final line remains one of:

```
[PASS] Elasticsearch connection OK
[FAIL] Elasticsearch connection failed: <reason>

[PASS] Gemini connection OK
[FAIL] Gemini connection failed: <reason>
```

No shared machinery to debug if one fails — you run the one script for the one thing that's broken, fix it, move on.
