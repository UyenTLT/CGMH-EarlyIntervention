from __future__ import annotations

import io, json, secrets, hashlib, hmac, re, os, csv, threading, time, unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.table import Table as ExcelTable, TableStyleInfo
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import CellIsRule
from pydantic import BaseModel, Field
from app.classifier import classify_text

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("HOSPITAL_DATA_DIR", ROOT / "data")).expanduser()
DATA.mkdir(exist_ok=True)
DB = DATA / "records.json"
USERS_DB = DATA / "users.json"
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin").strip().lower() or "admin"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "demo1234")
DIAGNOSIS_GROUPS = {
    "01": "Brain", "02": "Psychosocial disorder", "03": "Spinal cord",
    "04": "Roots and nerves", "05": "Neuromuscular junction", "06": "Muscle disease",
    "07": "Congenital myopathies", "08": "Metabolic myopathies", "09": "Chromosome & syndromes",
    "10": "Endocrine & metabolism", "11": "Mitochondrial", "12": "Neurocutaneous",
    "13": "Vision", "14": "Auditory", "15": "Unspecified delay", "99": "Others",
}
app = FastAPI(title="Hospital Checklist Prototype")
# An exact origin list supports a static CDN frontend; same-origin remains valid.
frontend_origins = [origin.strip().rstrip('/') for origin in os.environ.get("FRONTEND_ORIGINS", "").split(",") if origin.strip()]
if frontend_origins:
    app.add_middleware(CORSMiddleware, allow_origins=frontend_origins,
                       allow_methods=["GET", "POST", "DELETE"],
                       allow_headers=["Authorization", "Content-Type"])


@app.get("/config.js")
def frontend_config():
    return FileResponse(ROOT / "static" / "config.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})

app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
TOKENS: dict[str, str] = {}
STATE_LOCK = threading.RLock()
_PG_SCHEMA_READY = False
_PG_SCHEMA_LOCK = threading.Lock()


class Login(BaseModel):
    username: str
    password: str


class NewUser(BaseModel):
    username: str
    password: str
    role: str = "user"


class PasswordReset(BaseModel):
    password: str


class DeleteRecordsRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=5000)


class ClassifyRequest(BaseModel):
    text: str = Field(max_length=50000)


class Record(BaseModel):
    id: str | None = None
    caseId: str = ""
    patientName: str = ""
    chartNo: str = ""
    examDate: str = ""
    physician: str = ""
    functional: list[str] = Field(default_factory=list)
    diagnoses: list[str] = Field(default_factory=list)
    diagnosisLabels: list[str] = Field(default_factory=list)
    classificationReview: list[dict[str, str]] = Field(default_factory=list)
    classificationStatus: str = "review"
    diagnosisNotes: str = ""
    management: list[str] = Field(default_factory=list)
    functionalNotes: str = ""
    managementNotes: str = ""
    importSource: dict[str, Any] = Field(default_factory=dict)
    medication: str = ""
    sourceText: str = ""
    importedAt: str = ""


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256${salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 310_000).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except (ValueError, TypeError):
        return False


def _database_url() -> str | None:
    return os.environ.get("DATABASE_URL")


def _pg_get(key: str):
    import psycopg
    url = _database_url()
    if not url:
        return None
    _pg_ensure_schema(url)
    try:
        with psycopg.connect(url.replace("postgres://", "postgresql://", 1), connect_timeout=10) as conn:
            row = conn.execute("SELECT value FROM app_state WHERE key = %s", (key,)).fetchone()
            return row[0] if row else None
    except Exception as exc:
        raise HTTPException(503, "Database connection unavailable") from exc


def _pg_set(key: str, value: Any):
    import psycopg
    from psycopg.types.json import Jsonb
    url = _database_url()
    if not url:
        return
    _pg_ensure_schema(url)
    try:
        with psycopg.connect(url.replace("postgres://", "postgresql://", 1), connect_timeout=10) as conn:
            conn.execute(
                "INSERT INTO app_state (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, Jsonb(value)),
            )
    except Exception as exc:
        raise HTTPException(503, "Database connection unavailable") from exc


def _pg_ensure_schema(url: str):
    global _PG_SCHEMA_READY
    if _PG_SCHEMA_READY:
        return
    with _PG_SCHEMA_LOCK:
        if _PG_SCHEMA_READY:
            return
        import psycopg
        try:
            with psycopg.connect(url.replace("postgres://", "postgresql://", 1), connect_timeout=10) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS app_state (key text PRIMARY KEY, value jsonb NOT NULL)")
            _PG_SCHEMA_READY = True
        except Exception as exc:
            raise HTTPException(503, "Database connection unavailable") from exc


def _initial_admin() -> dict[str, str]:
    return {"username": ADMIN_USERNAME, "role": "admin", "passwordHash": _password_hash(ADMIN_PASSWORD)}


