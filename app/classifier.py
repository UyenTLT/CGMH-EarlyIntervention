"""Conservative, explainable suggestions for the Chang Gung checklist.

The rules use the checklist and examples in the supplied diagnosis workbook as
terminology guidance. They are not a diagnostic model and never auto-save.
"""
from __future__ import annotations

import re


# value, display label, terminology patterns. Values must match diagnosis-data.js.
RULES = [
    ("diag-01-cp-spastic-diplegia", "Brain: cerebral palsy, spastic diplegia", [r"\bspastic diplegia\b", r"\bcp\s*(?:with|,)?\s*sd\b", r"痙攣性雙癱"]),
    ("diag-01-cp-monoplegia", "Brain: cerebral palsy, monoplegia", [r"\bcp\b.{0,30}\bmonoplegia\b"]),
    ("diag-01-cp-sq", "Brain: cerebral palsy, spastic quadriplegia", [r"\bspastic quadriplegia\b", r"\bcp\b.{0,30}\b(?:sq|quadriplegia)\b"]),
    ("diag-01-cp-sh", "Brain: cerebral palsy, spastic hemiplegia", [r"\bspastic hemiplegia\b", r"\bcp\b.{0,30}\b(?:sh|hemiplegia|hemiparesis)\b"]),
    ("diag-01-cp-athetoid", "Brain: cerebral palsy, athetoid/dyskinetic", [r"\b(?:athetoid|dyskinetic|dystonic)\s+cp\b", r"\bcp\b.{0,30}\b(?:athetoid|dyskinetic|dystonic)\b"]),
    ("diag-01-cp-hypotonic", "Brain: cerebral palsy, hypotonic", [r"\bhypotonic cp\b", r"\bcp\b.{0,30}\bhypotonic\b"]),
    ("diag-01-cp-other", "Brain: cerebral palsy, other type", [r"\b(?:ataxic|mixed|triplegic)\s+cp\b", r"\bcp\b.{0,30}\b(?:ataxic|triplegia)\b"]),
    ("diag-01-brain-other", "Brain: other brain lesion", [r"\b(?:periventricular leukomalacia|pvl|periventricular flaring|subdural ha?emorrhage|subdural hematoma|subependymal cyst|brain atrophy|encephalopathy)\b"]),
    ("diag-01-hypoxic-encephalopathy", "Brain: hypoxic encephalopathy", [r"\b(?:hypoxic|hypoxic[- ]ischemic) encephalopathy\b", r"\bhie\b"]),
    ("diag-01-epilepsy", "Brain: epilepsy/seizure", [r"\b(?:epilepsy|epileptic|seizures?|status epilepticus)\b", r"癲癇|痙攣發作"]),
    ("diag-01-brain-infection", "Brain: CNS infection", [r"\b(?:encephalitis|meningitis|meningoencephalitis|cerebellitis|brain abscess)\b"]),
    ("diag-01-brain-anomaly", "Brain: structural anomaly", [r"\b(?:microcephaly|macrocephaly|schizencephaly|lissencephaly|cerebral dysgenesis)\b"]),
    ("diag-01-tbi", "Brain: traumatic brain injury", [r"\b(?:traumatic brain injury|brain contusion|intracranial injury)\b"]),
    ("diag-01-brain-tumor", "Brain: brain tumor", [r"\bbrain tumou?r\b"]),
    ("diag-01-brain-vascular", "Brain: vascular lesion/hemorrhage", [r"\b(?:intraventricular hemorrhage|ivh|intracranial hemorrhage|cerebral infarct|brain infarction|avm|moyamoya)\b"]),
    ("diag-01-hydrocephalus", "Brain: hydrocephalus", [r"\bhydrocephal(?:us|y)\b"]),
    ("diag-01-premature", "Brain: prematurity", [r"\b(?:preterm|premature infant|prematurity|born at \d{1,2}\s*(?:\+\s*\d+\s*)?weeks? gestation)\b", r"早產"]),
    ("diag-01-craniosynostosis", "Brain: craniosynostosis", [r"\bcraniosynostosis\b"]),
    ("diag-02-intellectual-disability", "Psychosocial: intellectual disability", [r"\b(?:intellectual disability|mental retardation|\bmr\b)\b", r"智能障礙"]),
    ("diag-02-psychosocial-other", "Psychosocial: other (borderline IQ/cognitive delay)", [r"\b(?:borderline\s+(?:iq|intelligence)|cognitive delay)\b"]),
    ("diag-02-speech-delay", "Psychosocial: speech/language delay", [r"\b(?:developmental language disorder|\bdld\b|speech delay|language delay|expressive language|mixed language)\b", r"語言發展遲緩"]),
    ("diag-02-articulation", "Psychosocial: articulation disorder", [r"\b(?:articulation disorder|speech sound disorder)\b"]),
    ("diag-02-stuttering", "Psychosocial: stuttering", [r"\bstutter(?:ing)?\b"]),
    ("diag-02-sensory-integration", "Psychosocial: sensory integration dysfunction", [r"\b(?:sensory integration dysfunction|si dysfunction)\b"]),
    ("diag-02-adhd-si", "Psychosocial: ADHD/ADD", [r"\b(?:adhd|add|attention[- ]deficit(?: hyperactivity)? disorder)\b"]),
    ("diag-02-behavior", "Psychosocial: behavior disorder", [r"\bbehavior(?:al)? disorder\b"]),
    ("diag-02-autism", "Psychosocial: autism spectrum", [r"\b(?:autism|autistic|asperger(?:'s)?|pdd|asd)\b", r"自閉症"]),
    ("diag-02-coordination", "Psychosocial: coordination disorder", [r"\b(?:developmental coordination disorder|\bdcd\b|coordination disorder)\b"]),
    ("diag-02-emotional", "Psychosocial: emotional disorder", [r"\bemotional disorder\b"]),
    ("diag-02-learning-disability", "Psychosocial: learning disability", [r"\b(?:learning disability|learning disorder)\b"]),
    ("diag-02-tic", "Psychosocial: tic disorder", [r"\btic disorder\b"]),
    ("diag-03-sma-i", "Spinal cord: SMA type I", [r"\b(?:spinal muscular atrophy|sma)\s*(?:type\s*)?(?:i|1)\b"]),
    ("diag-03-sma-ii", "Spinal cord: SMA type II", [r"\b(?:spinal muscular atrophy|sma)\s*(?:type\s*)?(?:ii|2)\b"]),
    ("diag-03-sma-iii", "Spinal cord: SMA type III", [r"\b(?:spinal muscular atrophy|sma)\s*(?:type\s*)?(?:iii|3)\b"]),
    ("diag-03-sma-unspecified", "Spinal cord: SMA type not specified", [r"\bspinal muscular atrophy\b", r"\bsma\b"]),
    ("diag-03-polio", "Spinal cord: poliomyelitis", [r"\b(?:poliomyelitis|polio)\b"]),
    ("diag-03-sci", "Spinal cord: spinal cord injury", [r"\bspinal cord injury\b"]),
    ("diag-03-spinal-tumor", "Spinal cord: tumor", [r"\bspinal cord tumou?r\b"]),
    ("diag-03-spinal-anomaly", "Spinal cord: anomaly", [r"\b(?:myelodysplasia|spina bifida|meningomyelocele|tethered cord|syringomyelia)\b"]),
    ("diag-04-infectious-polyneuropathy", "Roots/nerves: infectious polyneuropathy", [r"\b(?:guillain[- ]barre|\bgbs\b|cidp)\b"]),
    ("diag-04-hereditary-neuropathy", "Roots/nerves: hereditary neuropathy", [r"\b(?:charcot[- ]marie[- ]tooth|\bcmt\b|hereditary polyneuropathy)\b"]),
    ("diag-04-traumatic-neuritis", "Roots/nerves: traumatic nerve injury", [r"\b(?:traumatic neuritis|peripheral nerve injury)\b"]),
    ("diag-04-bpi", "Roots/nerves: brachial plexus injury", [r"\b(?:brachial plexus injury|\bbpi\b|erb.?s palsy)\b"]),
    ("diag-05-myasthenia", "Neuromuscular junction: myasthenia gravis", [r"\bmyasthenia gravis\b"]),
    ("diag-05-botulism", "Neuromuscular junction: botulism", [r"\bbotulism\b"]),
    ("diag-06-duchenne", "Muscle disease: Duchenne muscular dystrophy", [r"\b(?:duchenne|\bdmd\b)\b"]),
    ("diag-06-becker", "Muscle disease: Becker muscular dystrophy", [r"\bbecker muscular dystrophy\b"]),
    ("diag-06-fshd", "Muscle disease: facioscapulohumeral dystrophy", [r"\b(?:facioscapulohumeral|\bfshd\b)\b"]),
    ("diag-06-myotonic", "Muscle disease: myotonic dystrophy", [r"\bmyotonic dystrophy\b"]),
    ("diag-07-nemaline", "Congenital myopathy: nemaline", [r"\bnemaline myopathy\b"]),
    ("diag-07-central-core", "Congenital myopathy: central core", [r"\bcentral core disease\b"]),
    ("diag-08-glycogenesis", "Metabolic myopathy: glycogen storage", [r"\b(?:pompe disease|glycogen storage disease|glycogenosis)\b"]),
    ("diag-09-down", "Chromosome/syndrome: Down syndrome", [r"\bdown(?:'s)? syndrome\b", r"唐氏症"]),
    ("diag-09-prader-willi", "Chromosome/syndrome: Prader-Willi", [r"\bprader[- ]willi\b"]),
    ("diag-09-fragile-x", "Chromosome/syndrome: Fragile X", [r"\bfragile\s*x\b"]),
    ("diag-09-rett", "Chromosome/syndrome: Rett syndrome", [r"\brett syndrome\b"]),
    ("diag-09-angelman", "Chromosome/syndrome: Angelman syndrome", [r"\bangelman syndrome\b"]),
    ("diag-09-turner", "Chromosome/syndrome: Turner syndrome", [r"\bturner syndrome\b"]),
    ("diag-09-williams", "Chromosome/syndrome: Williams syndrome", [r"\bwilliams syndrome\b"]),
    ("diag-09-chromosome-other", "Chromosome/syndrome: other named syndrome", [r"\b(?:microdeletion|de lange|goldenhar|fetal alcohol|achondroplasia|crouzon|catch 22|22q11|digeorge|noonan|cri[- ]du[- ]chat|leigh disease|noonan|gene mutation|chromosom\w+ abnormality)\b"]),
    ("diag-10-hypothyroidism", "Endocrine/metabolism: hypothyroidism", [r"\bhypothyroidism\b"]),
    ("diag-10-mineral-deficit", "Endocrine/metabolism: mineral deficiency", [r"\b(?:zinc|zn|copper|cu) deficiency\b", r"\bmineral deficit\b"]),
    ("diag-10-hypoparathyroidism", "Endocrine/metabolism: hypoparathyroidism", [r"\bhypoparathyroidism\b"]),
    ("diag-11-mitochondrial-disease", "Mitochondrial disease", [r"\bmitochondrial disease\b"]),
    ("diag-12-neurofibromatosis", "Neurocutaneous: neurofibromatosis", [r"\bneurofibromatosis\b"]),
    ("diag-12-tuberous-sclerosis", "Neurocutaneous: tuberous sclerosis", [r"\btuberous sclerosis\b"]),
    ("diag-12-ito-hypomelanosis", "Neurocutaneous: hypomelanosis of Ito", [r"\bhypomelanosis of ito\b"]),
    ("diag-13-refraction", "Vision: refractive error", [r"\b(?:hyperopia|hypermetropia|myopia|astigmatism|refractive error)\b"]),
    ("diag-13-amblyopia", "Vision: amblyopia", [r"\bamblyopia\b"]),
    ("diag-13-strabismus", "Vision: strabismus", [r"\b(?:strabismus|strabismic|esotropia|exotropia)\b"]),
    ("diag-13-visual-impairment", "Vision: visual impairment", [r"\bvisual impairment\b"]),
    ("diag-13-cortical-blindness", "Vision: cortical blindness", [r"\b(?:cortical blindness|cortical visual impairment)\b"]),
    ("diag-13-nystagmus", "Vision: nystagmus", [r"\bnystagmus\b"]),
    ("diag-14-conductive-loss", "Auditory: conductive hearing loss", [r"\bconductive (?:hearing )?loss\b"]),
    ("diag-14-sensorineural-loss", "Auditory: sensorineural hearing loss", [r"\bsensorineural (?:hearing )?loss\b"]),
    ("diag-14-mixed-loss", "Auditory: mixed hearing loss", [r"\bmixed hearing loss\b"]),
    ("diag-14-capd", "Auditory: central auditory processing disorder", [r"\b(?:central auditory processing disorder|\bcapd\b)\b"]),
    ("diag-14-deafness", "Auditory: deafness", [r"\bdeaf(?:ness)?\b"]),
    ("diag-14-auditory-neuropathy", "Auditory: auditory neuropathy", [r"\bauditory neuropathy\b"]),
    ("diag-15-global-delay", "Unspecified delay: global developmental delay", [r"\b(?:global developmental delay|global delay|global dd|global developmental disorder)\b", r"全面性發展遲緩"]),
    ("diag-15-motor-delay", "Unspecified delay: motor delay", [r"\b(?:motor delay|motor developmental delay|motor dd)\b", r"動作發展遲緩"]),
    ("diag-15-delay-other", "Unspecified delay: developmental delay, subtype unclear", [r"\b(?:developmental delay|developmental disorder|\bdd\b)\b", r"發展遲緩"]),
    ("diag-99-digestive", "Other: digestive/GI condition", [r"\b(?:feeding intolerance|feeding difficulty|gastroesophageal reflux|\bgerd\b|dysphagia|constipation|hernia|cholestasis)\b"]),
    ("diag-99-orthopedic", "Other: orthopedic condition", [r"\b(?:scoliosis|torticollis|ddh|hip dysplasia|hip dislocation|contracture|flat foot|club foot|leg length discrepancy)\b"]),
    ("diag-99-cardiovascular", "Other: cardiovascular condition", [r"\b(?:atrial septal defect|\basd\b|ventricular septal defect|\bvsd\b|\bpda\b|patent ductus arteriosus|cardiomyopathy|heart failure|arrhythmia|congenital heart disease|pulmonary hypertension)\b"]),
    ("diag-99-urinary", "Other: urinary/renal condition", [r"\b(?:urinary tract infection|\buti\b|renal disease|urologic|hydronephrosis)\b"]),
    ("diag-99-cleft-lip-palate", "Other: cleft lip/palate", [r"\bcleft lip\b|\bcleft palate\b"]),
    ("diag-99-failure-to-thrive", "Other: failure to thrive", [r"\bfailure to thrive\b|\bftt\b"]),
    ("diag-99-precocious-puberty", "Other: precocious puberty", [r"\bprecocious puberty\b"]),
    ("diag-99-other-other", "Other: neonatal/general condition", [r"\b(?:respiratory distress syndrome|\brds\b|bronchopulmonary dysplasia|\bbpd\b|apnea of prematurity|sepsis|anemia of prematurity|neonatal jaundice|hyperbilirubinemia|small for gestational age|\bsga\b|low birth weight|perinatal asphyxia|g6pd deficiency)\b"]),
]

