# Hospital Checklist — local prototype

An English / Traditional Chinese prototype for reviewing pediatric rehabilitation checklist records. Existing homework files in the parent folder are unchanged.

## Run

```sh
cd /workspace/CGMH-EarlyIntervention
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. First-run administrator sign-in: `admin` / `demo1234`. Before deployment, provision a replacement administrator and remove the demo account. The static `index.html` also supports an in-memory preview when opened directly; that preview does not export files, run document extraction, or preserve new accounts after the page closes. Use the FastAPI URL for persistent accounts and Excel, Word, or PDF exports.


## Public test deployment (Render)

`render.yaml` defines a free Singapore web service and a linked PostgreSQL database. Push this app to GitHub, then choose **New + → Blueprint** in Render and connect the repository. Render generates the `ADMIN_PASSWORD`; find it in the service environment settings and share it only with testers who need the admin login. The username is `testadmin`.

When `DATABASE_URL` is set (the Render deployment), the app stores both accounts and records in the linked PostgreSQL database, in the `app_state` table under the `users` and `records` JSONB keys. Without it, local development stores records in `app/data/records.json` and accounts in `app/data/users.json` (or under `HOSPITAL_DATA_DIR`). The free Render PostgreSQL plan is intended for temporary testing and expires after 30 days, so upgrade the database plan before relying on long-term storage. The local JSON files are ignored by Git and are not deployed. The public page warns testers to use synthetic data only. Do not enter real patient information.

## Architecture and API

- `app/main.py`: FastAPI app, demo session auth, upload extraction, record persistence, export.
- `app/classifier.py`: explainable keyword suggestions aligned to the checklist's diagnosis section.
- `app/static/`: bilingual clinical UI and the detailed translated checklist catalog in `diagnosis-data.js`.
- `app/data/records.json`: local prototype storage (created on first save).
- `app/data/users.json`: password hashes and account roles (seeded on first login).

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/login` | Demo username/password; returns bearer token |
| GET | `/api/me` | Validate the current session and return account role |
| POST | `/api/logout` | Revoke current demo token |
| GET/POST | `/api/users` | Administrator-only list/create accounts |
| DELETE | `/api/users/{username}` | Administrator-only account removal |
| POST | `/api/users/{username}/reset-password` | Administrator-only password reset (minimum 8 characters) |
| POST | `/api/classify` | Signed-in users: suggest diagnosis checklist items from text; uncertain/negated mentions are returned separately |
| GET | `/api/records` | List records |
| GET | `/api/storage-status` | Show whether the signed-in deployment uses PostgreSQL or local JSON and current counts |
| POST | `/api/records` | Create/update a reviewed record |
| POST | `/api/records/bulk-delete` | Delete selected records in one request |
| POST | `/api/import-cases` | Import `.xlsx`, `.csv`, and `.txt` case data; tabular files need a `CASE ID` header, and labeled TXT blocks can use `Case ID:` / `Diagnosis:`; each case is a separate preview record, and repeat imports skip known case IDs |
| DELETE | `/api/records/{id}` | Delete a record |
| POST | `/api/extract` | Extract text from an uploaded document for clinician review |
| POST | `/api/export` | Download selected saved records as XLSX, CSV, TXT, DOCX, or PDF. JSON body: `ids` (1–5000 record IDs), `format`, and `lang` (`en` or `zh-TW`) |
| GET | `/api/export?format=xlsx&ids=...` | Compatibility endpoint; repeat `ids` for selected records, or omit IDs for all saved records |

## Scope and clinical use

This is a local demonstration, not a production hospital system. The sample credentials, in-memory sessions, browser-session draft storage, local JSON storage, and basic upload pipeline are not suitable for real patient information. Passwords are stored as salted PBKDF2 hashes; session tokens are kept in process memory. Before deployment, require hospital security review, secure identity integration, role-based access, audit logging, encrypted storage and transport, retention controls, malware scanning, CSRF protections, and validated backup/recovery. Extraction recognizes labeled basic fields only; clinicians must verify extracted values. OCR runs only when Tesseract is installed; recognized language packs `eng` and `chi_tra` are needed for English and Traditional Chinese. Scanned PDF OCR additionally requires Poppler. The supplied diagnosis workbook informs keyword terminology and examples; Excel export uses a compact Case overview sheet, a linked Checklist details sheet organized into the form’s three sections, and a separate Diagnosis matrix sheet with 0/1 flags for analysis.

Diagnosis suggestions use conservative keyword patterns informed by the supplied checklist and sample workbook. They are not trained clinical AI and do not determine diagnoses. Uncertain, suspected, borderline, and locally negated matches are shown separately and left unchecked. The feature covers the checklist's diagnosis section; functional classifications and treatment plans remain manual. Every suggested item needs clinician review before saving.

