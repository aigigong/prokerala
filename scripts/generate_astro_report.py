"""Generate natal chart, transit data, and AI insights via Prokerala APIs."""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional

import requests

from prokerala_client import ProkeralaAPIError, ProkeralaAstrologyClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--birth-datetime", required=True, help="Birth datetime in ISO 8601 format")
    parser.add_argument("--birth-lat", type=float, required=True, help="Birth latitude")
    parser.add_argument("--birth-lon", type=float, required=True, help="Birth longitude")
    parser.add_argument(
        "--transit-datetime",
        default=datetime.now(timezone.utc).isoformat(),
        help="Transit datetime in ISO 8601 format (defaults to now)",
    )
    parser.add_argument("--current-lat", type=float, help="Current latitude (defaults to birth latitude)")
    parser.add_argument("--current-lon", type=float, help="Current longitude (defaults to birth longitude)")
    parser.add_argument(
        "--house-system",
        default="placidus",
        help="House system to use. See astrology.v2.yaml /components/parameters/house_system",
    )
    parser.add_argument(
        "--orb",
        default="default",
        choices=["default", "exact"],
        help="Aspect orb value (default or exact)",
    )
    parser.add_argument(
        "--ayanamsa",
        type=int,
        default=0,
        help="Ayanamsa selection (0 = tropical, 1 = Lahiri, 3 = Raman, 5 = KP)",
    )
    parser.add_argument("--language", default="en", help="Language code for textual responses (default: en)")
    parser.add_argument(
        "--birth-time-unknown",
        action="store_true",
        help="Flag to mark birth time as unknown, per profile parameter definition",
    )
    parser.add_argument(
        "--birth-time-rectification",
        choices=["flat-chart", "true-sunrise-chart"],
        help="Birth time rectification mode (optional)",
    )
    parser.add_argument(
        "--aspect-filter",
        choices=["all", "major", "minor"],
        default="major",
        help="Aspect filter for natal chart",
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Directory where API responses will be stored",
    )
    parser.add_argument(
        "--openai-model",
        default="gpt-4o-mini",
        help="Chat model to use when calling the OpenAI API",
    )
    parser.add_argument(
        "--deepseek-model",
        default="deepseek-chat",
        help="Chat model to use when falling back to the DeepSeek API",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    return parser


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _profile_dict(args: argparse.Namespace) -> Mapping[str, Any]:
    return {
        "datetime": args.birth_datetime,
        "coordinates": f"{args.birth_lat},{args.birth_lon}",
        "birth_time_unknown": args.birth_time_unknown or None,
    }


def _current_coordinates(args: argparse.Namespace) -> str:
    lat = args.current_lat if args.current_lat is not None else args.birth_lat
    lon = args.current_lon if args.current_lon is not None else args.birth_lon
    return f"{lat},{lon}"


def _save_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def _planet_summary(positions: Iterable[Mapping[str, Any]]) -> List[str]:
    lines: List[str] = []
    for planet in positions:
        name = planet.get("name", "?")
        zodiac = planet.get("zodiac", {}).get("name", "?")
        degree = planet.get("degree")
        house = planet.get("house_number")
        retrograde = " (R)" if planet.get("is_retrograde") else ""
        if isinstance(degree, (int, float)):
            degree_str = f"{degree:.2f}°"
        else:
            degree_str = str(degree)
        lines.append(f"{name}: {degree_str} {zodiac} (House {house}){retrograde}")
    return lines


def _aspect_summary(aspects: Iterable[Mapping[str, Any]]) -> List[str]:
    summaries: List[str] = []
    for aspect in aspects:
        planet_one = aspect.get("planet_one", {}).get("name", "?")
        planet_two = aspect.get("planet_two", {}).get("name", "?")
        aspect_name = aspect.get("aspect", {}).get("name") or aspect.get("name")
        orb = aspect.get("orb")
        orb_str = f" (orb {orb:.2f})" if isinstance(orb, (int, float)) else ""
        summaries.append(f"{planet_one} {aspect_name} {planet_two}{orb_str}")
    return summaries


def _prepare_insight_prompt(
    natal_positions: Mapping[str, Any],
    transit_data: Mapping[str, Any],
) -> str:
    natal_planets = natal_positions.get("data", {}).get("planet_positions", [])
    natal_angles = natal_positions.get("data", {}).get("angles", [])
    transit_planets = transit_data.get("data", {}).get("transit_details", {}).get("planet_positions", [])
    transit_aspects = transit_data.get("data", {}).get("transit_natal_aspects", [])

    lines: List[str] = [
        "You are an expert western astrologer. Provide a concise interpretation using the natal placements and current transits."
    ]
    if natal_planets:
        lines.append("\nNatal planet positions:")
        lines.extend(f"- {row}" for row in _planet_summary(natal_planets))
    if natal_angles:
        lines.append("\nKey angles:")
        lines.extend(
            f"- {row}" for row in _planet_summary(natal_angles)
        )
    if transit_planets:
        lines.append("\nCurrent transit positions:")
        lines.extend(f"- {row}" for row in _planet_summary(transit_planets))
    if transit_aspects:
        lines.append("\nImportant transit-to-natal aspects:")
        lines.extend(f"- {row}" for row in _aspect_summary(transit_aspects))

    lines.append(
        "\nSummarize the natal themes in three bullet points and highlight three short-term transit influences."
    )
    lines.append("Keep the tone practical and supportive.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# AI insight helpers
# ---------------------------------------------------------------------------


class InsightGenerator:
    def __init__(
        self,
        *,
        openai_api_key: Optional[str],
        deepseek_api_key: Optional[str],
        openai_model: str,
        deepseek_model: str,
    ) -> None:
        self._openai_key = openai_api_key
        self._deepseek_key = deepseek_api_key
        self._openai_model = openai_model
        self._deepseek_model = deepseek_model

    def generate(self, prompt: str) -> Optional[str]:
        if not prompt.strip():
            return None

        if self._openai_key:
            try:
                return self._call_openai(prompt)
            except requests.RequestException as exc:  # pragma: no cover - network path
                logger.warning("OpenAI request failed: %s", exc)

        if self._deepseek_key:
            try:
                return self._call_deepseek(prompt)
            except requests.RequestException as exc:  # pragma: no cover - network path
                logger.warning("DeepSeek request failed: %s", exc)
        return None

    # ------------------------------------------------------------------
    def _call_openai(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self._openai_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._openai_model,
            "messages": [
                {"role": "system", "content": "You are an insightful western astrologer."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    def _call_deepseek(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self._deepseek_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._deepseek_model,
            "messages": [
                {"role": "system", "content": "You are an insightful western astrologer."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)s %(message)s")

    client_id = os.getenv("PROKERALA_CLIENT_ID")
    client_secret = os.getenv("PROKERALA_CLIENT_SECRET")
    if not client_id or not client_secret:
        parser.error("PROKERALA_CLIENT_ID and PROKERALA_CLIENT_SECRET environment variables are required")

    client = ProkeralaAstrologyClient(client_id, client_secret)

    profile = _profile_dict(args)
    current_coords = _current_coordinates(args)
    logger.info("Requesting natal chart and transit data from Prokerala")

    try:
        natal_chart = client.get_natal_chart(
            profile=profile,
            house_system=args.house_system,
            orb=args.orb,
            language=args.language,
            birth_time_rectification=args.birth_time_rectification,
            aspect_filter=args.aspect_filter,
            ayanamsa=args.ayanamsa,
        )
        natal_positions = client.get_natal_planet_positions(
            profile=profile,
            house_system=args.house_system,
            orb=args.orb,
            language=args.language,
            birth_time_rectification=args.birth_time_rectification,
            ayanamsa=args.ayanamsa,
        )
        transit_positions = client.get_transit_positions(
            profile=profile,
            transit_datetime=args.transit_datetime,
            current_coordinates=current_coords,
            house_system=args.house_system,
            orb=args.orb,
            language=args.language,
            birth_time_rectification=args.birth_time_rectification,
            ayanamsa=args.ayanamsa,
        )
    except ProkeralaAPIError as exc:
        logger.error("Prokerala API error: %s", exc)
        return 1

    output_dir = Path(args.output_dir)
    _save_json(output_dir / "natal_chart.json", natal_chart)
    _save_json(output_dir / "natal_positions.json", natal_positions)
    _save_json(output_dir / "transit_positions.json", transit_positions)
    logger.info("Saved responses to %s", output_dir.resolve())

    print("\nNatal chart response:")
    print(json.dumps(natal_chart, indent=2)[:2000])
    print("\nTransit positions response:")
    print(json.dumps(transit_positions, indent=2)[:2000])

    openai_key = os.getenv("OPENAI_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")

    prompt = _prepare_insight_prompt(natal_positions, transit_positions)
    generator = InsightGenerator(
        openai_api_key=openai_key,
        deepseek_api_key=deepseek_key,
        openai_model=args.openai_model,
        deepseek_model=args.deepseek_model,
    )
    insight = generator.generate(prompt)
    if insight:
        print("\nAI insight:")
        print(insight)
    else:
        print("\nAI insight: unavailable (no API key or network error)")

    return 0


if __name__ == "__main__":  # pragma: no cover - script entrypoint
    raise SystemExit(main())
