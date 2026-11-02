import io
import unittest
from openpyxl import load_workbook
from app.main import build_checklist_workbook


class ChecklistWorkbookTests(unittest.TestCase):
    def record(self, **changes):
        return dict(id='record-1', caseId='CASE-001', patientName='測試個案', chartNo='CH001', examDate='2026-11-02', physician='Dr Example', functional=['Language: expressive', 'Motor: delay'], diagnoses=['diag-01-cp-spastic-diplegia', 'diag-02-autism'], diagnosisLabels=['Brain: CP — Spastic diplegia', 'Psychosocial disorder: Autism'], management=['Rehabilitation: PT'], medication='Review notes', diagnosisNotes='Clinician reviewed', **changes)

    def roundtrip(self, rows):
        stream = io.BytesIO()
        build_checklist_workbook(rows).save(stream)
        stream.seek(0)
        return load_workbook(stream)

    def test_readable_overview_and_clinical_details(self):
        wb = self.roundtrip([self.record()])
        self.assertEqual(wb.sheetnames, ['Case overview', 'Checklist details', 'Diagnosis matrix'])
        overview = wb['Case overview']
        self.assertEqual(overview.max_column, 7)
        self.assertEqual(overview['A2'].value, 'CASE-001')
        self.assertEqual(overview['B2'].value, '測試個案')
        self.assertEqual(overview['G2'].hyperlink.target, "#'Checklist details'!A4")
        self.assertIn('Cases', overview.tables)
        details = wb['Checklist details']
        self.assertEqual(details['B7'].value, 'Language: expressive\nMotor: delay')
        self.assertEqual(details['B8'].value, 'Brain: CP — Spastic diplegia\nPsychosocial disorder: Autism')
        self.assertEqual(details['B9'].value, 'Clinician reviewed')
        self.assertEqual(details['B10'].value, 'Rehabilitation: PT')
        self.assertEqual(details['B11'].value, 'Review notes')
        self.assertEqual(details['B12'].value, 'record-1')
        self.assertTrue(details['B8'].alignment.wrap_text)
        self.assertEqual(list(wb['Diagnosis matrix'].values)[1][3:6], (1, 1, 0))

    def test_each_case_links_to_its_own_checklist(self):
        first = self.record()
        second = dict(first, id='record-2', caseId='CASE-002', patientName='Second patient')
        wb = self.roundtrip([first, second])
        self.assertEqual(wb['Case overview']['G3'].hyperlink.target, "#'Checklist details'!A15")
        self.assertIn('Second patient', wb['Checklist details']['A15'].value)

    def test_user_text_is_never_an_excel_formula(self):
        record = dict(self.record(), patientName='=1+1', diagnosisNotes='=HYPERLINK("https://example.com")')
        wb = self.roundtrip([record])
        for ws in wb:
            for row in ws:
                for cell in row:
                    self.assertNotEqual(cell.data_type, 'f')
        self.assertEqual(wb['Case overview']['B2'].value, '=1+1')

    def test_empty_export_is_a_valid_workbook(self):
        wb = self.roundtrip([])
        self.assertEqual(wb['Case overview'].max_row, 1)
        self.assertEqual(len(wb['Case overview'].tables), 0)
        self.assertIn('No saved', wb['Checklist details']['A4'].value)


if __name__ == '__main__':
    unittest.main()