## Workspace and Excel export

- **Overview** shows activity counts. **Overview & new record** contains the checklist editor below the activity summary. Diagnosis groups expand individually and can be searched; selections stay checked while searching.
- **Records** owns case-list import (XLSX/CSV/TXT), import preview/save, search, date filtering, selection, deletion, and export. The editor’s upload extracts a single source document. Imported cases remain previews until explicitly saved.
- The UI downloads only selected saved records; the download button is disabled until cases are selected. Selections persist across queries and pages. On phones, records display as cards.
- Excel’s **Case overview** has three columns, filters, a frozen Case ID column, and links to each checklist. **Checklist details** separates functional classifications, diagnoses/notes, and management/medication. **Diagnosis matrix** retains all 16 diagnostic group flags and internal record IDs for analysis. All user-entered cell values are stored as text, not Excel formulas.

Run workbook regression checks with the app dependencies installed:

```sh
HOSPITAL_DATA_DIR=/tmp/cgmh-export-tests .venv/bin/python -m unittest discover -s tests -v
```

## Fast-opening frontend (Render Static Site)

The Python service can sleep on a free plan. Serving its own HTML cannot remove the hosting provider's cold-start page on a first visit. The static frontend declared in `render.yaml` serves the login UI independently; only API operations may wait for the Python service. The page starts one health request when opened, supports language switching immediately, distinguishes connection failures from invalid credentials, and keeps form contents on failure. It does not run a keep-alive polling job.

For an existing Render Blueprint, sync this revision to create the additional **Static Site** `chang-gung-rehab-checklist-web`. Do not recreate or delete the existing backend/database. If the existing service was created manually, create a Static Site from the same repository with:

- Build command: `python3 scripts/build_static.py`
- Publish directory: `dist`
- Environment variable `API_BASE_URL`: the existing Python service's HTTPS origin, currently `https://chang-gung-rehab-checklist-demo.onrender.com`.
- On the existing Python service, set `FRONTEND_ORIGINS` to the actual Static Site HTTPS origin (comma-separated exact origins for multiple sites), then deploy it. The blueprint includes the expected default static hostname; use Render's actual assigned hostname if it differs.

Use the **Static Site's** published URL for the fast-opening UI. The old Python-service URL still has Render's cold-start behavior. No credentials are bundled into the static build. CORS permits only explicitly configured origins; authentication remains on the API. Login, saving, OCR, and exports still require a responsive API. This architecture does not provide offline record storage or guarantee a cold API will respond instantly.

Local cross-origin check:

```sh
API_BASE_URL=http://127.0.0.1:8002 python3 scripts/build_static.py
# Separate terminals, starting from the repository root:
FRONTEND_ORIGINS=http://127.0.0.1:8010 uvicorn app.main:app --port 8002
python3 -m http.server 8010 --directory dist
```

With Playwright and Chromium installed, `python tests/browser_smoke.py` builds the static UI, starts both servers with isolated test data, holds/aborts API requests to simulate a sleeping/offline backend, and tests cross-origin login, saved records, language switching, bilingual diagnosis search, Excel output, and desktop widths. It cleans up the servers and test data it creates.

Excel follows the current UI language (`/api/export?format=xlsx&lang=en` or `lang=zh-TW`). Traditional Chinese output includes English field headings for cross-reference, translates known checklist items, and preserves free-text notes without machine translation. `app/export_labels.json` stores export translations corresponding to `app/static/diagnosis-data.js` and the functional/management catalog. Long notes continue across rows so they are not clipped by Excel's row-height limit. Diagnosis flags are highlighted in the separate analysis sheet.


## Case ID-only workflow

Case ID is required in the editor and is the only field used for record search. Patient Name, Chart No, Exam Date, and Physician are omitted from the editor, record list, document-field extraction, and all XLSX/DOCX/PDF outputs. New case-list imports ignore these structured columns. Uploaded source text and free-text clinical notes are not automatically redacted. Existing stored fields remain intact when an older record is edited. Activity counts use the record creation/import timestamp rather than examination dates. Older records without a Case ID display a prompt to add one when editing.


## Unified Records workspace

Overview & new record opens after login and shows the activity summary and inline checklist editor together. Records remains a separate page for querying, selecting, importing, and downloading cases. New record stays in Overview; Edit in Records navigates to that inline editor. There is no separate New record tab or editor dialog. Switching pages preserves the current browser-session draft.

