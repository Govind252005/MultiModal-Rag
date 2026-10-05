"""
Comprehensive citation judge.
Evaluates the 4 distinct citation dimensions (Requirement 11):
1. Citation presence
2. Source-level citation precision
3. Claim-level citation accuracy
4. Citation completeness / claim coverage
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set
from evaluation.judges.faithfulness_judge import split_into_claims
from evaluation.metrics.citation_metrics import (
    citation_completeness,
    citation_presence,
    claim_level_accuracy,
    source_level_precision,
)
from evaluation.metrics.generation_metrics import token_overlap_f1


class CitationJudge:
    """Evaluates citations across all 4 required dimensions."""

    def __init__(self, claim_support_threshold: float = 0.35):
        self.claim_support_threshold = claim_support_threshold

    @staticmethod
    def _source_key(value: str) -> str:
        return Path(str(value or "")).name.lower()

    def _inline_cited_files(
        self,
        answer: str,
        fallback_files: Sequence[str],
        available_citations: Sequence[Dict[str, Any]],
    ) -> List[str]:
        """Resolve only citations actually referenced by the answer.

        The backend returns a citation map for every retrieved hit. That map
        is not proof that the model cited every hit, so presence/precision must
        be based on inline [n] markers in the answer.
        """
        indexes = {int(n) for n in re.findall(r"\[(\d+)\]", answer or "")}
        if not indexes:
            return []
        by_index = {
            int(c.get("index")): c.get("file")
            for c in available_citations
            if c.get("index") is not None and c.get("file")
        }
        if not by_index:
            # Backward-compatible fallback for callers that do not provide a
            # citation map: [1] refers to the first returned source.
            return [f for i, f in enumerate(fallback_files, start=1) if i in indexes]
        return [by_index[i] for i in sorted(indexes) if i in by_index]

    def judge_citations(
        self,
        generated_answer: str,
        cited_files: Sequence[str],
        required_citations: Sequence[str],
        retrieved_items: Sequence[Dict[str, Any]],
        requires_evidence: bool = True,
        available_citations: Sequence[Dict[str, Any]] = (),
    ) -> Dict[str, Any]:
        """
        Calculates all four distinct citation dimensions:
        - presence: bool
        - source_precision: float (0.0 to 1.0)
        - claim_accuracy: float (0.0 to 1.0)
        - completeness: float (0.0 to 1.0)
        """
        inline_cited_files = self._inline_cited_files(
            generated_answer, cited_files, available_citations
        )

        # 1. Presence: returned citation metadata alone is not an inline
        # citation in the answer.
        present = citation_presence(inline_cited_files)

        # 2. Source-level citation precision
        expected_set = {self._source_key(s) for s in required_citations}
        cited_set = [self._source_key(s) for s in inline_cited_files]
        src_precision = source_level_precision(cited_set, expected_set) if expected_set else (1.0 if not cited_set else 0.0)

        # 3 & 4. Claim analysis
        claims = split_into_claims(generated_answer)
        total_claims = len(claims)

        # Map cited files to text snippet evidence
        evidence_by_file: Dict[str, List[str]] = {}
        for item in retrieved_items:
            fname = item.get("file")
            txt = item.get("text") or item.get("snippet") or ""
            if fname and txt:
                evidence_by_file.setdefault(self._source_key(fname), []).append(txt)

        # Check claim-level support
        claims_checked = 0
        claims_supported = 0

        # Look for in-text citations like [1], [filename], (filename), etc.
        has_bracket_citations = bool(re.search(r"\[\d+\]|\[.*?\.pdf\]|\(.*?.pdf\)", generated_answer, re.IGNORECASE))

        # Check how many claims are supported by cited sources
        for claim in claims:
            claims_checked += 1
            claim_indexes = {int(n) for n in re.findall(r"\[(\d+)\]", claim)}
            claim_files = []
            for position, citation in enumerate(available_citations, start=1):
                index = citation.get("index", position)
                if citation.get("file") and int(index) in claim_indexes:
                    claim_files.append(citation["file"])
            claim_text = " ".join(
                txt for f in claim_files
                for txt in evidence_by_file.get(self._source_key(f), [])
            ).lower()
            if claim_text:
                overlap = token_overlap_f1(claim, claim_text)
                if overlap["precision"] >= self.claim_support_threshold:
                    claims_supported += 1

        claim_acc = claim_level_accuracy(claims_checked, claims_supported)

        # 4. Completeness: if evidence is required, did the claims get citations/citations present?
        if requires_evidence and total_claims > 0:
            claims_with_citation = total_claims if present else 0
            completeness = citation_completeness(total_claims, claims_with_citation)
        else:
            completeness = 1.0

        return {
            "citation_present": present,
            "source_level_precision": round(src_precision, 4),
            "claim_level_accuracy": round(claim_acc, 4),
            "citation_completeness": round(completeness, 4),
            "cited_files": list(inline_cited_files),
            "required_citations": list(required_citations),
            "total_claims": total_claims,
            "claims_supported": claims_supported,
        }
