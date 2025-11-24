
# QBO Attachment Migration Demo

## TL;DR

Small, self-contained data engineering project that demonstrates how to design an idempotent batch pipeline for migrating legacy file attachments into QuickBooks Online style entities.

The project focuses on:

- Identifier normalization and mapping verification before any "API" work.
- Idempotent upload logic built around a persistent run log.
- Structured CSV logs for observability, data quality checks, and auditability.
- A fake remote API with controlled failure modes to exercise error handling and retries.

Originally inspired by a production migration that handled hundreds of thousands of legacy transactions and more than one hundred thousand attachments, this repository recreates the core ideas on a synthetic, laptop-sized dataset.

## Project highlights (for reviewers)

- Designed a configuration-driven, idempotent batch pipeline to migrate legacy attachments into QuickBooks Online style entities.
- Implemented explicit identifier normalization and mapping verification to catch data issues before simulated API calls.
- Simulated a remote attachment API with tunable failure rates in order to test error handling, logging, and reruns.
- Emitted structured CSV logs that make partial failures safe to rerun and easy to reason about.

## Tech stack

- Language: Python 3.10+
- Libraries: standard library only (pathlib, csv, dataclasses, typing, random, time).
- Storage: local filesystem for both source files and logs (in a real deployment these directories would map cleanly to S3 or GCS buckets).
- Configuration: environment-variable driven, centralized in `src/config.py`.
- Testing: small `tests/` package intended to cover normalization and idempotency logic.

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

In ETL terms this can be read as:

- Extract: scan a legacy attachment tree into a flat inventory.
- Transform: normalize identifiers, join against a mapping export, and filter out invalid rows.
- Load: attach files to mapped entities via a simulated remote API, with idempotent behavior and detailed logging.

## Repository layout

The repository is structured to mirror the stages a data engineer would implement in a real migration.

`src/config.py` centralizes configuration. It resolves `DATA_DIR`, `FILES_DIR`, and `LOG_DIR` from environment variables (with defaults relative to the repository root), ensures that the log directory exists, and defines shared paths such as `attachments_inventory.csv`, `mapping_export.csv`, and the various log files. It also exposes the `normalize_legacy_id` function, which implements the canonical identifier normalization rule for the pipeline.

`src/auth_qbo_demo.py` represents the authentication layer. In a production system this module would encapsulate the OAuth 2.0 flow and return an authorized HTTP session and realm identifier. In this demonstration it returns a small `FakeQboSession` object and a dummy realm id so that the structure of the code matches a real QuickBooks integration without any external dependencies.

`src/fake_qbo_api.py` simulates the QuickBooks Online attachment API. Its `attach_file` function accepts an entity type, entity identifier, and file path, measures a simple elapsed time, checks for missing files, and randomly injects failures at a configurable rate. It returns a small response object containing a synthetic HTTP status code, an Intuit-style id on success, an error message on failure, and a duration in milliseconds. This allows the uploader to exercise realistic error handling, logging, and retry behavior without leaving the local machine.

`src/build_attachment_inventory.py` walks a synthetic legacy folder tree under `FILES_DIR`, extracts a normalized legacy transaction identifier from folder names, and writes a flat `attachments_inventory.csv` file with one row per discovered attachment. This models the “metadata discovery” step that converts an ad hoc directory structure such as `Attach/<Client>/Txn/<TxnId>/file.ext` into something that can be joined and validated.

`src/download_mapping_demo.py` stands in for the step that produces a `QbdtEntityIdMapping` export. In a full system this export would come from an upstream migration or QuickBooks API. Here it simply writes `mapping_export.csv` under `DATA_DIR` using synthetic data that matches the normalization rules and identifiers in the attachment inventory.

`src/mapping_verifier.py` loads `mapping_export.csv` and `attachments_inventory.csv`, joins attachments to mappings using `legacy_txnid_norm` and entity type, and writes two verification files under `LOG_DIR`: `mapping_verification_log.csv` for in-scope rows with explicit status flags, and `mapping_verification_skips.csv` for rows that were intentionally excluded by configuration. This stage acts as a data quality and completeness check before any upload attempts.

