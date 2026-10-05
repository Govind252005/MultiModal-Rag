import json
import re
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, "backend")

from retrieval import vector_store


DATASET = Path("evaluation/datasets/real_rag_eval_dataset_v1_190q.json")
OUTPUT = Path("evaluation/datasets/real_rag_eval_dataset_v1_190q_groundtruth.json")
REPORT = Path("evaluation/datasets/real_rag_eval_groundtruth_report.json")

SESSION_ID = "real-eval-v1"
USER_ID = "5e5d2ac1aedd"

STOPWORDS = {
    "the", "and", "for", "with", "what", "which", "does", "how",
    "many", "is", "are", "was", "were", "of", "a", "an", "in",
    "to", "on", "by", "from", "as", "that", "this", "it", "or",
    "be", "can", "used", "use", "system", "paper", "according",
    "mentioned", "listed", "shown", "specified", "purpose",
    "type", "types", "does", "allow", "return"
}


def normalize(text):
    text = str(text).lower()
    return re.sub(r"\s+", " ", text).strip()


def alnum_normalize(text):
    return re.sub(r"[^a-z0-9]+", " ", normalize(text)).strip()


def tokens(text):
    return [
        t for t in alnum_normalize(text).split()
        if len(t) > 2 and t not in STOPWORDS
    ]


def extract_identifiers(text):
    """
    Extract technical/code identifiers such as:
      pprint.pformat
      zipfile.extractall
      os.path.exists
      dict.get
      range
    """
    return re.findall(
        r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+",
        str(text)
    )


def score_chunk(answer, document):
    """
    Evidence-oriented scoring.

    The score deliberately rewards:
      1. exact answer phrase
      2. technical identifiers
      3. distinctive phrases
      4. token coverage

    It does NOT use RAG retrieval results.
    """

    answer = str(answer)
    document = str(document)

    answer_norm = normalize(answer)
    doc_norm = normalize(document)

    if not answer_norm or not doc_norm:
        return 0.0

    # Exact phrase.
    if answer_norm in doc_norm:
        return 100.0

    # Technical identifiers.
    identifiers = extract_identifiers(answer)

    for identifier in identifiers:
        if identifier.lower() in doc_norm:
            return 98.0

    # Symbolic answers such as +, *, ==, etc.
    if answer.strip() in {
        "+", "-", "*", "/", "//", "%", "**",
        "==", "!=", "<", ">", "<=", ">="
    }:
        if answer.strip() in document:
            return 95.0

    # Important multi-word phrases.
    answer_parts = [
        p.strip()
        for p in re.split(r"[,;/()]|\band\b|\bor\b", answer_norm)
        if len(p.strip()) >= 4
    ]

    phrase_hits = 0

    for part in answer_parts:
        if part in doc_norm:
            phrase_hits += 1

    if answer_parts and phrase_hits:
        phrase_score = (
            phrase_hits / len(answer_parts)
        ) * 80.0

        if phrase_score >= 60:
            return phrase_score

    # Normal token evidence.
    ans_tokens = tokens(answer)

    if not ans_tokens:
        return 0.0

    matched = [
        t for t in ans_tokens
        if t in alnum_normalize(document)
    ]

    coverage = len(matched) / len(ans_tokens)

    # Weighted by token length.
    total_weight = sum(len(t) for t in ans_tokens)
    matched_weight = sum(len(t) for t in matched)

    weighted_coverage = (
        matched_weight / total_weight
        if total_weight
        else 0
    )

    return (
        coverage * 60.0
        + weighted_coverage * 40.0
    )


def page_numbers(locator):
    if not locator:
        return []

    return [
        int(x)
        for x in re.findall(r"p\.(\d+)", str(locator))
    ]


def candidate_chunks(question, rows):

    source_rows = [
        r for r in rows
        if r["metadata"].get("file") == question["source_file"]
    ]

    if not source_rows:
        return []

    target_pages = page_numbers(
        question.get("source_locator")
    )

    scored = []

    for row in source_rows:

        score = score_chunk(
            question.get("answer", ""),
            row.get("document", "")
        )

        page = row["metadata"].get("page")

        if target_pages:
            try:
                page_num = int(page)

                if page_num in target_pages:
                    score += 35

                else:
                    score -= 10

            except (TypeError, ValueError):
                pass

        scored.append((score, row))

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return scored


