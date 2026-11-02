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
| GET | `/api/export?format=xlsx&ids=...` | Download selected records (or all when no IDs are supplied) as `.xlsx`, `.docx`, or `.pdf`; repeat `ids` for multiple records |

## Scope and clinical use

This is a local demonstration, not a production hospital system. The sample credentials, in-memory sessions, browser-session draft storage, local JSON storage, and basic upload pipeline are not suitable for real patient information. Passwords are stored as salted PBKDF2 hashes; session tokens are kept in process memory. Before deployment, require hospital security review, secure identity integration, role-based access, audit logging, encrypted storage and transport, retention controls, malware scanning, CSRF protections, and validated backup/recovery. Extraction recognizes labeled basic fields only; clinicians must verify extracted values. OCR runs only when Tesseract is installed; recognized language packs `eng` and `chi_tra` are needed for English and Traditional Chinese. Scanned PDF OCR additionally requires Poppler. The supplied diagnosis workbook informs keyword terminology and examples; Excel export uses a compact Case overview sheet, a linked Checklist details sheet organized into the form’s three sections, and a separate Diagnosis matrix sheet with 0/1 flags for analysis.

Diagnosis suggestions use conservative keyword patterns informed by the supplied checklist and sample workbook. They are not trained clinical AI and do not determine diagnoses. Uncertain, suspected, borderline, and locally negated matches are shown separately and left unchecked. The feature covers the checklist's diagnosis section; functional classifications and treatment plans remain manual. Every suggested item needs clinician review before saving.

## Workspace and Excel export

- **Overview** shows activity counts. **New record** is the single checklist editor, with one sticky Save action. Diagnosis groups expand individually and can be searched; selections stay checked while searching.
- **Records** owns case-list import (XLSX/CSV/TXT), import preview/save, search, date filtering, selection, deletion, and export. The editor’s upload extracts a single source document. Imported cases remain previews until explicitly saved.
- Export uses selected saved records, or all saved records when none are selected. Search and date filters do not restrict an unselected export. On phones, records display as cards.
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
