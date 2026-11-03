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