def _json_read(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        try:
            corrupt = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
            os.replace(path, corrupt)
        except OSError:
            pass
        return default


def _json_write(path: Path, value: Any):
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def load_users() -> list[dict[str, str]]:
    with STATE_LOCK:
        if _database_url():
            users = _pg_get("users")
            if users is None:
                users = [_initial_admin()]
                _pg_set("users", users)
                return users
            # Keep the configured admin login available after a Render restart
            # without re-hashing its password on every authenticated request.
            if not any(user.get("username") == ADMIN_USERNAME for user in users):
                users.append(_initial_admin())
                _pg_set("users", users)
            return users
        users = _json_read(USERS_DB, None)
        if users is None:
            users = [_initial_admin()]
            _json_write(USERS_DB, users)
            return users
        if not any(user.get("username") == ADMIN_USERNAME for user in users):
            users.append(_initial_admin())
            _json_write(USERS_DB, users)
        return users


def save_users(users: list[dict[str, str]]):
    with STATE_LOCK:
        if _database_url():
            _pg_set("users", users)
            return
        _json_write(USERS_DB, users)


def auth(authorization: str | None = Header(default=None)) -> dict[str, str]:
    token = authorization.removeprefix("Bearer ") if authorization else ""
    username = TOKENS.get(token)
    user = next((u for u in load_users() if u.get("username") == username), None)
    if user is None:
        raise HTTPException(401, "Sign in required")
    return user


def admin_auth(user: dict[str, str] = Depends(auth)) -> dict[str, str]:
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator access required")
    return user


def read_records() -> list[dict[str, Any]]:
    with STATE_LOCK:
        if _database_url():
            return _pg_get("records") or []
        return _json_read(DB, [])


def write_records(rows: list[dict[str, Any]]):
    with STATE_LOCK:
        if _database_url():
            _pg_set("records", rows)
            return
        _json_write(DB, rows)


def extract_basic_fields(text: str) -> dict[str, str]:
    """Conservative label-based extraction only; no clinical diagnosis inference."""
    match = re.search(r"(?:case\s*(?:id|no\.?|number)|caseid|個案編號)\s*[:：=|]\s*([^\r\n|;,]+)", text, re.IGNORECASE)
    return {"caseId": match.group(1).strip()} if match else {}



@app.get("/", response_class=HTMLResponse)
def home():
    return FileResponse(ROOT / "static" / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/style.css")
def stylesheet():
    return FileResponse(ROOT / "static" / "style.css", media_type="text/css", headers={"Cache-Control": "no-cache"})


@app.get("/app.js")
def frontend_script():
    return FileResponse(ROOT / "static" / "app.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/import-review.js")
def import_review_script():
    return FileResponse(ROOT / "static" / "import-review.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/diagnosis-data.js")
def diagnosis_data_script():
    return FileResponse(ROOT / "static" / "diagnosis-data.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@app.post("/api/login")
def login(body: Login):
    username = body.username.strip().lower()
    user = next((u for u in load_users() if u.get("username") == username), None)
    if user is None or not _verify_password(body.password, user["passwordHash"]):
        raise HTTPException(401, "Invalid username or password")
    token = secrets.token_urlsafe(32)
    TOKENS[token] = username
    return {"token": token, "username": username, "role": user["role"]}


@app.get("/api/me")
def current_session(user: dict[str, str] = Depends(auth)):
    return {"username": user["username"], "role": user["role"]}


@app.post("/api/classify", dependencies=[Depends(auth)])
def classify_diagnoses(body: ClassifyRequest):
    return classify_text(body.text)


@app.post("/api/logout", dependencies=[Depends(auth)])
def logout(authorization: str | None = Header(default=None)):
    TOKENS.pop(authorization.removeprefix("Bearer "), None)
    return {"ok": True}


@app.get("/api/users", dependencies=[Depends(admin_auth)])
def users():
    return [{"username": u["username"], "role": u["role"]} for u in load_users()]


@app.post("/api/users", dependencies=[Depends(admin_auth)])
def create_user(body: NewUser):
    username = body.username.strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,32}", username):
        raise HTTPException(422, "Username must be 3–32 characters: letters, numbers, dot, underscore, or hyphen")
    if len(body.password) < 8:
        raise HTTPException(422, "Password must contain at least 8 characters")
    if body.role not in {"admin", "user"}:
        raise HTTPException(422, "Role must be admin or user")
    with STATE_LOCK:
        rows = load_users()
        if any(u.get("username") == username for u in rows):
            raise HTTPException(409, "Username already exists")
        rows.append({"username": username, "role": body.role, "passwordHash": _password_hash(body.password)})
        save_users(rows)
    return {"username": username, "role": body.role}


@app.delete("/api/users/{username}")
def delete_user(username: str, current: dict[str, str] = Depends(admin_auth)):
    username = username.lower()
    with STATE_LOCK:
        rows = load_users()
        target = next((u for u in rows if u.get("username") == username), None)
        if target is None:
            raise HTTPException(404, "Account not found")
        if username == current["username"]:
            raise HTTPException(400, "You cannot remove your own account")
        if target.get("role") == "admin" and sum(u.get("role") == "admin" for u in rows) <= 1:
            raise HTTPException(400, "At least one administrator account must remain")
        save_users([u for u in rows if u.get("username") != username])
    for token, owner in list(TOKENS.items()):
        if owner == username:
            TOKENS.pop(token, None)
    return {"ok": True}


@app.post("/api/users/{username}/reset-password")
def reset_user_password(username: str, body: PasswordReset, current: dict[str, str] = Depends(admin_auth)):
    if len(body.password) < 8:
        raise HTTPException(422, "Password must contain at least 8 characters")
    with STATE_LOCK:
        rows = load_users()
        target = next((u for u in rows if u.get("username") == username.lower()), None)
        if target is None:
            raise HTTPException(404, "Account not found")
        target["passwordHash"] = _password_hash(body.password)
        save_users(rows)
    for token, owner in list(TOKENS.items()):
        if owner == target["username"]:
            TOKENS.pop(token, None)
    return {"ok": True}


@app.get("/api/health")
def health():
    """Non-sensitive deployment check for persistence configuration."""
    if not _database_url():
        return {"ok": True, "backend": "json", "persistent": False, "message": "DATABASE_URL is not configured"}
    try:
        rows = read_records()
        return {"ok": True, "backend": "postgresql", "persistent": True, "records": len(rows)}
    except Exception as exc:
        return JSONResponse(status_code=503, content={"ok": False, "backend": "postgresql", "persistent": False, "message": "Database connection unavailable"})


@app.get("/api/records", dependencies=[Depends(auth)])
def records():
    return read_records()


@app.get("/api/storage-status", dependencies=[Depends(auth)])
def storage_status():
    """Expose where this deployment persists data so admins can verify it."""
    if _database_url():
        return {"backend": "postgresql", "location": "DATABASE_URL / app_state", "records": len(read_records()), "users": len(load_users())}
    return {"backend": "json", "location": str(DATA), "records": len(read_records()), "users": len(load_users())}


@app.post("/api/records", dependencies=[Depends(auth)])
def save_record(body: Record):
    with STATE_LOCK:
        rows = read_records()
        row = body.model_dump()
        row["id"] = body.id or secrets.token_hex(8)
        old = next((i for i, x in enumerate(rows) if x.get("id") == row["id"]), None)
        if old is None:
            row["importedAt"] = row.get("importedAt") or datetime.now().isoformat(timespec="seconds")
        else:
            row["importedAt"] = row.get("importedAt") or rows[old].get("importedAt", "")
        if old is None:
            rows.insert(0, row)
        else:
            for key in ("patientName", "chartNo", "examDate", "physician", "importSource"):
                if key not in body.model_fields_set and key in rows[old]:
                    row[key] = rows[old][key]
            rows[old] = row
        write_records(rows)
    return row


@app.post("/api/records/bulk", dependencies=[Depends(auth)])
def save_records_bulk(records: list[Record]):
    if len(records) > 5000:
        raise HTTPException(413, "Too many records in one save")
    with STATE_LOCK:
        rows = read_records()
        known_cases = {str(row.get("caseId") or "").strip().casefold() for row in rows if row.get("caseId")}
        saved, skipped = [], 0
        for item in records:
            row = item.model_dump()
            row["caseId"] = row["caseId"].strip()
            if not row["caseId"]:
                raise HTTPException(422, "Every imported record needs a Case ID")
            if row["caseId"].casefold() in known_cases:
                skipped += 1
                continue
            row["id"] = row.get("id") or secrets.token_hex(8)
            row["importedAt"] = row.get("importedAt") or datetime.now().isoformat(timespec="seconds")
            rows.insert(0, row)
            if row.get("caseId"):
                known_cases.add(row["caseId"].casefold())
            saved.append(row)
        if saved:
            write_records(rows)
    return {"saved": len(saved), "skipped": skipped, "records": saved, "storage": "postgresql" if _database_url() else "json"}


@app.post("/api/records/bulk-delete", dependencies=[Depends(auth)])
def delete_records_bulk(body: DeleteRecordsRequest):
    selected = set(body.ids)
    with STATE_LOCK:
        rows = read_records()
        kept = [row for row in rows if str(row.get("id")) not in selected]
        deleted = len(rows) - len(kept)
        if deleted:
            write_records(kept)
    return {"deleted": deleted}


@app.post("/api/import-cases", dependencies=[Depends(auth)])
async def import_cases(file: UploadFile = File(...), mapping: str | None = Form(default=None)):
    name = (file.filename or "").lower()
    extension = Path(name).suffix
    if extension not in {".xlsx", ".xls", ".csv", ".txt"}:
        raise HTTPException(415, "Choose an .xlsx, .xls, .csv, or .txt file")
    raw = await file.read()
    if len(raw) > 30 * 1024 * 1024:
        raise HTTPException(413, "Import file exceeds 30 MB limit")
    datasets: list[tuple[str, list[tuple[Any, ...]]]] = []
    if extension == ".xlsx":
        try:
            from openpyxl import load_workbook
            workbook = load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
            datasets = []
            for sheet in workbook.worksheets:
                table = []
                for cells in sheet.iter_rows():
                    values = []
                    for cell in cells:
                        value = cell.value
                        if isinstance(value, (int, float)) and not isinstance(value, bool) and float(value).is_integer() and re.fullmatch(r"0{2,}", cell.number_format or ""):
                            value = str(int(value)).zfill(len(cell.number_format))
                        values.append(value)
                    table.append(tuple(values))
                datasets.append((sheet.title, table))
            workbook.close()
        except Exception as exc:
            raise HTTPException(422, "Could not read the Excel workbook") from exc
    elif extension == ".xls":
        try:
            import xlrd
            book = xlrd.open_workbook(file_contents=raw)
            datasets = [(sheet.name, [tuple(sheet.row_values(i)) for i in range(sheet.nrows)]) for sheet in book.sheets()]
        except Exception as exc:
            raise HTTPException(422, "Could not read the legacy Excel workbook") from exc
    else:
        text = None
        for encoding in ("utf-8-sig", "utf-16", "cp950", "cp1252"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise HTTPException(422, "Could not decode the text file; save it as UTF-8 and try again")
        if extension == ".csv":
            try:
                dialect = csv.Sniffer().sniff(text[:8192], delimiters=",\t;|")
            except csv.Error:
                dialect = csv.excel
            table = [tuple(row) for row in csv.reader(io.StringIO(text), dialect) if any(str(cell).strip() for cell in row)]
            datasets = [(Path(name).stem or "CSV", table)]
        else:
            lines = text.splitlines()
            first_content = next((line for line in lines if line.strip()), "")
            try:
                dialect = csv.Sniffer().sniff(text[:8192], delimiters="\t,;|")
                table = [tuple(row) for row in csv.reader(io.StringIO(text), dialect) if any(str(cell).strip() for cell in row)]
            except csv.Error:
                table = []
            header_probe = re.sub(r"[^a-z0-9]+", " ", first_content.casefold()).strip()
            if table and re.search(r"\bcase\s*(?:id|no|number)\b", header_probe):
                datasets = [(Path(name).stem or "TXT", table)]
            else:
                fields = {"case": "Case ID", "patient": "Patient Name", "chart": "Chart No", "diagnosis": "Diagnosis", "date": "Exam Date", "physician": "Physician", "functional": "Functional Classifications", "management": "Treatment Plan", "medication": "Medication"}
                label_patterns = {
                    "case": re.compile(r"^\s*(?:case\s*(?:id|no\.?|number)|caseid|個案編號)\s*[:：=]\s*(.*)$", re.I),
                    "patient": re.compile(r"^\s*(?:patient(?:\s*name)?|name|病患姓名|姓名)\s*[:：=]\s*(.*)$", re.I),
                    "chart": re.compile(r"^\s*(?:chart\s*(?:no\.?|number)|medical\s*record\s*(?:no\.?|number)|病歷號碼?|病歷編號)\s*[:：=]\s*(.*)$", re.I),
                    "diagnosis": re.compile(r"^\s*(?:clinical\s*)?diagnosis(?:\s*(?:text|summary))?\s*[:：=]\s*(.*)$|^\s*診斷(?:內容)?\s*[:：=]\s*(.*)$", re.I),
                    "date": re.compile(r"^\s*(?:exam(?:ination)?\s*date|date|檢查日期)\s*[:：=]\s*(.*)$", re.I),
                    "functional": re.compile(r"^\s*(?:functional(?:\s*classifications?)?|功能性診斷分類|功能分類)\s*[:：=]\s*(.*)$", re.I),
                    "management": re.compile(r"^\s*(?:treatment(?:\s*plan)?|management|rehabilitation|處置(?:計畫)?|處置與介入)\s*[:：=]\s*(.*)$", re.I),
                    "medication": re.compile(r"^\s*(?:medication(?:\s*/?\s*notes)?|medicine|藥物(?:／備註)?)\s*[:：=]\s*(.*)$", re.I),
                    "physician": re.compile(r"^\s*(?:physician|doctor|醫師)\s*[:：=]\s*(.*)$", re.I),
                }
                records, current, active = [], {}, None
                for line in lines + [""]:
                    stripped = line.strip()
                    if not stripped:
                        if current.get("Case ID"):
                            records.append(tuple(current.get(fields[key], "") for key in fields))
                        current, active = {}, None
                        continue
                    matched = False
                    for key, pattern in label_patterns.items():
                        match = pattern.match(stripped)
                        if not match:
                            continue
                        if key == "case" and current.get("Case ID"):
                            records.append(tuple(current.get(fields[field], "") for field in fields))
                            current = {}
                        value = next((part for part in match.groups() if part is not None), "").strip()
                        header = fields[key]
                        current[header] = f"{current[header]} {value}".strip() if key == "diagnosis" and current.get(header) else value
                        active = header if key in {"diagnosis", "functional", "management", "medication"} else None
                        matched = True
                        break
                    if not matched and active:
                        current[active] = f"{current.get(active, '')}\n{stripped}".strip()
                datasets = [(Path(name).stem or "TXT", [tuple(fields.values()), *records])]
    from app.importing import preview_import
    try:
        options = json.loads(mapping) if isinstance(mapping, str) and mapping else None
        if options is not None and not isinstance(options, dict):
            raise ValueError('Invalid column mapping')
        result = preview_import(datasets, read_records(), file.filename or name, options)
        if not result['records']:
            raise ValueError('No cases found below the selected header row')
        return result
    except (ValueError, TypeError) as exc:
        sheets = [{'name': sheet, 'rows': [[str(value or '')[:100] for value in row[:60]] for row in table[:30]]} for sheet, table in datasets if table]
        return JSONResponse(status_code=422, content={'detail': {'code': 'column_mapping_required', 'message': str(exc), 'sheets': sheets}})


@app.delete("/api/records/{record_id}", dependencies=[Depends(auth)])
def delete_record(record_id: str):
    with STATE_LOCK:
        rows = read_records()
        kept = [row for row in rows if row.get("id") != record_id]
        if len(kept) == len(rows):
            raise HTTPException(404, "Record not found")
        write_records(kept)
    return {"ok": True}


@app.post("/api/extract", dependencies=[Depends(auth)])
async def extract(file: UploadFile = File(...)):
    name = (file.filename or "").lower()
    raw = await file.read()
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(413, "File exceeds 15 MB limit")
    text = ""
    try:
        if name.endswith(".xlsx"):
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
            text = "\n".join(" | ".join(str(c) for c in row if c is not None) for ws in wb for row in ws.iter_rows(values_only=True) if any(c is not None for c in row))
        elif name.endswith(".xls"):
            try:
                import xlrd
                book = xlrd.open_workbook(file_contents=raw)
                text = "\n".join(" | ".join(str(c) for c in row if c not in (None, "")) for sheet in book.sheets() for row in sheet.get_rows() if any(c not in (None, "") for c in row))
            except ImportError as exc:
                raise HTTPException(415, "Legacy .xls support is not installed. Save as .xlsx and upload again.") from exc
        elif name.endswith(".docx"):
            from docx import Document
            doc = Document(io.BytesIO(raw))
            text = "\n".join([p.text for p in doc.paragraphs] + [" | ".join(c.text for c in row.cells) for t in doc.tables for row in t.rows])
        elif name.endswith(".pdf"):
            from pypdf import PdfReader
            text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(raw)).pages)
            if not text.strip():
                try:
                    import pytesseract
                    from pdf2image import convert_from_bytes
                    pages = convert_from_bytes(raw, dpi=180, first_page=1, last_page=20)
                    text = "\n".join(pytesseract.image_to_string(page, lang="eng+chi_tra") for page in pages)
                except Exception as exc:
                    raise HTTPException(422, "Scanned PDF OCR needs Tesseract, eng/chi_tra language data, and Poppler.") from exc
        elif name.endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff")):
            try:
                import pytesseract
                from PIL import Image
                text = pytesseract.image_to_string(Image.open(io.BytesIO(raw)), lang="eng+chi_tra")
            except Exception as exc:
                raise HTTPException(422, "Image OCR unavailable. Install Tesseract with eng and chi_tra language data.") from exc
        elif name.endswith(".doc"):
            raise HTTPException(415, "Legacy .doc is unsupported; save as .docx and upload again")
        else:
            raise HTTPException(415, "Supported: xlsx, xls, docx, pdf, png, jpg")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, f"Could not extract document: {exc}") from exc
    clipped = text[:50000]
    return {"filename": file.filename, "text": clipped, "fields": extract_basic_fields(clipped)}


