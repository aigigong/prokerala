"""Insight generation using OpenAI with a DeepSeek fallback."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"


class InsightGenerationError(RuntimeError):
    """Raised when neither OpenAI nor DeepSeek can generate insights."""


def _call_chat_completion(
    *,
    endpoint: str,
    api_key: str,
    model: str,
    prompt: str,
    provider: str,
    temperature: float = 0.3,
) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are an experienced astrologer. Provide concise, actionable insights.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }
    response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        raise InsightGenerationError(
            f"{provider} API error (status {response.status_code}): {response.text}"
        )
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise InsightGenerationError(f"Unexpected {provider} API response format: {data}") from exc


def _summarise_payload(payload: Dict[str, Any], *, max_chars: int = 2000) -> str:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if len(text) > max_chars:
        return text[: max_chars - 3] + "..."
    return text


def generate_insights(
    *,
    birth_details: Dict[str, Any],
    natal_chart: Dict[str, Any],
    transit_data: Dict[str, Any],
    openai_api_key: Optional[str],
    deepseek_api_key: Optional[str],
    openai_model: str = "gpt-4o-mini",
    deepseek_model: str = "deepseek-chat",
) -> str:
    """Generate astrology insights using OpenAI with a DeepSeek fallback."""

    prompt = (
        "Review the natal chart and current transit details below. "
        "Highlight the most significant themes, strengths, and current opportunities/challenges. "
        "Make sure your response is easy to read with short paragraphs and bullet points where helpful.\n\n"
        "Birth details:\n"
        f"{_summarise_payload(birth_details, max_chars=400)}\n\n"
        "Natal chart summary:\n"
        f"{_summarise_payload(natal_chart.get('data', natal_chart))}\n\n"
        "Transit data summary:\n"
        f"{_summarise_payload(transit_data.get('data', transit_data))}"
    )

    if openai_api_key:
        try:
            logger.info("Requesting insights from OpenAI model %s", openai_model)
            return _call_chat_completion(
                endpoint=OPENAI_ENDPOINT,
                api_key=openai_api_key,
                model=openai_model,
                prompt=prompt,
                provider="OpenAI",
            )
        except InsightGenerationError as exc:
            logger.warning("OpenAI insight generation failed: %s", exc)

    if deepseek_api_key:
        try:
            logger.info("Falling back to DeepSeek model %s", deepseek_model)
            return _call_chat_completion(
                endpoint=DEEPSEEK_ENDPOINT,
                api_key=deepseek_api_key,
                model=deepseek_model,
                prompt=prompt,
                provider="DeepSeek",
            )
        except InsightGenerationError as exc:
            logger.warning("DeepSeek insight generation failed: %s", exc)

    raise InsightGenerationError(
        "Unable to generate insights – no provider succeeded and at least one API key must be configured."
    )
