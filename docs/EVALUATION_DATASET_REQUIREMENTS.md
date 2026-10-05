# Evaluation Dataset Requirements

The canonical migrated dataset is `evaluation/datasets/rag_test_dataset.json` with 250 records. It is structurally valid; retrieval IDs still require validation after ingestion, and OCR/audio references are not yet human-certified.

## Current schema

The loader at `evaluation/datasets/schema.py` expects a JSON array. Each item must contain:

```json
{
  "question_id": "q-001",
  "question": "What does the source document say about ...?",
  "category": "factual",
  "relevant_chunk_ids": ["chunk-id-from-api-query"],
  "relevant_document_ids": ["document-id"],
  "required_citations": ["document-id or source reference"],
  "expected_answer": "Reference answer when answer quality is being evaluated"
}
```

Required categories are defined in `schema.py`: factual, multi-hop, comparison, numerical, table, summarization, image, audio, cross-modal, unanswerable, and adversarial. Optional fields default to empty lists or null, but metrics requiring them will remain unavailable.

## Files to provide locally

For a pilot, provide:

1. A small set of representative source files in formats the ingestion pipeline supports: PDF, DOCX, PNG/JPEG, and audio only when audio evaluation is intended.
2. One versioned dataset JSON file using the schema above.
3. Ground-truth relevant document/chunk IDs obtained from the same ingested session and stable document version.
4. Reference answers for exact match, token F1, relevance, faithfulness, or human/LLM-judge evaluation.
5. Citation/source annotations for citation precision and completeness.
6. For audio, reference transcripts; for image questions, page/image identifiers and human-verified relevance labels.

Do not put API keys or private credentials in the dataset. Keep source documents and annotations in a local directory outside committed secrets, and record only a dataset identifier/version in reports.

The installed corpus is organized under `evaluation/corpus/`: `pdf/`, `docx/`, `images/`, and `audio/`. Unsupported archive formats such as PPTX, XLSX, CSV, TXT, and Markdown were not placed in the ingest corpus because the current ingestion contract does not verify them.

## Recommended pilot coverage

Use enough examples to exercise every intended path, not an arbitrary research sample size:

- direct factual and paraphrased questions;
- multi-document and table questions;
- unanswerable questions that should trigger abstention;
- relevant and irrelevant retrieval candidates;
- one or more image questions if genuine image retrieval is enabled;
- audio questions only if transcription is part of the tested pipeline;
- one malformed/unsupported input for error handling.

Before scaling up, validate that every `question_id` is unique, every referenced chunk/document exists in the target session, and source files can be re-ingested without accidental duplicate or stale records. Use a new isolated test session for experiments rather than clearing production data.

## Metric applicability

- P@K, R@K, MRR, MAP, nDCG: require relevant IDs or graded relevance labels.
- Exact match/token F1: require reference answers.
- Faithfulness/groundedness: require retrieved context plus judge or human annotations; the internal citation-presence signal is not semantic proof.
- Citation precision/completeness: require expected citation/source annotations.
- ROC-AUC/PR-AUC: require binary labels and continuous candidate scores with both classes; arbitrary generated answers are invalid scores.
- Latency, error rate, provider/model identity: available from live operational records without reference answers.
- Confidence intervals and comparative claims: require enough repeated, eligible observations and a documented experiment design.