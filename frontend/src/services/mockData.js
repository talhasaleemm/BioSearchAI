const now = new Date().toISOString()

export const mockSessions = [
  {
    id: 1,
    session_name: 'BRAF in Melanoma',
    query_summary: 'What is the role of BRAF in melanoma?',
    created_at: '2024-07-22T08:30:00Z',
  },
  {
    id: 2,
    session_name: 'KRAS Inhibitors Review',
    query_summary: 'List KRAS inhibitors and their indications.',
    created_at: now,
  },
  {
    id: 3,
    session_name: 'Alzheimer Biomarkers',
    query_summary: 'Recent CSF biomarkers for Alzheimer disease.',
    created_at: '2024-07-21T14:15:00Z',
  },
]

export const mockActions = [
  {
    id: 101,
    session_id: 1,
    timestamp: '2024-07-22T08:30:12Z',
    input_query: 'What is the role of BRAF in melanoma?',
    retrieved_evidence: [
      { sentence: 'BRAF mutations are common in melanoma and drive MAPK signaling.', source: 'PMID:12345678' },
      { sentence: 'Vemurafenib targets BRAF V600E in metastatic melanoma.', source: 'PMID:87654321' },
    ],
    extracted_entities: [
      { text: 'BRAF', type: 'gene' },
      { text: 'melanoma', type: 'disease' },
      { text: 'vemurafenib', type: 'drug' },
      { text: 'MAPK', type: 'gene' },
    ],
    generated_answer:
      'BRAF mutations, especially V600E, are key drivers in melanoma. Targeted inhibitors like vemurafenib improve outcomes by suppressing downstream MAPK signaling.',
  },
  {
    id: 102,
    session_id: 1,
    timestamp: '2024-07-22T08:31:45Z',
    input_query: 'What are resistance mechanisms to BRAF inhibitors?',
    retrieved_evidence: [
      { sentence: 'Upregulation of PDGFRβ mediates resistance to BRAF inhibition.', source: 'PMID:11223344' },
    ],
    extracted_entities: [
      { text: 'PDGFRβ', type: 'gene' },
      { text: 'resistance', type: 'disease' },
    ],
    generated_answer:
      'Resistance can emerge through receptor tyrosine kinase upregulation such as PDGFRβ, suggesting combination strategies may be beneficial.',
  },
]
