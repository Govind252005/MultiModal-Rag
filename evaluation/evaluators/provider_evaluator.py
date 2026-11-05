"""
Provider Evaluator module.
Coordinates end-to-end evaluation for an LLM provider (Ollama or Groq).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence
from evaluation.evaluators.citation_evaluator import CitationEvaluator
from evaluation.evaluators.generation_evaluator import GenerationEvaluator
from evaluation.providers.base_provider import BaseEvalProvider


class ProviderEvaluator:
    """Evaluates answer generation and citation behavior for a specific provider."""

    def __init__(self, provider: BaseEvalProvider):
        self.provider = provider
        self.generation_evaluator = GenerationEvaluator()
        self.citation_evaluator = CitationEvaluator()

    def evaluate_provider_generation(
        self,
        questions_with_retrieval: Sequence[Dict[str, Any]],
        system_prompt: str = (
            "You are a helpful assistant answering questions using only the provided context. "
            "If the answer is not in the context, explicitly state that you cannot find the answer."
        ),
    ) -> Dict[str, Any]:
        """
        Runs generation for each question using self.provider, then evaluates
        correctness, relevance, faithfulness, and citation quality.
        """
        if not self.provider.is_available():
            return {
                "status": "NOT_RUN",
                "reason": f"Provider '{self.provider.name}' is not reachable or API key is not configured.",
                "generation": {},
                "citations": {},
            }

        generation_records = []
        citation_records = []
        latencies = []

        for item in questions_with_retrieval:
            qid = item["question_id"]
            q = item["question"]
            gt = item["ground_truth"]
            ans = item["answerable"]
            req_cites = item.get("required_citations", [])
            ret_items = item.get("retrieved_items", [])
            contexts = [h.get("text") or h.get("snippet") or "" for h in ret_items]

            context_block = "\n\n".join([f"Source [{h.get('file', 'doc')}]: {txt}" for h, txt in zip(ret_items, contexts)])
            user_prompt = f"Context:\n{context_block}\n\nQuestion: {q}\nAnswer:"

            gen_res = self.provider.generate(user_prompt, system=system_prompt)
            gen_text = gen_res["text"]
            lat = gen_res["latency_ms"]
            latencies.append(lat)

            # Find cited sources mentioned in response or citations
            cited_files = []
            for h in ret_items:
                fname = h.get("file")
                if fname and (fname.lower() in gen_text.lower() or f"[{fname}]" in gen_text):
                    cited_files.append(fname)
            cited_files = list(set(cited_files))

            rec = {
                "question_id": qid,
                "question": q,
                "ground_truth": gt,
                "generated_answer": gen_text,
                "retrieved_contexts": contexts,
                "answerable": ans,
                "faithfulness_warning": False,
                "latency_ms": lat,
            }
            generation_records.append(rec)

            cit_rec = {
                "question_id": qid,
                "generated_answer": gen_text,
                "cited_files": cited_files,
                "required_citations": req_cites,
                "retrieved_items": ret_items,
                "answerable": ans,
            }
            citation_records.append(cit_rec)

        gen_eval = self.generation_evaluator.evaluate_generation(generation_records)
        cit_eval = self.citation_evaluator.evaluate_citations(citation_records)

        return {
            "status": "COMPLETED",
            "provider": self.provider.name,
            "model": self.provider.model,
            "usage": self.provider.get_usage(),
            "generation": gen_eval,
            "citations": cit_eval,
            "generation_records": generation_records,
            "citation_records": citation_records,
        }
