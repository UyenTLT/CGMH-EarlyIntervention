"""Extract explicit clinical columns into an unsaved, traceable import preview."""
from __future__ import annotations
import json
import re
import secrets
from datetime import datetime
from pathlib import Path
from app.classifier import classify_text

LABELS = json.loads((Path(__file__).parent / 'export_labels.json').read_text())
ALIASES = {
    'caseId': ['case id', 'case no', 'case number', 'caseid', 'case', 'id', '個案id', '個案編號', '個案號碼'],
    'diagnosisNotes': ['diagnosis', 'diagnoses', 'diagnostic items', 'diagnosis text', 'diagnosis notes', 'diagnosis summary', 'clinical diagnosis', '診斷', '診斷內容', '診斷補充說明', '診斷項目'],
    'functional': ['functional classifications', 'functional classification', 'functional diagnostic classification', '功能性診斷分類', '功能分類'],
    'management': ['management', 'treatment', 'treatment plan', 'rehabilitation', 'rehabilitation programs', 'management interventions', '處置', '處置計畫', '處置與介入', '復健計畫'],
    'medication': ['medication', 'medication notes', 'medications', 'medicine', '藥物', '藥物備註'],
}

def normalized(value):
    return re.sub(r'[^a-z0-9\u4e00-\u9fff]+', ' ', str(value or '').casefold()).strip()


def canonical_items(text, group):
    prefix = ('Laboratory:', 'Rehabilitation:') if group == 'management' else ('Overall ', 'Language:', 'Motor:', 'Social ', 'Cognitive ', 'Specific ')
    values = {normalized(key): key for key in LABELS['values'] if key.startswith(prefix)}
    values.update({normalized(zh): key for key, zh in LABELS['values'].items() if key.startswith(prefix)})
    if group == 'management':
        values.update({key: 'Rehabilitation: '+key.upper() for key in ['pt', 'ot', 'st']})
    selected, notes = [], []
    for part in re.split(r'[\n;；|]+', text):
        part = part.strip()
        if not part:
            continue
        value = values.get(normalized(part))
        if value and value not in selected:
            selected.append(value)
        elif not value:
            notes.append(part)
    return selected, '\n'.join(notes)


def preview_import(datasets, existing, filename, mapping=None):
    known = {str(row.get('caseId') or '').strip().casefold() for row in existing}
    seen, records, found, ignored = set(), [], False, []
    aliases = {key: {normalized(value) for value in values} for key, values in ALIASES.items()}
    for sheet, table in datasets:
        if mapping and sheet != mapping.get('sheet'):
            continue
        header_index, columns = None, None
        if mapping:
            header_index = mapping.get('headerRow', 1) - 1
            selected = mapping.get('columns', {})
            if not isinstance(header_index, int) or header_index < 0 or header_index >= len(table) or not isinstance(selected.get('caseId'), int):
                raise ValueError('Invalid column mapping')
            width = len(table[header_index])
            if any(not isinstance(col, int) or isinstance(col, bool) or col < 0 or col >= width for col in selected.values()):
                raise ValueError('Invalid column mapping')
            columns = {key: [selected[key]] if key in selected else [] for key in aliases}

        for index, row in enumerate(table[:30]) if not mapping else []:
            detected = {key: [i for i, cell in enumerate(row) if any(normalized(line) in names for line in str(cell or '').splitlines())] for key, names in aliases.items()}
            if detected['caseId']:
                header_index, columns = index, detected
                break
        if header_index is None:
            ignored.append(sheet)
            continue
        found = True
        for source_row, values in enumerate(table[header_index + 1:], header_index + 2):
            if not any(value is not None and str(value).strip() for value in values):
                continue
            def cell_text(key):
                parts = []
                for col in columns[key]:
                    if col >= len(values) or values[col] is None:
                        continue
                    value = values[col]
                    value = str(int(value)) if isinstance(value, float) and value.is_integer() else str(value).strip()
                    if value and value not in parts:
                        parts.append(value)
                return '\n'.join(parts)
            raw_case = cell_text('caseId')
            if normalized(raw_case) in aliases['caseId']:
                continue
            clinical = {key: cell_text(key) for key in ['diagnosisNotes', 'functional', 'management', 'medication']}
            # Unknown columns and removed identity fields are never diagnosis input.
            if not raw_case and not any(clinical.values()):
                continue
            ids = [value.strip() for value in re.split(r'[\r\n,，;；|]+', raw_case) if value.strip()] or ['']
            result = classify_text(clinical['diagnosisNotes']) if clinical['diagnosisNotes'] else {'suggestions': [], 'review': []}
            functional, functional_notes = canonical_items(clinical['functional'], 'functional')
            management, management_notes = canonical_items(clinical['management'], 'management')
            for case_id in ids:
                key = case_id.strip().casefold()
                legacy_id = f'{sheet}-{case_id}'
                issues = []
                if not key:
                    issues.append('missing_case_id')
                elif key in known or legacy_id.casefold() in known:
                    issues.append('existing_case_id')
                elif key in seen:
                    issues.append('duplicate_in_file')
                if not any(clinical.values()):
                    issues.append('no_clinical_data')
                if result.get('review'):
                    issues.append('uncertain_diagnosis')
                if clinical['diagnosisNotes'] and not result['suggestions']:
                    issues.append('no_diagnosis_match')
                if functional_notes or management_notes:
                    issues.append('unmapped_clinical_text')
                seen.add(key)
                records.append({
                    'id': secrets.token_hex(8), 'caseId': case_id,
                    'functional': functional, 'functionalNotes': functional_notes,
                    'management': management, 'managementNotes': management_notes,
                    'diagnosisNotes': clinical['diagnosisNotes'], 'medication': clinical['medication'],
                    'diagnoses': [item['value'] for item in result['suggestions']],
                    'diagnosisLabels': [item['label'] for item in result['suggestions']],
                    'classificationReview': result.get('review', []), 'classificationStatus': 'suggested' if result['suggestions'] else 'review',
                    'sourceText': '\n'.join([f'Case ID: {case_id}'] + [f'{field}: {value}' for field, value in clinical.items() if value]),
                    'importSource': {'file': filename, 'sheet': sheet, 'row': source_row},
                    'importMeta': {'issues': issues, 'legacyCaseId': legacy_id, 'originalCaseId': case_id},
                    'importedAt': datetime.now().isoformat(timespec='seconds'),
                })
    if not found:
        raise ValueError('No table with a CASE ID column was found')
    return {'records': records, 'imported': len(records), 'skipped': 0,
            'suggested': sum(bool(row['diagnoses']) for row in records),
            'needsReview': len(records), 'ignoredSheets': ignored,
            'duplicates': sum(any(issue in row['importMeta']['issues'] for issue in ['existing_case_id', 'duplicate_in_file']) for row in records)}
