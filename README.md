
# QBO Attachment Migration Demo

## TL;DR

Data engineering project that builds an idempotent batch pipeline for migrating legacy file attachments into QuickBooks Online–style entities.

The pipeline:

- Walks a legacy attachment tree and flattens it into an inventory.
- Normalizes legacy transaction identifiers and joins them against a mapping export.
- Verifies mapping coverage before any "API" work.
- Runs an idempotent uploader against a fake QBO attachment API.
- Emits structured CSV logs for observability, audit, and safe reruns.

The design is based on a production migration that handled hundreds of thousands of legacy transactions and roughly one hundred seventy thousand attachments. This repo replays the core ideas on synthetic, laptop-sized data.

## Project highlights

- Batch pipeline that treats a messy legacy filesystem as source and a QBO-like API as sink.
- Explicit identifier normalization and mapping verification to catch data issues before upload.
- Idempotent uploader keyed on (entity_id, file_name) with a persistent run log.
- Fake remote API with controlled failures to exercise error handling and retries.
- Logs designed to be loaded into a warehouse for analysis and audit.

## Tech stack

- Language: Python 3.10+
- Libraries: standard library only (pathlib, csv, dataclasses, typing, random, time).
- Storage: local filesystem for files and logs (would map cleanly to S3 or GCS buckets).
- Configuration: environment variables read in src/config.py (DATA_DIR, FILES_DIR, LOG_DIR).
- Testing: pytest tests intended to cover normalization, joins, and idempotency behavior.

## Architecture snapshot

High-level flow:

```text
legacy filesystem
    ↓
attachment inventory (attachments_inventory.csv)
    ↓
mapping export (mapping_export.csv)
    ↓
mapping_verifier
    ↓
qbo_attach_demo
    ↙            ↘
fake_qbo_api   structured logs (run, errors, dups, verification)
```

In ETL terms:

- Extract: scan a legacy attachment tree into a flat inventory.
- Transform: normalize IDs, join to mapping export, label invalid or skipped rows.
- Load: attach files to mapped entities via a QBO-like API, with idempotent semantics.

## One-shot quick start

From a clean clone, on a machine with Python 3.10+:

```bash
python -m venv .venv && \
source .venv/bin/activate && \
pip install -r requirements.txt && \
python -m src.download_mapping_demo && \
python -m src.build_attachment_inventory && \
python -m src.mapping_verifier && \
python -m src.qbo_attach_demo
```

After that, the main outputs live under logs/:

- qbo_attach_runlog.csv – all attempts (success, failure, skipped).
- qbo_attach_errors.csv – filtered failures.
- qbo_attach_dups.csv – idempotent skips.
- mapping_verification_log.csv – mapping coverage and statuses.

### Tests

If pytest is installed, core behaviors can be exercised with:

```bash
pytest
```

Tests are aimed at normalize_legacy_id, mapping joins, and idempotency logic driven by prior run logs.

## Repository layout

src/config.py centralizes configuration. It resolves DATA_DIR, FILES_DIR, and LOG_DIR from environment variables (with defaults relative to the repo root), ensures the log directory exists, and defines shared paths for the inventory, mapping, and log CSVs. It also exposes normalize_legacy_id, the canonical normalization rule for legacy transaction identifiers.

src/auth_qbo_demo.py represents the authentication layer. A production version would encapsulate OAuth 2.0 and return an authorized HTTP session plus realm id. The demo version returns a small FakeQboSession object and a dummy realm id so the module boundary matches a real QBO integration without pulling in any external dependencies.

src/fake_qbo_api.py simulates the QuickBooks Online attachment API. The attach_file function accepts an entity type, entity id, and file path, measures elapsed time, checks for missing files, and injects failures at a configurable rate. It returns a response object with a synthetic HTTP status code, a fake Intuit-style id on success, an error message on failure, and a duration in milliseconds. The uploader treats it like a real HTTP client.

src/build_attachment_inventory.py walks a legacy-style folder tree under FILES_DIR, parses folder names to recover legacy transaction identifiers, normalizes them, and writes attachments_inventory.csv with one row per file. This models the common “flatten the Attach tree” step that turns a path such as Attach/Client/Txn/<RawId>/file.ext into structured metadata.

src/download_mapping_demo.py stands in for the QbdtEntityIdMapping export. In production this would be an upstream table or API. Here it writes mapping_export.csv under DATA_DIR using synthetic data that is consistent with the inventory and normalization logic.

src/mapping_verifier.py loads mapping_export.csv and attachments_inventory.csv, joins on legacy_txnid_norm and entity type, and writes:

- mapping_verification_log.csv – attachment rows and whether they have valid mappings.
- mapping_verification_skips.csv – rows intentionally excluded by configuration.

This stage is a data quality and completeness gate before any uploads.

src/qbo_attach_demo.py is the batch uploader. It:

- Reads the verified attachments.
- Loads qbo_attach_runlog.csv (if present) and builds an in-memory index of prior successes keyed by (qbo_entity_id, file_name).
- Calls fake_qbo_api.attach_file for work that has not succeeded before.
- Writes structured rows into qbo_attach_runlog.csv, qbo_attach_errors.csv, and qbo_attach_dups.csv.

A tests/ package (not shown here) is meant to exercise the behaviors that matter in production: normalization, mapping joins, and idempotent decisions given different prior logs.

## Normalized identifier and idempotent design

The original system used transaction identifiers with a fixed prefix in the legacy filesystem that did not appear in the mapping export. Instead of sprinkling s[2:] and .upper() across the codebase, normalization is pulled into a single helper: normalize_legacy_id in config.py.

