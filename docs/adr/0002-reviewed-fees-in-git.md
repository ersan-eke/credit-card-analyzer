# Reviewed fees live in a committed file; a pull request is the review

The hosted app and the weekly refresh job (a GitHub Action) have no shared database, so the reviewed fees are a committed
JSON file shipped with the app. When a source changes, the job re-extracts and opens a pull request showing each changed fee
with its quote; merging is the approval and deploys it. If fetching or extraction fails, the old fees and their "Stand" date
stay and the job opens an issue. This replaces the SQLite review queue and the ingest webhook; SQLite remains only for the
local audit log.