def classify(scored):

    if not scored:
        return "unmatched", []

    best_score = scored[0][0]

    if best_score <= 0:
        return "unmatched", []

    # Exact answer / exact identifier / exact symbol.
    if best_score >= 95:
        return "confident", [
            scored[0][1]["id"]
        ]

    # Very strong evidence.
    if best_score >= 85:
        return "confident", [
            scored[0][1]["id"]
        ]

    # Check ambiguity.
    if len(scored) >= 2:

        second_score = scored[1][0]

        if (
            best_score < 85
            and best_score - second_score < 10
        ):

            ids = [
                row["id"]
                for score, row in scored[:3]
                if score > 0
            ]

            return "review", ids

    # Moderate evidence.
    if best_score >= 60:
        return "review", [
            scored[0][1]["id"]
        ]

    return "unmatched", []


def main():

    if not DATASET.exists():
        raise FileNotFoundError(DATASET)

    data = json.loads(
        DATASET.read_text(
            encoding="utf-8"
        )
    )

    where = vector_store.build_where(
        session_id=SESSION_ID,
        user_id=USER_ID,
    )

    rows = vector_store.get_text_corpus(
        where=where
    )

    print(
        "Indexed text chunks:",
        len(rows)
    )

    status_counts = Counter()

    review_questions = []
    unmatched_questions = []

    output_questions = []

    for question in data["questions"]:

        q = dict(question)

        # Unanswerable questions have no relevant chunks.
        if not q.get("answerable", False):

            q["relevant_chunk_ids"] = []
            q["ground_truth_status"] = "unanswerable"

            status_counts["unanswerable"] += 1

            output_questions.append(q)

            continue

        scored = candidate_chunks(
            q,
            rows
        )

        status, ids = classify(
            scored
        )

        q["relevant_chunk_ids"] = ids
        q["ground_truth_status"] = status

        status_counts[status] += 1

        if status == "review":

            review_questions.append({
                "id": q["id"],
                "question": q["question"],
                "answer": q["answer"],
                "source_file": q["source_file"],
                "source_locator": q.get(
                    "source_locator"
                ),
                "candidates": [
                    {
                        "chunk_id": row["id"],
                        "score": round(score, 2),
                        "page": row[
                            "metadata"
                        ].get("page"),
                        "preview": row[
                            "document"
                        ][:500]
                    }
                    for score, row in scored[:3]
                ]
            })

        elif status == "unmatched":

            unmatched_questions.append({
                "id": q["id"],
                "question": q["question"],
                "answer": q["answer"],
                "source_file": q["source_file"],
                "source_locator": q.get(
                    "source_locator"
                ),
                "top_candidates": [
                    {
                        "chunk_id": row["id"],
                        "score": round(score, 2),
                        "page": row[
                            "metadata"
                        ].get("page"),
                        "preview": row[
                            "document"
                        ][:500]
                    }
                    for score, row in scored[:3]
                ]
            })

        output_questions.append(q)

    output = dict(data)

    output[
        "ground_truth_version"
    ] = "v2"

    output[
        "ground_truth_method"
    ] = (
        "source-constrained evidence matching with "
        "exact phrases, technical identifiers, symbolic "
        "answers, page-locator preference, and "
        "conservative ambiguity handling"
    )

    output["questions"] = output_questions

    report = {
        "dataset": data.get(
            "dataset_name"
        ),
        "question_count": len(
            output_questions
        ),
        "status_counts": dict(
            status_counts
        ),
        "review_count": len(
            review_questions
        ),
        "unmatched_count": len(
            unmatched_questions
        ),
        "review_questions":
            review_questions,
        "unmatched_questions":
            unmatched_questions,
    }

    OUTPUT.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    REPORT.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print()
    print(
        "=== Ground Truth Generation Complete ==="
    )

    print(
        "Output :",
        OUTPUT
    )

    print(
        "Report :",
        REPORT
    )

    print()
    print("Status:")

    for status, count in status_counts.items():
        print(
            f"  {status:15} {count}"
        )

    print()
    print(
        "The original dataset was NOT modified."
    )


if __name__ == "__main__":
    main()