UNCERTAIN = re.compile(r"\b(?:r\s*/\s*o|rule\s*out|suspect(?:ed)?|possible|probable|presumed|borderline|query)\b|疑似|待排", re.I)
NEGATED = re.compile(r"\b(?:no|not|without|negative for|denies)\b|無|沒有|否認", re.I)
SENTENCE_BREAK = re.compile(r"[;,\n。；.!?]+")

CHECKLIST_CODES = {
    "diag-01-cp-spastic-diplegia": "1.1a", "diag-01-cp-monoplegia": "1.1b",
    "diag-01-cp-sq": "1.1c", "diag-01-cp-sh": "1.1d", "diag-01-cp-athetoid": "1.1e",
    "diag-01-cp-hypotonic": "1.1f", "diag-01-cp-other": "1.1g", "diag-01-brain-other": "1.0",
    "diag-01-hypoxic-encephalopathy": "1.2", "diag-01-epilepsy": "1.3", "diag-01-brain-infection": "1.4",
    "diag-01-brain-anomaly": "1.5", "diag-01-tbi": "1.6", "diag-01-brain-tumor": "1.7",
    "diag-01-brain-vascular": "1.8", "diag-01-hydrocephalus": "1.9a", "diag-01-premature": "1.10",
    "diag-01-craniosynostosis": "1.11", "diag-02-intellectual-disability": "2.2", "diag-02-speech-delay": "2.3a",
    "diag-02-articulation": "2.3b", "diag-02-stuttering": "2.3c", "diag-02-sensory-integration": "2.4a",
    "diag-02-adhd-si": "2.4b", "diag-02-behavior": "2.5", "diag-02-autism": "2.6",
    "diag-02-psychosocial-other": "2.0", "diag-02-coordination": "2.9", "diag-02-emotional": "2.12", "diag-02-learning-disability": "2.21",
    "diag-02-tic": "2.24", "diag-03-sma-unspecified": "3.1", "diag-03-sma-i": "3.1a",
    "diag-03-sma-ii": "3.1b", "diag-03-sma-iii": "3.1c", "diag-03-polio": "3.2",
    "diag-03-sci": "3.3", "diag-03-spinal-tumor": "3.4", "diag-03-spinal-anomaly": "3.6",
    "diag-04-infectious-polyneuropathy": "4.1", "diag-04-hereditary-neuropathy": "4.2",
    "diag-04-traumatic-neuritis": "4.4", "diag-04-bpi": "4.5", "diag-05-myasthenia": "5.1",
    "diag-05-botulism": "5.5", "diag-06-duchenne": "6.1a", "diag-06-becker": "6.1b",
    "diag-06-fshd": "6.2a", "diag-06-myotonic": "6.5", "diag-07-nemaline": "7.3",
    "diag-07-central-core": "7.4", "diag-08-glycogenesis": "8.1", "diag-09-down": "9.1",
    "diag-09-prader-willi": "9.4", "diag-09-fragile-x": "9.10", "diag-09-rett": "9.15",
    "diag-09-angelman": "9.11", "diag-09-turner": "9.7", "diag-09-williams": "9.8",
    "diag-09-chromosome-other": "9.0", "diag-10-hypothyroidism": "10.1", "diag-10-mineral-deficit": "10.2",
    "diag-10-hypoparathyroidism": "10.3", "diag-11-mitochondrial-disease": "11.2",
    "diag-12-neurofibromatosis": "12.1", "diag-12-tuberous-sclerosis": "12.2",
    "diag-12-ito-hypomelanosis": "12.3", "diag-13-refraction": "13.1a", "diag-13-amblyopia": "13.1b",
    "diag-13-strabismus": "13.2a", "diag-13-visual-impairment": "13.4b",
    "diag-13-cortical-blindness": "13.5", "diag-13-nystagmus": "13.6",
    "diag-14-conductive-loss": "14.1a", "diag-14-sensorineural-loss": "14.1b",
    "diag-14-mixed-loss": "14.1c", "diag-14-capd": "14.2", "diag-14-deafness": "14.3",
    "diag-14-auditory-neuropathy": "14.4", "diag-15-global-delay": "15.1",
    "diag-15-motor-delay": "15.2", "diag-15-delay-other": "15.0", "diag-99-digestive": "99.1",
    "diag-99-orthopedic": "99.2", "diag-99-cardiovascular": "99.3", "diag-99-urinary": "99.4",
    "diag-99-cleft-lip-palate": "99.5", "diag-99-failure-to-thrive": "99.6",
    "diag-99-precocious-puberty": "99.7", "diag-99-other-other": "99.0",
}