def diagnosis_group_codes(record: dict[str, Any]) -> list[str]:
    """Return checklist diagnosis group codes in the checklist's defined order."""
    codes = set()
    for value in record.get("diagnoses", []) or []:
        match = re.match(r"diag-(\d+)-", str(value))
        if match and match.group(1) in DIAGNOSIS_GROUPS:
            codes.add(match.group(1))
    return sorted(codes, key=lambda code: (int(code), code))


def primary_diagnosis_group(record: dict[str, Any]) -> str:
    codes = diagnosis_group_codes(record)
    if not codes:
        return "Unclassified"
    return "; ".join(f"{code} — {DIAGNOSIS_GROUPS[code]}" for code in codes)


def record_sort_key(record: dict[str, Any]):
    codes = diagnosis_group_codes(record)
    rank = int(codes[0]) if codes else 1000
    return (rank, str(record.get("caseId", "")).casefold())


def ordered_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=record_sort_key)


def selected_records(ids: list[str]) -> list[dict[str, Any]]:
    rows = read_records()
    if ids:
        selected = set(ids)
        rows = [row for row in rows if str(row.get("id")) in selected]
    return ordered_records(rows)


def record_export_rows(rows: list[dict[str, Any]]) -> list[list[str]]:
    header = ["Case ID", "Functional Classifications", "Diagnostic Items", "Treatment Plan", "Medication"]
    return [header] + [[str(r.get("caseId", "")), "; ".join(r.get("functional", [])), "; ".join(r.get("diagnosisLabels", []) + ([r["diagnosisNotes"]] if r.get("diagnosisNotes") else [])), "; ".join(r.get("management", [])), str(r.get("medication", ""))] for r in rows]