`src/qbo_attach_demo.py` is the main batch uploader. It reads the verified attachments, builds an in-memory idempotency index from the prior `qbo_attach_runlog.csv`, calls `fake_qbo_api.attach_file` for new work, and writes detailed logs of every attempt into `qbo_attach_runlog.csv`, `qbo_attach_errors.csv`, and `qbo_attach_dups.csv`. It treats the run log as the source of truth when deciding whether a particular file has already been attached to a particular entity.

A small `tests/` package is intended to cover the core behaviors that matter in production: identifier normalization, mapping joins, and idempotency behavior given different combinations of prior run log entries.

## Normalized identifier and idempotent design

The original system used transaction identifiers with a fixed prefix that did not appear in the mapping export. Rather than relying on ad hoc string slicing, this project treats normalization as a first-class concern via the `normalize_legacy_id` helper in `config.py`.

All components that deal with identifiers work against the normalized form:

- `build_attachment_inventory.py` parses raw folder names and immediately normalizes them into `legacy_txnid_norm`.
- `download_mapping_demo.py` emits mapping rows keyed by `legacy_txnid_norm`.
- `mapping_verifier.py` performs joins exclusively on the normalized key.
- `qbo_attach_demo.py` uses the same key when building its joins and logs.

This eliminates an entire class of subtle bugs around mismatched prefixes and casing.

Idempotency is implemented at the level of individual attachment-to-entity pairs. The uploader treats a pair `(qbo_entity_id, file_name)` as the natural idempotent key. At startup it reads `qbo_attach_runlog.csv` (if present), filters for prior successes, and builds an index in memory. When the script encounters the same pair again, it records a new row with an outcome such as `skipped_already_uploaded` without calling the fake API a second time.

This pattern makes the pipeline safe to rerun in the presence of network glitches, process restarts, or other partial failures, and it aligns with how idempotent batch jobs are designed in larger data platforms.

## Running the demo

Running the demonstration requires Python 3.10 or later.

1. Create and activate a virtual environment, then install the dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Set the environment variables used by `config.py`, or rely on the defaults. The typical configuration is:

- `DATA_DIR` pointing to the `data` folder in the repository root.
- `LOG_DIR` pointing to a writable `logs` folder.
- `FILES_DIR` pointing to a small synthetic legacy attachment tree.

3. Generate the synthetic mapping and attachment inventory:

```bash
python -m src.download_mapping_demo
python -m src.build_attachment_inventory
```

4. Run the mapping verifier:

```bash
python -m src.mapping_verifier
```

5. Run the uploader:

```bash
python -m src.qbo_attach_demo
```

After these steps, the most interesting files to inspect for portfolio purposes are:

- `logs/qbo_attach_runlog.csv` to see how successful uploads, skips, and failures are represented.
- `logs/qbo_attach_errors.csv` to see how failures are captured with status codes and messages.
- `logs/qbo_attach_dups.csv` to see how idempotent behavior is summarized.
- `logs/mapping_verification_log.csv` to see how mapping coverage and data quality checks are expressed.

These logs can be opened in any spreadsheet tool or loaded into a database for further analysis.

## Real-world origin and scale

The structure of this repository is based on a production QuickBooks Desktop to QuickBooks Online migration in which attachment handling was built as a dedicated pipeline. That project worked against hundreds of thousands of legacy transactions and on the order of one hundred seventy thousand attachments extracted from a legacy Attach tree. The same concerns appear there as in this demo:

- Mapping coverage and identifier normalization.
- Safe, repeatable batch runs across large attachment inventories.
- Logging that can support auditors and downstream teams, not just developers.

The synthetic dataset in this repository is deliberately small so that it can be run end-to-end on a laptop in seconds, but the code and design choices are intended to scale by swapping the local filesystem for S3 or GCS and wiring the scripts into an orchestrator such as Airflow, Prefect, or Dagster.

## Relevance for data engineering roles

This project is aimed at showing how a data engineer approaches a concrete migration problem rather than how a candidate solves isolated coding puzzles.

Key aspects:

- Config-driven design that separates code from environment, using paths and options derived from environment variables.
- Clear separation of concerns between discovery, mapping verification, authentication, API interaction, and logging.
- Idempotent batch processing with a simple, explicit key and a durable run log.
- Structured logging and CSV outputs that support observability, debugging, and audit.
- A simulated external dependency that makes error handling and retries testable without relying on external services.

The same patterns apply when moving from this synthetic setup to cloud storage, containerized workloads, and production schedulers.
