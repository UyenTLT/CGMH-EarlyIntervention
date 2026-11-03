import unittest
from app.importing import preview_import

class ImportReviewTests(unittest.TestCase):
    def test_only_explicit_fields_are_extracted(self):
        result=preview_import([('Sheet', [('CASE ID','Diagnosis','Functional Classifications','Treatment Plan','Medication','Other','Patient Name'),('001','Autism','Language: expressive','PT; custom treatment','note','Epilepsy','Private')])],[],'input.csv')
        row=result['records'][0]
        self.assertEqual(row['caseId'],'001')
        self.assertEqual(row['functional'],['Language: expressive'])
        self.assertEqual(row['management'],['Rehabilitation: PT'])
        self.assertEqual(row['managementNotes'],'custom treatment')
        self.assertEqual(row['medication'],'note')
        self.assertNotIn('Epilepsy',row['sourceText'])
        self.assertNotIn('Private',row['sourceText'])
        self.assertEqual(row['importSource']['row'],2)

    def test_duplicates_and_missing_ids_remain_visible_in_preview(self):
        result=preview_import([('S',[('Case ID','Diagnosis'),('A','Autism'),('A','Epilepsy'),('', 'Speech delay'),('OLD','Autism')])],[{'caseId':'S-OLD'}],'in.xlsx')
        self.assertEqual(len(result['records']),4)
        self.assertIn('duplicate_in_file',result['records'][1]['importMeta']['issues'])
        self.assertIn('missing_case_id',result['records'][2]['importMeta']['issues'])
        self.assertIn('existing_case_id',result['records'][3]['importMeta']['issues'])

    def test_title_rows_multiple_ids_chinese_headers(self):
        result=preview_import([('S',[('Title',),('個案編號','診斷','處置','藥物'),('A;B','Autism','ST','藥物備註')])],[],'in.xlsx')
        self.assertEqual([r['caseId'] for r in result['records']],['A','B'])
        self.assertEqual(result['records'][0]['management'],['Rehabilitation: ST'])
        self.assertEqual(result['records'][0]['importSource']['row'],3)

    def test_unrelated_columns_are_not_classified_as_diagnosis(self):
        row=preview_import([('S',[('CASE ID','Random'),('C','Epilepsy')])],[],'in.csv')['records'][0]
        self.assertEqual(row['diagnoses'],[])
        self.assertEqual(row['diagnosisNotes'],'')
        self.assertIn('no_clinical_data',row['importMeta']['issues'])


class ExcelUploadTests(unittest.TestCase):
    def test_xlsx_mapping_and_formatted_case_id(self):
        import asyncio, io, json
        from unittest.mock import patch
        from fastapi import UploadFile
        from openpyxl import Workbook
        from app.main import import_cases
        book=Workbook();sheet=book.active;sheet.title='Source';sheet.append(['Identifier','Condition']);sheet.append([12,'Autism']);sheet['A2'].number_format='0000'
        stream=io.BytesIO();book.save(stream);raw=stream.getvalue()
        with patch('app.main.read_records',return_value=[]):
            first=asyncio.run(import_cases(UploadFile(filename='example.xlsx',file=io.BytesIO(raw))))
            self.assertEqual(first.status_code,422)
            self.assertEqual(json.loads(first.body)['detail']['code'],'column_mapping_required')
            result=asyncio.run(import_cases(UploadFile(filename='example.xlsx',file=io.BytesIO(raw)),mapping=json.dumps({'sheet':'Source','headerRow':1,'columns':{'caseId':0,'diagnosisNotes':1}})))
        self.assertEqual(result['records'][0]['caseId'],'0012')
        self.assertEqual(result['records'][0]['diagnosisNotes'],'Autism')


class DuplicateImportTests(unittest.TestCase):
    def test_identical_rows_removed_but_conflicts_retained(self):
        rows=[('Case ID','Diagnosis'),('A','Autism'),('A','Autism'),('A','Epilepsy')]
        result=preview_import([('S',rows)],[],'file.csv')
        self.assertEqual(result['duplicatesRemoved'],1)
        self.assertEqual(len(result['records']),2)
        self.assertEqual([r['diagnosisNotes'] for r in result['records']],['Autism','Epilepsy'])

    def test_existing_identical_row_is_skipped_without_mutation(self):
        first=preview_import([('S',[('CASE ID','Diagnosis'),('A','Autism')])],[],'file.csv')['records'][0]
        existing=dict(first)
        result=preview_import([('S',[('CASE ID','Diagnosis'),('A','Autism')])],[existing],'file.csv')
        self.assertEqual(result['records'],[])
        self.assertEqual(result['duplicatesRemoved'],1)
        self.assertEqual(existing,first)
