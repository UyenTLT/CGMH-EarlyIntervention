# Hospital Checklist — local prototype

An English / Traditional Chinese prototype for reviewing pediatric rehabilitation checklist records. Existing homework files in the parent folder are unchanged.

## Run

```sh
cd hospital-app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. First-run administrator sign-in: `admin` / `demo1234`. Before deployment, provision a replacement administrator and remove the demo account. The static `index.html` also supports an in-memory preview when opened directly; that preview does not export files, run document extraction, or preserve new accounts after the page closes. Use the FastAPI URL for persistent accounts and Excel, Word, or PDF exports.


## Public test deployment (Render)

`render.yaml` defines a free Singapore web service and a linked PostgreSQL database. Push this app to GitHub, then choose **New + → Blueprint** in Render and connect the repository. Render generates the `ADMIN_PASSWORD`; find it in the service environment settings and share it only with testers who need the admin login. The username is `testadmin`.

When `DATABASE_URL` is set, the app stores accounts and records in PostgreSQL; without it, local development uses the JSON files. The free Render PostgreSQL plan is intended for temporary testing and expires after 30 days, so upgrade the database plan before relying on long-term storage. The local JSON files are ignored by Git and are not deployed. The public page warns testers to use synthetic data only. Do not enter real patient information.

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
| POST | `/api/records` | Create/update a reviewed record |
| POST | `/api/records/bulk-delete` | Delete selected records in one request |
| POST | `/api/import-cases` | Import `.xlsx`, `.csv`, and `.txt` case data; tabular files need a `CASE ID` header, and labeled TXT blocks can use `Case ID:` / `Diagnosis:`; each case is a separate preview record, and repeat imports skip known case IDs |
| DELETE | `/api/records/{id}` | Delete a record |
| POST | `/api/extract` | Extract text from an uploaded document for clinician review |
| GET | `/api/export?format=xlsx&ids=...` | Download selected records (or all when no IDs are supplied) as `.xlsx`, `.docx`, or `.pdf`; repeat `ids` for multiple records |

## Scope and clinical use

This is a local demonstration, not a production hospital system. The sample credentials, in-memory sessions, browser-session draft storage, local JSON storage, and basic upload pipeline are not suitable for real patient information. Passwords are stored as salted PBKDF2 hashes; session tokens are kept in process memory. Before deployment, require hospital security review, secure identity integration, role-based access, audit logging, encrypted storage and transport, retention controls, malware scanning, CSRF protections, and validated backup/recovery. Extraction recognizes labeled basic fields only; clinicians must verify extracted values. OCR runs only when Tesseract is installed; recognized language packs `eng` and `chi_tra` are needed for English and Traditional Chinese. Scanned PDF OCR additionally requires Poppler. The supplied diagnosis workbook informs keyword terminology and examples; export currently uses a default layout containing multi-select text fields plus one 0/1 flag for each diagnostic group.

Diagnosis suggestions use conservative keyword patterns informed by the supplied checklist and sample workbook. They are not trained clinical AI and do not determine diagnoses. Uncertain, suspected, borderline, and locally negated matches are shown separately and left unchecked. The feature covers the checklist's diagnosis section; functional classifications and treatment plans remain manual. Every suggested item needs clinician review before saving.
