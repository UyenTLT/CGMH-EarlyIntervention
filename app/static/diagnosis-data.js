// Selectable checklist items. IDs are stable export/storage keys; labels are translated in the browser.
window.diagnosisSchema = [
  {id:"01",en:"Brain",zh:"腦部",items:[
    ["cp-spastic-diplegia","CP — Spastic diplegia","腦性麻痺－痙攣性雙癱"],["cp-monoplegia","CP — Monoplegia","腦性麻痺－單癱"],["cp-sq","CP — SQ","腦性麻痺－SQ"],["cp-sh","CP — SH","腦性麻痺－SH"],["cp-athetoid","CP — Athetoid","腦性麻痺－手足徐動型"],["cp-hypotonic","CP — Hypotonic","腦性麻痺－低張型"],["cp-other","CP — Other","腦性麻痺－其他"],["hypoxic-encephalopathy","Hypoxic encephalopathy","缺氧性腦病變"],["epilepsy","Epilepsy","癲癇"],["brain-infection","Infection","感染"],["brain-anomaly","Anomaly","異常"],["tbi","Traumatic brain injury","創傷性腦損傷"],["brain-tumor","Brain tumor","腦瘤"],["brain-vascular","Vascular","血管性疾病"],["hydrocephalus","Hydrocephalus","水腦症"],["premature","Prematurity","早產"],["craniosynostosis","Craniosynostosis","顱縫早閉"],["brain-other","Other","其他"]]},
  {id:"02",en:"Psychosocial disorder",zh:"心理社會障礙",items:[
    ["psychomotor","Psychomotor disorder","精神動作障礙"],["intellectual-disability","Intellectual disability","智能障礙"],["speech-delay","Speech delay","語言發展遲緩"],["articulation","Articulation disorder","構音障礙"],["stuttering","Stuttering","口吃"],["adhd-si","ADHD / ADD","注意力不足過動症／注意力不足症"],["sensory-integration","Sensory integration dysfunction","感覺統合功能障礙"],["behavior","Behavior disorder","行為障礙"],["autism","Autism / PDD / Asperger syndrome","自閉症／廣泛性發展障礙／亞斯伯格症"],["deafness-psychosocial","Deafness","失聰"],["blindness-psychosocial","Blindness","失明"],["coordination","Coordination disorder","協調障礙"],["emotional","Emotional disorder","情緒障礙"],["learning-disability","Learning disability","學習障礙"],["tic","Tic disorder","抽動障礙"],["psychosocial-other","Other","其他"]]},
  {id:"03",en:"Spinal cord",zh:"脊髓",items:[
    ["sma-unspecified","SMA (type not specified)","脊髓性肌肉萎縮症（型別未註明）"],["sma-i","SMA Type I","脊髓性肌肉萎縮症第一型"],["sma-ii","SMA Type II","脊髓性肌肉萎縮症第二型"],["sma-iii","SMA Type III","脊髓性肌肉萎縮症第三型"],["sma-distal","Distal SMA","遠端型脊髓性肌肉萎縮症"],["polio","Poliomyelitis","小兒麻痺"],["sci","Spinal cord injury","脊髓損傷"],["spinal-tumor","Tumor","腫瘤"],["spinal-vascular","Vascular","血管性疾病"],["spinal-anomaly","Anomaly","異常"],["spinal-infection","Infection","感染"],["spinal-other","Other","其他"]]},
  {id:"04",en:"Roots and nerves",zh:"神經根與神經",items:[
    ["infectious-polyneuropathy","Infectious polyneuropathy","感染性多發性神經病變"],["hereditary-neuropathy","Hereditary","遺傳性神經病變"],["toxic-neuropathy","Toxic","中毒性神經病變"],["traumatic-neuritis","Traumatic neuritis","外傷性神經炎"],["bpi","Brachial plexus injury","臂神經叢損傷"],["nerves-other","Other","其他"]]},
  {id:"05",en:"Neuromuscular junction",zh:"神經肌肉接合處",items:[
    ["myasthenia","Myasthenia gravis","重症肌無力"],["tick-paralysis","Tick paralysis","壁蝨麻痺"],["botulism","Botulism","肉毒桿菌中毒"],["nmj-other","Other","其他"]]},
  {id:"06",en:"Muscle disease",zh:"肌肉疾病",items:[
    ["duchenne","Duchenne muscular dystrophy","裘馨氏肌肉失養症"],["becker","Becker muscular dystrophy","貝克氏肌肉失養症"],["fshd","Facioscapulohumeral dystrophy","臉肩肱型肌肉失養症"],["myotonic","Myotonic dystrophy","肌強直性肌肉失養症"],["muscle-other","Other","其他"]]},
  {id:"07",en:"Congenital myopathies",zh:"先天性肌病變",items:[
    ["type1-hypotrophy","Type 1 hypotrophy","第一型肌纖維萎縮"],["congenital-mitochondrial","Mitochondrial","粒線體型"],["nemaline","Nemaline myopathy","線狀體肌病變"],["central-core","Central core disease","中心核病"],["congenital-other","Other","其他"]]},
  {id:"08",en:"Metabolic myopathies",zh:"代謝性肌病變",items:[
    ["glycogenesis","Glycogenesis","糖原合成異常"],["endocrine-myopathy","Endocrine","內分泌性"],["lipid-myopathy","Lipid","脂質代謝性"],["metabolic-other","Other","其他"]]},
  {id:"09",en:"Chromosome & syndromes",zh:"染色體與症候群",items:[
    ["down","Down syndrome","唐氏症"],["prader-willi","Prader-Willi syndrome","小胖威利症"],["fragile-x","Fragile X syndrome","脆折 X 症候群"],["rett","Rett syndrome","雷特症候群"],["angelman","Angelman syndrome","天使人症候群"],["turner","Turner syndrome","透納氏症候群"],["williams","Williams syndrome","威廉斯症候群"],["chromosome-other","Other","其他"]]},
  {id:"10",en:"Endocrine & metabolism",zh:"內分泌與代謝",items:[
    ["hypothyroidism","Hypothyroidism","甲狀腺功能低下"],["mineral-deficit","Mineral deficit","礦物質缺乏"],["hypoparathyroidism","Hypoparathyroidism","副甲狀腺功能低下"],["endocrine-other","Other","其他"]]},
  {id:"11",en:"Mitochondrial",zh:"粒線體疾病",items:[
    ["mitochondrial-birth-defect","Birth defect","出生缺陷"],["mitochondrial-disease","Mitochondrial disease","粒線體疾病"],["mitochondrial-other","Other","其他"]]},
  {id:"12",en:"Neurocutaneous",zh:"神經皮膚症候群",items:[
    ["neurofibromatosis","Neurofibromatosis","神經纖維瘤症"],["tuberous-sclerosis","Tuberous sclerosis","結節性硬化症"],["ito-hypomelanosis","Hypomelanosis of Ito","伊藤氏色素減退症"],["neurocutaneous-other","Other","其他"]]},
  {id:"13",en:"Vision",zh:"視覺",items:[
    ["refraction","Refraction error","屈光異常"],["amblyopia","Amblyopia","弱視"],["strabismus","Strabismus","斜視"],["visual-impairment","Visual impairment","視覺障礙"],["cortical-blindness","Cortical blindness","皮質盲"],["nystagmus","Nystagmus","眼球震顫"],["vision-other","Other","其他"]]},
  {id:"14",en:"Auditory",zh:"聽覺",items:[
    ["conductive-loss","Conductive hearing loss","傳導性聽力損失"],["sensorineural-loss","Sensorineural hearing loss","感音神經性聽力損失"],["mixed-loss","Mixed hearing loss","混合性聽力損失"],["capd","Central auditory processing disorder","中樞聽覺處理障礙"],["deafness","Deafness","失聰"],["auditory-neuropathy","Auditory neuropathy","聽神經病變"],["auditory-other","Other","其他"]]},
  {id:"15",en:"Unspecified delay",zh:"未特定發展遲緩",items:[
    ["global-delay","Global developmental delay","全面性發展遲緩"],["motor-delay","Motor delay","動作發展遲緩"],["delay-other","Other","其他"]]},
  {id:"99",en:"Others",zh:"其他",items:[
    ["digestive","Digestive","消化系統"],["orthopedic","Orthopedic","骨科"],["cardiovascular","Cardiovascular","心血管"],["urinary","Urinary","泌尿系統"],["cleft-lip-palate","Cleft lip / palate","唇顎裂"],["failure-to-thrive","Failure to thrive","生長遲滯"],["precocious-puberty","Precocious puberty","性早熟"],["other-other","Other","其他"]]}
];