def _status(text: str, start: int) -> str:
    # Check only the current clause and a short local window to avoid carrying
    # a negation across unrelated diagnoses.
    prefix = text[max(0, start - 100):start]
    clause = SENTENCE_BREAK.split(prefix)[-1]
    marker = list(UNCERTAIN.finditer(clause)) + list(NEGATED.finditer(clause))
    if not marker:
        return "confirmed"
    last = max(marker, key=lambda m: m.end())
    return "uncertain" if UNCERTAIN.fullmatch(last.group()) else "negated"


def classify_text(text: str) -> dict:
    text = text[:50000]
    suggestions: dict[str, dict] = {}
    excluded: dict[tuple[str, str], dict] = {}
    for value, label, patterns in RULES:
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.I):
                status = _status(text, match.start())
                item = {"value": value, "code": CHECKLIST_CODES.get(value, ""), "label": label, "matched": match.group(), "status": status}
                if status == "confirmed":
                    suggestions.setdefault(value, item)
                else:
                    excluded.setdefault((value, status), item)
    # Do not suggest an unspecified delay when a more specific delay was found.
    if "diag-15-delay-other" in suggestions and any(k in suggestions for k in ("diag-15-global-delay", "diag-15-motor-delay")):
        suggestions.pop("diag-15-delay-other", None)
    if any(k in suggestions for k in ("diag-03-sma-i", "diag-03-sma-ii", "diag-03-sma-iii")):
        suggestions.pop("diag-03-sma-unspecified", None)
    # ASD in this data has two common meanings. Retain it only when context
    # clarifies cardiac septal defect vs autism spectrum disorder.
    asd_matches = list(re.finditer(r"\basd\b", text, re.I))
    if asd_matches:
        contexts = " ".join(text[max(0, m.start() - 50):min(len(text), m.end() + 50)] for m in asd_matches)
        if re.search(r"\b(?:atrial septal defect|heart|cardiac|pfo)\b", contexts, re.I):
            suggestions.pop("diag-02-autism", None)
            for status in ("uncertain", "negated"):
                excluded.pop(("diag-02-autism", status), None)
        else:
            # The sample workbook reads bare ASD as autism spectrum disorder;
            # cardiac ASD needs explicit septal/heart context.
            suggestions.pop("diag-99-cardiovascular", None)
            for status in ("uncertain", "negated"):
                excluded.pop(("diag-99-cardiovascular", status), None)
    return {
        "suggestions": sorted(suggestions.values(), key=lambda x: x["value"]),
        "review": sorted(excluded.values(), key=lambda x: (x["status"], x["value"])),
        "notice": "Keyword suggestions only. Confirm each item against the source record and the checklist before saving.",
    }