Search one Case ID by partial match, or paste comma/semicolon/newline-separated IDs for exact multi-ID matching. **Select results** adds all matching saved cases across pages; preview imports cannot be selected. Individual checkboxes, removable Case ID chips, and **Clear selection** control the output set. Download sends explicitly selected record IDs, or all saved records matching the active filters when nothing is checked. The selection summary states this scope. Unsaved import previews are excluded. Available formats are XLSX, CSV (UTF-8 BOM, spreadsheet formula escaping), UTF-8 TXT, DOCX, and PDF. The UI posts IDs in a JSON body, shows preparation and download feedback, and asks for sign-in if the session has expired. Excel details register their disjoint merged ranges together to avoid repeated overlap checks during large exports.


The Records layout uses a compact heading with one Import button, a full-width Case ID query row, and a separate selection/download row above the table. Import date is an inline toolbar control with Reset date. Delete selected appears directly beside selection actions when records are selected. Native file-input chrome is visually hidden while the labelled upload remains keyboard accessible. Static builds add content hashes to asset URLs, and the Python-hosted HTML/CSS/JS routes require cache revalidation so styles and markup stay in sync after updates.


Case ID filtering also offers a checkbox dropdown: choose one or multiple IDs without typing, or search inside the dropdown. Options are sorted naturally and displayed 100 at a time with Show more. Reset filter clears only the query/filter; output selections remain until explicitly removed. With checked IDs, the dropdown search narrows its options while the table shows the checked IDs. Select results adds filtered cases to the download selection.


Records has a Select all action that selects every matching saved record across pages (not only the visible page). Bulk Delete appears only after selection and retains its confirmation prompt. Case ID suggestions prioritize exact matches and then prefix matches, highlight the matching text, and support arrow-key navigation. Overview keeps its activity summary and inline editor without a recent-cases table. Routine connection/wakeup is silent; genuine connection failures still show a reconnect action.

## Review imports before saving

XLSX/CSV/TXT case lists now open a separate paginated review dialog. Preview rows never appear in Records and no database writes happen during extraction. Explicit English/Traditional Chinese clinical headers identify Case ID, diagnosis, functional classification, treatment, and medication. Unknown columns are ignored rather than guessed as diagnoses. Unmatched functional/treatment text is retained in notes and included in exports. Original Case IDs are preserved; existing legacy sheet-prefixed IDs are checked during duplicate review without migrating stored records.

Review shows the source file/sheet/row, extracted diagnosis, missing/duplicate ID problems and unreviewed/approved status. Review an individual case to edit fields and checklist selections, or explicitly approve valid filtered results in bulk after confirmation. Only approved selected cases are saved. Missing/duplicate IDs are blocked until corrected or excluded. Saving only some rows retains the remaining preview; closing review keeps it available in the current page session. Refreshing/closing the browser does not persist an unsaved review. Batch saving rechecks IDs on the server, preserves successful batches if a later request fails, and leaves remaining rows for retry. Diagnosis suggestions still require clinical review.


Excel review opens the first case automatically. Each case has its own checkbox checklist, source sheet/ID heading, and Previous/Next navigation; navigation retains edits as unapproved drafts. XLSX zero-padded numeric IDs are preserved; legacy XLS is supported. Unknown headers open a column-mapping dialog for sheet/header/clinical columns instead of failing without a recovery path. If two sheets reuse the same IDs, the reviewer can explicitly choose Separate IDs by sheet (with confirmation), preserving the original ID in source metadata. This changes only the unsaved import and requires approval again.


Imports automatically skip rows with the same Case ID and identical extracted clinical fields, including identical already-saved cases. Rows with the same ID but different clinical content remain in review. This never deletes stored records. The review header reports the number skipped.


Import-review checkboxes allow selecting unreviewed and ID-conflicting rows, including all rows on a review page. Selecting a row opens its checklist. Approval acts on the selected set when present. Save selected cases remains disabled until at least one selected case is approved and has a valid non-conflicting ID. Selection and approval counts are shown separately.


The import-review Diagnosis column displays disease names from the case's selected checklist diagnoses, not the source diagnosis paragraph. It updates when checklist selections change. Raw file diagnosis notes remain separately editable in the case inspector. Cases without selected diagnoses explicitly show No diagnosis selected; an empty match is never presented as a confirmed disease.


Review diagnosis names include their checklist group (for example Psychosocial disorder: Speech delay). Delete selected removes the selected rows only from the unsaved import, after confirmation. Discard duplicates rechecks the current preview after edits and removes only matching Case ID plus identical clinical content, retaining the first preview instance or the already-saved case. Conflicting same-ID cases remain available for review. Neither action deletes saved Records.