EXPORT_LABELS = json.loads((ROOT / "export_labels.json").read_text(encoding="utf-8"))
EXPORT_HEADINGS = {'CASE ID': '個案編號', 'Patient Name': '病患姓名', 'Chart No': '病歷號碼', 'Exam Date': '檢查日期', 'Physician': '醫師', 'Diagnosis Groups': '診斷分類', 'Checklist': '檢核表', 'REHABILITATION CHECKLIST': '小兒復健科檢核表', 'One section per evaluation · Matches the three sections of the hospital checklist': '每筆評估獨立呈現 · 依醫院檢核表三大部分編排', 'Record ID': '紀錄編號', 'Case ID': '個案編號', 'I. FUNCTIONAL CLASSIFICATION': '一、功能性診斷分類', 'II. DIAGNOSIS': '二、診斷分類', 'Diagnosis notes': '診斷補充說明', 'III. MANAGEMENT & INTERVENTIONS': '三、處置與介入', 'Medication / notes': '藥物／備註', 'View checklist →': '檢視檢核表 →', 'Back to case list ↑': '返回個案清單 ↑', 'Functional Classifications': '功能性診斷分類', 'Diagnostic Items': '診斷項目', 'Treatment Plan': '處置計畫', 'Medication': '藥物／備註', 'No saved evaluations to export.': '沒有可匯出的已儲存評估紀錄。', 'Unnamed patient': '未填寫姓名'}


