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
        self.assertEqual(overview.max_column, 3)
        self.assertEqual(overview['A2'].value, 'CASE-001')
        self.assertIn('Brain', overview['B2'].value)
        self.assertEqual(overview['C2'].hyperlink.target, "#'Checklist details'!A4")
        self.assertIn('Cases', overview.tables)
        details = wb['Checklist details']
        self.assertEqual(details['B6'].value, 'Language: expressive\nMotor: delay')
        self.assertEqual(details['B7'].value, 'Brain: CP — Spastic diplegia\nPsychosocial disorder: Autism')
        self.assertEqual(details['B8'].value, 'Clinician reviewed')
        self.assertEqual(details['B9'].value, 'Rehabilitation: PT')
        self.assertEqual(details['B10'].value, 'Review notes')
        self.assertEqual(details['B11'].value, 'record-1')
        self.assertTrue(details['B7'].alignment.wrap_text)
        matrix = wb['Diagnosis matrix']
        self.assertEqual(list(matrix.values)[1][2:5], ('CP — Spastic diplegia', 'Autism / PDD / Asperger syndrome', None))
        self.assertEqual(matrix['A2'].hyperlink.target, "#'Checklist details'!A4")
        self.assertEqual(matrix.freeze_panes, 'C2')
        self.assertFalse(matrix.column_dimensions['C'].hidden)
        self.assertTrue(matrix.column_dimensions['E'].hidden)
        self.assertNotIn('Record ID', [cell.value for cell in matrix[1]])

    def test_matrix_preserves_multiple_diagnoses_and_unclassified_cases(self):
        records = [dict(self.record(), diagnoses=['diag-02-speech-delay', 'diag-02-autism', 'diag-02-speech-delay'], diagnosisLabels=['stale labels']),
                   dict(self.record(), id='second', caseId='CASE-002', diagnoses=[], diagnosisLabels=[], diagnosisNotes='Speech delay mentioned in source only')]
        matrix = self.roundtrip(records)['Diagnosis matrix']
        self.assertIsNone(matrix['C2'].value)
        self.assertEqual(matrix['D2'].value.splitlines(), ['Speech delay', 'Autism / PDD / Asperger syndrome'])
        self.assertEqual(matrix['B3'].value, 'No checklist diagnosis selected')
        self.assertTrue(all(cell.value is None for cell in matrix[3][2:]))
        self.assertGreaterEqual(matrix.row_dimensions[2].height, 44)
        self.assertIn('not that disease is excluded', matrix['A1'].comment.text)

    def test_matrix_supports_legacy_labels_without_guessing_unknown_items(self):
        record = dict(self.record(), diagnoses=[], diagnosisLabels=['Psychosocial disorder: Speech delay', 'Unrecognized custom label'])
        matrix = self.roundtrip([record])['Diagnosis matrix']
        self.assertEqual(matrix['D2'].value, 'Speech delay')
        self.assertEqual(matrix['S2'].value, 'Unrecognized custom label')
        self.assertEqual(matrix['B2'].value, 'Check unmapped items')
        self.assertFalse(matrix.column_dimensions['S'].hidden)

    def test_matrix_column_order_is_stable_across_different_export_sets(self):
        first = dict(self.record(), diagnoses=['diag-02-speech-delay'])
        second = dict(self.record(), diagnoses=['diag-01-epilepsy'])
        for record in [first, second]:
            matrix = self.roundtrip([record])['Diagnosis matrix']
            self.assertEqual(matrix['C1'].value, '01 — Brain')
            self.assertEqual(matrix['D1'].value, '02 — Psychosocial disorder')
            self.assertEqual(matrix['R1'].value, '99 — Others')
        matrix = self.roundtrip([second])['Diagnosis matrix']
        self.assertFalse(matrix.column_dimensions['C'].hidden)
        self.assertTrue(matrix.column_dimensions['D'].hidden)
        self.assertTrue(matrix.column_dimensions['S'].hidden)

    def test_each_case_links_to_its_own_checklist(self):
        first = self.record()
        second = dict(first, id='record-2', caseId='CASE-002', patientName='Second patient')
        wb = self.roundtrip([first, second])
        self.assertEqual(wb['Case overview']['C3'].hyperlink.target, "#'Checklist details'!A14")
        self.assertIn('CASE-002', wb['Checklist details']['A14'].value)

    def test_user_text_is_never_an_excel_formula(self):
        record = dict(self.record(), caseId='=1+1', diagnosisNotes='=HYPERLINK("https://example.com")')
        wb = self.roundtrip([record])
        for ws in wb:
            for row in ws:
                for cell in row:
                    self.assertNotEqual(cell.data_type, 'f')
        self.assertEqual(wb['Case overview']['A2'].value, '=1+1')

    def test_traditional_chinese_export_preserves_free_text(self):
        record = dict(self.record(), diagnosisNotes='自由備註 / Clinical note')
        stream = io.BytesIO()
        build_checklist_workbook([record], 'zh-TW').save(stream)
        stream.seek(0)
        wb = load_workbook(stream)
        self.assertEqual(wb['Case overview']['A1'].value, 'CASE ID')
        self.assertIn('診斷分類', wb['Case overview']['B1'].value)
        self.assertIn('Diagnosis Groups', wb['Case overview']['B1'].value)
        self.assertIn('腦部', wb['Case overview']['B2'].value)
        self.assertIn('語言：表達', wb['Checklist details']['B6'].value)
        self.assertIn('腦性麻痺', wb['Checklist details']['B7'].value)
        self.assertEqual(wb['Checklist details']['B8'].value, '自由備註 / Clinical note')
        self.assertGreaterEqual(wb['Checklist details'].row_dimensions[7].height, 52)
        matrix = wb['Diagnosis matrix']
        self.assertTrue(matrix.conditional_formatting)
        self.assertEqual(matrix['C2'].value, '腦性麻痺－痙攣性雙癱')
        self.assertIn('自閉症', matrix['D2'].value)
        self.assertIn('心理社會障礙', matrix['D1'].value)
        self.assertIn('Psychosocial disorder', matrix['D1'].value)

    def test_long_notes_continue_without_losing_text(self):
        note = '第一行 clinical note\n' * 100
        record = dict(self.record(), diagnosisNotes=note)
        wb = self.roundtrip([record])
        details = wb['Checklist details']
        pieces = [details.cell(row, 2).value or '' for row in range(1, details.max_row + 1)
                  if str(details.cell(row, 1).value or '').startswith('Diagnosis notes')]
        self.assertGreater(len(pieces), 1)
        self.assertEqual(''.join(pieces), note)
        self.assertTrue(all((dim.height or 0) <= 400 for dim in details.row_dimensions.values()))

    def test_removed_identity_fields_are_absent_from_every_sheet(self):
        record = dict(self.record(), patientName='REMOVED-NAME', chartNo='REMOVED-CHART', examDate='2099-12-31', physician='REMOVED-DOCTOR')
        wb = self.roundtrip([record])
        for ws in wb:
            for row in ws:
                for cell in row:
                    text = str(cell.value or '')
                    for removed in ['REMOVED-NAME', 'REMOVED-CHART', '2099-12-31', 'REMOVED-DOCTOR', 'Patient Name', 'Chart No', 'Exam Date', 'Physician']:
                        self.assertNotIn(removed, text)

    def test_empty_export_is_a_valid_workbook(self):
        wb = self.roundtrip([])
        self.assertEqual(wb['Case overview'].max_row, 1)
        self.assertEqual(len(wb['Case overview'].tables), 0)
        self.assertIn('No saved', wb['Checklist details']['A4'].value)


if __name__ == '__main__':
    unittest.main()
