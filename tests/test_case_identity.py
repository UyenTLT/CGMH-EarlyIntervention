import asyncio
import io
import unittest
from unittest.mock import patch

from docx import Document
from pypdf import PdfReader
from app import main


class CaseIdentityTests(unittest.TestCase):
    def legacy(self):
        return dict(id='legacy-1', caseId='CASE-001', patientName='REMOVED-NAME', chartNo='REMOVED-CHART', examDate='2099-12-31', physician='REMOVED-DOCTOR', importedAt='2026-01-01T12:00:00', diagnoses=[], functional=[], management=[])

    def test_edit_preserves_omitted_legacy_fields(self):
        record = self.legacy()
        with patch.object(main, 'read_records', return_value=[record]), patch.object(main, 'write_records') as write:
            result = main.save_record(main.Record(id='legacy-1', caseId='CASE-001', diagnosisNotes='Updated'))
        for key in ['patientName', 'chartNo', 'examDate', 'physician', 'importedAt']:
            self.assertEqual(result[key], record[key])
        self.assertEqual(write.call_args.args[0][0]['diagnosisNotes'], 'Updated')

    def test_extraction_only_returns_case_id(self):
        for label in ['Case ID', '個案編號']:
            self.assertEqual(main.extract_basic_fields(f'{label}: CASE-123\nPatient Name: Example\nChart No: X\nExam Date: 2026-01-01\nPhysician: Example'), {'caseId':'CASE-123'})
        self.assertEqual(main.extract_basic_fields('Patient Name: Example'), {})

    def test_new_import_ignores_removed_structured_columns(self):
        from fastapi import UploadFile
        raw = b'CASE ID,Patient Name,Chart No,Exam Date,Physician,Diagnosis\nC-123,REMOVED-NAME,REMOVED-CHART,2099-12-31,REMOVED-DOCTOR,Autism\n'
        with patch.object(main, 'read_records', return_value=[]):
            result = asyncio.run(main.import_cases(UploadFile(filename='cases.csv', file=io.BytesIO(raw))))
        row = result['records'][0]
        self.assertTrue(row['caseId'].endswith('C-123'))
        for key in ['patientName', 'chartNo', 'examDate', 'physician']:
            self.assertNotIn(key, row)
        self.assertNotIn('REMOVED-', row['sourceText'])

    def test_word_and_pdf_only_use_case_identity(self):
        async def read_body(response):
            return b''.join([chunk async for chunk in response.body_iterator])
        for fmt in ['docx', 'pdf']:
            with self.subTest(format=fmt), patch.object(main, 'selected_records', return_value=[self.legacy()]):
                response = main.export(format=fmt, ids=[], lang='en')
                raw = asyncio.run(read_body(response))
                if fmt == 'docx':
                    document = Document(io.BytesIO(raw))
                    text = '\n'.join([p.text for p in document.paragraphs] + [cell.text for table in document.tables for row in table.rows for cell in row.cells])
                else:
                    text = '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(raw)).pages)
                self.assertIn('CASE-001', text)
                for removed in ['REMOVED-NAME', 'REMOVED-CHART', '2099-12-31', 'REMOVED-DOCTOR', 'Patient Name', 'Chart No', 'Exam Date', 'Physician']:
                    self.assertNotIn(removed, text)
