"""
IntelliCredit — Signal Extractor
Uses OpenRouter LLM API to classify search results as risk signals.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

import requests

from .models import RiskSignal, Severity, SignalType
from .web_searcher import SearchResult

# ── Constants ────────────────────────────────────────────────────────────────

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "mistralai/mistral-7b-instruct"

SCORE_PENALTIES: Dict[str, float] = {
    "HIGH": 25.0,
    "MEDIUM": 12.0,
    "LOW": 5.0,
    "POSITIVE": -5.0,
}

SYSTEM_PROMPT = """You are a credit-risk analyst. Analyze the following search result and determine if it indicates a risk signal for credit assessment.

Respond ONLY with JSON — no markdown, no explanation:
{
  "is_risk": true/false,
  "signal_type": "fraud" | "litigation" | "insolvency" | "regulatory" | "promoter_risk" | "positive" | "unknown",
  "severity": "HIGH" | "MEDIUM" | "LOW" | "POSITIVE",
  "summary": "<under 20 words describing the signal>"
}

Severity rules:
- HIGH: arrest, conviction, ED raid, wilful defaulter, NCLT admission
- MEDIUM: court case, SEBI notice, NPA, arbitration
- LOW: minor, old, or unconfirmed reports
- POSITIVE: awards, rating upgrade, positive recognition
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_signal_type(raw: str) -> SignalType:
    try:
        return SignalType(raw.lower())
    except ValueError:
        return SignalType.UNKNOWN


def _parse_severity(raw: str) -> Severity:
    try:
        return Severity(raw.upper())
    except ValueError:
        return Severity.MEDIUM


# ── Core Functions ───────────────────────────────────────────────────────────

def extract_signal(
    result: SearchResult,
    model: str = DEFAULT_MODEL,
) -> Optional[RiskSignal]:
    """
    Call the OpenRouter LLM to classify a single search result.
    Returns a RiskSignal if a risk is detected, else None.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("  ⚠ OPENROUTER_API_KEY not set — skipping signal extraction")
        return None

    user_content = (
        f"Title: {result.title}\n"
        f"URL: {result.url}\n"
        f"Snippet: {result.snippet}\n"
        f"Search Query: {result.query}"
    )

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.1,
                "max_tokens": 200,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        raw_text = data["choices"][0]["message"]["content"]
        cleaned = _strip_markdown_fences(raw_text)
        parsed = json.loads(cleaned)

        if not parsed.get("is_risk", False):
            return None

        signal_type = _parse_signal_type(parsed.get("signal_type", "unknown"))
        severity = _parse_severity(parsed.get("severity", "MEDIUM"))
        penalty = SCORE_PENALTIES.get(severity.value, 12.0)

        return RiskSignal(
            signal_type=signal_type,
            severity=severity,
            summary=parsed.get("summary", "No summary"),
            source_url=result.url,
            source_query=result.query,
            score_penalty=penalty,
        )

    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠ Signal extraction failed: {exc}")
        return None


def extract_signals_from_results(
    results: List[SearchResult],
    model: str = DEFAULT_MODEL,
    dedupe: bool = True,
) -> List[RiskSignal]:
    """
    Extract signals from a list of search results.
    Deduplicates by signal_type|severity|summary[:60] when dedupe=True.
    """
    signals: list[RiskSignal] = []
    seen_keys: set[str] = set()

    for idx, result in enumerate(results):
        print(f"  🧠 [{idx + 1}/{len(results)}] Analyzing: {result.title[:80]}")
        signal = extract_signal(result, model=model)

        if signal is None:
            continue

        if dedupe:
            key = f"{signal.signal_type.value}|{signal.severity.value}|{signal.summary[:60]}"
            if key in seen_keys:
                continue
            seen_keys.add(key)

        signals.append(signal)

    return signals