def export_heading(value: str, lang: str) -> str:
    if lang != "zh-TW":
        return value
    translated = EXPORT_HEADINGS.get(value)
    return f"{translated}\n{value}" if translated else value


def build_checklist_workbook(rows: list[dict[str, Any]], lang: str = "en") -> Workbook:
    """Keep the daily case list compact and the clinical checklist readable."""
    def heading(value: str) -> str:
        return export_heading(value, lang)
    wb = Workbook()
    overview = wb.active
    overview.title = "Case overview"
    overview.append(["CASE ID", *[heading(value) for value in ["Diagnosis Groups", "Checklist"]]])
    details = wb.create_sheet("Checklist details")
    details.append([heading("REHABILITATION CHECKLIST"), "", "", ""])
    details.merge_cells("A1:D1")
    details.append([heading("One section per evaluation · Matches the three sections of the hospital checklist"), "", "", ""])
    details.merge_cells("A2:D2")
    details.append(["", "", "", ""])
    matrix = wb.create_sheet("Diagnosis matrix")
    matrix.append(["CASE ID", heading("Record ID"), *[f"{code} — {EXPORT_LABELS['groups'][code]}\n{name}" if lang == "zh-TW" else f"{code} — {name}" for code, name in DIAGNOSIS_GROUPS.items()]])

    def text(value: Any) -> str:
        return str(value or "")

    def listed(values: list[str]) -> str:
        return "\n".join(EXPORT_LABELS["values"].get(str(value), str(value)) if lang == "zh-TW" else EXPORT_LABELS["english"].get(str(value), str(value)) for value in values or [])

    for index, record in enumerate(rows, start=1):
        start = details.max_row + 1
        case_id = text(record.get("caseId"))
        overview.append([case_id, ("; ".join(f"{code} — {EXPORT_LABELS['groups'][code]}" for code in diagnosis_group_codes(record)) or "未分類") if lang == "zh-TW" else primary_diagnosis_group(record), heading("View checklist →")])
        link = overview.cell(index + 1, 3)
        link.hyperlink = f"#'Checklist details'!A{start}"
        link.font = Font(name="Calibri", color="167568", underline="single")
        details.append([f"{index:02d} · {case_id or 'Case ID missing'}", "", "", ""])
        details.merge_cells(start_row=start, start_column=1, end_row=start, end_column=4)
        details.append([heading("Case ID"), case_id, "", ""])
        details.merge_cells(start_row=start + 1, start_column=2, end_row=start + 1, end_column=4)
        diagnosis_items = record.get("diagnosisLabels") or record.get("diagnoses", [])
        sections = [
            ("I. FUNCTIONAL CLASSIFICATION", listed(record.get("functional", [])) + ("\n" + record["functionalNotes"] if record.get("functionalNotes") else "")),
            ("II. DIAGNOSIS", listed(diagnosis_items)),
            ("Diagnosis notes", text(record.get("diagnosisNotes"))),
            ("III. MANAGEMENT & INTERVENTIONS", listed(record.get("management", [])) + ("\n" + record["managementNotes"] if record.get("managementNotes") else "")),
            ("Medication / notes", text(record.get("medication"))),
            ("Record ID", text(record.get("id"))),
        ]
        for label, value in sections:
            # Merged Excel cells do not auto-fit row heights. Continue long notes
            # across rows instead of silently clipping them at Excel's height limit.
            chunks = []
            begin, width, lines = 0, 0, 1
            for position, char in enumerate(value):
                if char == "\n":
                    lines += 1
                    width = 0
                else:
                    width += 2 if unicodedata.east_asian_width(char) in "WF" else 1
                    if width > 76:
                        lines += 1
                        width = 2 if unicodedata.east_asian_width(char) in "WF" else 1
                if lines >= 18:
                    chunks.append(value[begin:position + 1])
                    begin, width, lines = position + 1, 0, 1
            if begin < len(value) or not chunks:
                chunks.append(value[begin:])
            for part, chunk in enumerate(chunks):
                caption = heading(label)
                if part:
                    caption += "\n（續）" if lang == "zh-TW" else " (continued)"
                details.append([caption, chunk, "", ""])
                line = details.max_row
                details.merge_cells(start_row=line, start_column=2, end_row=line, end_column=4)
                details.cell(line, 1).font = Font(name="Calibri", bold=True, color="38594E", size=11)
                details.cell(line, 1).fill = PatternFill("solid", fgColor="EFF6F2")
                visual_lines = sum(max(1, (sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in segment) + 75) // 76) for segment in (chunk or "—").split("\n"))
                details.row_dimensions[line].height = min(400, max(52 if lang == "zh-TW" else 32, visual_lines * 16 + 12))
        details.append([heading("Back to case list ↑"), "", "", ""])
        details.cell(details.max_row, 1).hyperlink = f"#'Case overview'!A{index + 1}"
        details.cell(details.max_row, 1).font = Font(name="Calibri", color="167568", underline="single")
        details.append(["", "", "", ""])
        selected_groups = set(diagnosis_group_codes(record))
        matrix.append([case_id, text(record.get("id")), *[int(code in selected_groups) for code in DIAGNOSIS_GROUPS]])
        for cell in details[start]:
            cell.fill = PatternFill("solid", fgColor="167568")
            cell.font = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
        details.row_dimensions[start].height = 36
        details.row_dimensions[start + 1].height = 40 if lang == "zh-TW" else 30
        details.row_dimensions[start + 2].height = 40 if lang == "zh-TW" else 30

    details.row_dimensions[2].height = 42 if lang == "zh-TW" else 30
    if not rows:
        details.append([heading("No saved evaluations to export.")])

    for ws, widths in [(overview, [28, 64, 26]), (details, [34, 36, 20, 32]), (matrix, [28, 24] + [22] * len(DIAGNOSIS_GROUPS))]:
        ws.sheet_view.showGridLines = False
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.sheet_properties.outlinePr.summaryRight = False
        ws.freeze_panes = "B2" if ws != details else "B4"
        ws.print_options.horizontalCentered = True
        ws.page_setup.orientation = "landscape" if ws != details else "portrait"
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.print_title_rows = "1:1" if ws != details else "1:2"
        ws.print_area = ws.dimensions
        ws.oddFooter.center.text = "Page &P of &N"
        for col, width in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(col)].width = width
        for row in ws:
            for cell in row:
                if not cell.has_style:
                    cell.font = Font(name="Calibri", size=11, color="223B46")
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                # Treat user-entered values as text, including strings starting with '='.
                if isinstance(cell.value, str):
                    cell.data_type = "s"
        for cell in ws[1]:
            cell.fill = PatternFill("solid", fgColor="167568")
            cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.row_dimensions[1].height = 36 if ws != matrix else 58
        if ws != details:
            ws.auto_filter.ref = ws.dimensions
            if rows:
                table = ExcelTable(displayName="Cases" if ws == overview else "DiagnosisCodes", ref=ws.dimensions)
                table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium4", showRowStripes=True)
                ws.add_table(table)
            for row in ws.iter_rows(min_row=2):
                ws.row_dimensions[row[0].row].height = max(36, min(160, 16 * max((len(str(cell.value or "")) // widths[cell.column-1] + 1) for cell in row) + 12))
    if rows:
        matrix.conditional_formatting.add(f"C2:R{matrix.max_row}", CellIsRule(operator="equal", formula=["1"], fill=PatternFill("solid", fgColor="DDEFE2"), font=Font(color="145B3C", bold=True)))
    return wb


@app.get("/api/export", dependencies=[Depends(auth)])
def export(format: str = "xlsx", ids: list[str] = Query(default=[]), lang: str = Query(default="en", pattern="^(en|zh-TW)$")):
    rows = selected_records(ids)
    if ids and not rows:
        raise HTTPException(404, "No matching records selected")
    if format in {"csv", "txt"}:
        def translated(values):
            catalog = EXPORT_LABELS["values"] if lang == "zh-TW" else EXPORT_LABELS["english"]
            return "\n".join(catalog.get(str(value), str(value)) for value in values or [])

        fields = ["CASE ID", "Diagnosis Groups", "Functional Classifications", "Diagnostic Items", "Diagnosis notes", "Treatment Plan", "Medication"]
        values = [[str(row.get("caseId") or ""), primary_diagnosis_group(row), translated(row.get("functional", [])) + ("\n" + row["functionalNotes"] if row.get("functionalNotes") else ""), translated(row.get("diagnosisLabels") or row.get("diagnoses", [])), str(row.get("diagnosisNotes") or ""), translated(row.get("management", [])) + ("\n" + row["managementNotes"] if row.get("managementNotes") else ""), str(row.get("medication") or "")] for row in rows]
        if format == "csv":
            def safe_cell(value):
                # CSV spreadsheet programs interpret leading formula characters.
                return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r")) else value
            output = io.StringIO(newline="")
            writer = csv.writer(output)
            writer.writerow([field if field == "CASE ID" else export_heading(field, lang) for field in fields])
            writer.writerows([[safe_cell(value) for value in row] for row in values])
            raw = output.getvalue().encode("utf-8-sig")
            media_type = "text/csv; charset=utf-8"
        else:
            blocks = ["\n".join(f"{export_heading(field, lang).replace(chr(10), ' / ')}: {value}" for field, value in zip(fields, row)) for row in values]
            raw = ("\n\n".join(blocks) + ("\n" if blocks else "")).encode("utf-8")
            media_type = "text/plain; charset=utf-8"
        return StreamingResponse(io.BytesIO(raw), media_type=media_type, headers={"Content-Disposition": f'attachment; filename="hospital_checklist.{format}"'})
    if format == "docx":
        from docx import Document
        document = Document()
        document.add_heading("Hospital Rehabilitation Checklist Records", 0)
        for record in rows:
            document.add_heading(record.get("caseId") or "Case ID missing", level=1)
            table = document.add_table(rows=0, cols=2)
            table.style = "Light Shading Accent 1"
            fields = [("Record ID", record.get("id", "")), ("Case ID", record.get("caseId", "")), ("Primary diagnosis group", primary_diagnosis_group(record)), ("Functional classifications", "; ".join(record.get("functional", []) + ([record["functionalNotes"]] if record.get("functionalNotes") else []))), ("Diagnosis", "; ".join(record.get("diagnosisLabels", []) + ([record["diagnosisNotes"]] if record.get("diagnosisNotes") else []))), ("Treatment plan", "; ".join(record.get("management", []) + ([record["managementNotes"]] if record.get("managementNotes") else []))), ("Medication / notes", record.get("medication", ""))]
            for label, value in fields:
                cells = table.add_row().cells
                cells[0].text, cells[1].text = label, str(value)
        buf = io.BytesIO(); document.save(buf); buf.seek(0)
        return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": 'attachment; filename="hospital_checklist.docx"'})
    if format == "pdf":
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import landscape, letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except ImportError as exc:
            raise HTTPException(503, "PDF export dependency is missing; install reportlab") from exc
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(letter), rightMargin=0.45*inch, leftMargin=0.45*inch, topMargin=0.45*inch, bottomMargin=0.45*inch)
        styles = getSampleStyleSheet()
        cjk_font = Path("/System/Library/Fonts/PingFang.ttc")
        if cjk_font.exists():
            pdfmetrics.registerFont(TTFont("ChecklistCJK", str(cjk_font), subfontIndex=0))
            for style in styles.byName.values():
                style.fontName = "ChecklistCJK"
        story = [Paragraph("Hospital Rehabilitation Checklist Records", styles["Title"]), Spacer(1, 12)]
        for record in rows:
            story.append(Paragraph(str(record.get("caseId") or "Case ID missing"), styles["Heading2"]))
            data = [["Field", "Value"]] + [[label, str(value or "")] for label, value in [("Record ID", record.get("id")), ("Case ID", record.get("caseId")), ("Primary diagnosis group", primary_diagnosis_group(record)), ("Functional classifications", "; ".join(record.get("functional", []) + ([record["functionalNotes"]] if record.get("functionalNotes") else []))), ("Diagnosis", "; ".join(record.get("diagnosisLabels", []) + ([record["diagnosisNotes"]] if record.get("diagnosisNotes") else []))), ("Treatment plan", "; ".join(record.get("management", []) + ([record["managementNotes"]] if record.get("managementNotes") else []))), ("Medication / notes", record.get("medication"))]]
            table = Table([[Paragraph(escape(str(cell)), styles["BodyText"]) for cell in row] for row in data], colWidths=[1.8*inch, 8.0*inch], repeatRows=1)
            table.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0), colors.HexColor("#bd7137")), ("TEXTCOLOR", (0,0),(-1,0), colors.white), ("GRID", (0,0),(-1,-1), .4, colors.HexColor("#dedede")), ("VALIGN", (0,0),(-1,-1), "TOP"), ("PADDING", (0,0),(-1,-1), 6)]))
            story.extend([table, Spacer(1, 12)])
        doc.build(story); buf.seek(0)
        return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="hospital_checklist.pdf"'})
    if format != "xlsx":
        raise HTTPException(422, "Format must be xlsx, csv, txt, docx, or pdf")
    wb = build_checklist_workbook(rows, lang)
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="hospital_checklist.xlsx"'})