Every component works with the normalized form:

- build_attachment_inventory.py parses raw folder names and writes legacy_txnid_norm.
- download_mapping_demo.py writes mapping rows keyed on legacy_txnid_norm.
- mapping_verifier.py joins inventory to mapping on the normalized id.
- qbo_attach_demo.py uses the same normalized key in its joins and logs.

That removes an entire class of subtle bugs around mismatched prefixes, casing, and formatting.

Idempotency is implemented at the level of attachment–entity pairs. The uploader treats (qbo_entity_id, file_name) as the idempotent key. At startup it:

- Reads qbo_attach_runlog.csv (if it exists).
- Filters for prior successes.
- Builds an in-memory index keyed on that pair.

When the same pair appears again, the job writes a new row marked as skipped rather than calling the API again. This makes reruns safe after failures or restarts without needing distributed locks or external dedup tables.

## Failure modes and operational behavior

What happens if the job dies halfway.  
If the process dies in the middle of a run, only the attachments that were successfully written to qbo_attach_runlog.csv with a success outcome are considered done. On restart, the uploader reloads that log and skips those pairs. Any attachments that were in flight when the process died simply show no successful row, so they are retried.

How to replay safely.  
Safe replay is to run the uploader again. Because the decision to skip or upload is driven entirely by the run log and the idempotent key, a replay does not double-attach files that already succeeded. Partial failures are handled by leaving failed rows in the log with an error outcome and re-attempting them on the next run.

How to detect partial uploads.  
Partial uploads are visible in three places:

- The count of distinct (qbo_entity_id, file_name) pairs with success versus the count of attachment rows in the verifier log.
- The size of qbo_attach_errors.csv (persistent failures).
- The presence of attachment rows with no corresponding success row in the run log.

In a real system, these would be materialized as tables in a warehouse and monitored with simple queries.

How to detect data drift.  
Data drift here mostly means “mapping export diverged from the filesystem reality.” The mapping_verifier.py stage is the drift detector:

- New attachments with no mapping land in mapping_verification_log.csv with a missing-mapping status.
- Counts per entity type between inventory and mapping can be compared over time.

Where alerts and metrics would live in production.  
If wired into a monitoring stack, obvious metrics and alerts would be:

- Gauge: number of successful attachments per run.
- Gauge: number of failed attachments per run.
- Gauge: number of missing mappings per run.
- Counter: total runtime and p95 duration per attachment call.

Thresholds on “failed > 0” or “missing mappings > 0” would alert before bad data sneaks into accounting.

## Data volume and performance thinking

This repository runs on synthetic data sized to complete in seconds on a laptop. The design generalizes because:

- Work is row-oriented: attachments are processed independently.
- Idempotent keys are compact (entity_id, file_name) pairs.
- The run log is append-only and can be partitioned (by date, by batch id, and so on).

For higher volumes:

- Inventory building would stream results rather than holding everything in memory.
- The uploader could batch work by entity type or by file size.
- Concurrency could be added at the attachment level (for example, a worker pool over the inventory) as long as all workers share a consistent run-log view or write to a central log sink (database table, Kafka topic, and so on).

The emphasis in this demo is on safety and clarity of behavior; the same structure can support higher throughput once distributed execution and external storage are introduced.

## Path to production

Blob storage (S3/GCS).  
In a cloud deployment, DATA_DIR and FILES_DIR would point to S3 or GCS buckets instead of a local filesystem. Inventory building would list objects in a prefix rather than walking directories. The rest of the pipeline logic stays the same.

Orchestrator.  
The scripts would become tasks in an Airflow, Prefect, or Dagster flow:

- Task A: build attachment inventory.
- Task B: fetch mapping export.
- Task C: run mapping verifier and emit verification tables.
- Task D: run uploader in batches.

Warehouse.  
The CSV logs would land in a warehouse (Snowflake, BigQuery, Redshift) as:

- attachment_inventory table.
- attachment_mapping_verification table.
- attachment_run_log table.
- attachment_errors table.

Monitoring.  
Metrics around counts and error rates would be exported to something like Prometheus, DataDog, or a similar monitoring stack, with alerting rules wired to on-call.

## Real-world origin and what is missing here

Real-world origin.  
This design comes from a QuickBooks Desktop to QuickBooks Online migration where attachments were handled as a dedicated pipeline. That system worked against hundreds of thousands of transactions and roughly one hundred seventy thousand attachments, with a similar legacy Attach tree, mapping export, ID normalization rule, idempotent uploader, and CSV logs feeding auditors and downstream teams.

Deliberately not included in this repo:

- No real OAuth or token refresh logic.
- No production API client for QuickBooks Online.
- No secrets management (environment variable strategy, Vault, and so on).
- No infrastructure-as-code, containerization, or deployment scripts.
- No orchestrator configuration (Airflow DAGs, Prefect flows, and so on).

These pieces are omitted on purpose so the focus stays on the data-engineering core: mapping, ID normalization, idempotent updates, and logging. In a production environment, those concerns would be layered on top of this skeleton.

## Relevance for data engineering roles

The project is structured as a minimal design and implementation for a realistic migration workflow:

- Explicit file- and row-level idempotency, backed by a durable run log.
- Clear separation between discovery, verification, and writing to the external system.
- Logs structured so that auditors and downstream analysts can work with them without reverse-engineering the code.
- A fake API that forces the uploader to handle latency, missing files, and failures rather than assuming ideal conditions.

It is intended as a self-contained example of how an attachment migration pipeline can be structured before being integrated into a larger data platform.
