"""CLI entrypoint to fetch Prokerala natal chart and transit data."""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from insights import InsightGenerationError, generate_insights
from prokerala_client import ProkeralaAPIError, ProkeralaClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-id", default=os.getenv("PROKERALA_CLIENT_ID"), help="Prokerala client id")
    parser.add_argument(
        "--client-secret", default=os.getenv("PROKERALA_CLIENT_SECRET"), help="Prokerala client secret"
    )
    parser.add_argument("--birth-datetime", required=True, help="Birth datetime in ISO 8601 format")
    parser.add_argument("--birth-coordinates", required=True, help="Birth coordinates as 'lat,long'")
    parser.add_argument(
        "--transit-datetime",
        default=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        help="Transit datetime in ISO 8601 format (defaults to current UTC time)",
    )
    parser.add_argument(
        "--current-coordinates",
        help="Current location coordinates as 'lat,long'. Defaults to birth coordinates.",
    )
    parser.add_argument("--ayanamsa", type=int, default=0, help="Ayanamsa id (0=Tropical, 1=Lahiri, etc)")
    parser.add_argument("--language", default="en", help="Language code (default: en)")
    parser.add_argument(
        "--house-system",
        default="placidus",
        help="House system for transit calculations (e.g. placidus, koch)",
    )
    parser.add_argument("--orb", type=float, default=1.0, help="Orb value for transit aspects")
    parser.add_argument(
        "--birth-time-unknown",
        action="store_true",
        help="Set if the birth time is unknown (used for transit profile)",
    )
    parser.add_argument(
        "--output-dir",
        default=Path.cwd(),
        type=Path,
        help="Directory to store the raw JSON responses",
    )
    parser.add_argument("--openai-model", default="gpt-4o-mini", help="OpenAI model for insight generation")
    parser.add_argument("--deepseek-model", default="deepseek-chat", help="DeepSeek model for fallback insights")
    parser.add_argument(
        "--aspect-filter", default="major", help="Transit aspect filter (major, minor, all)")
    return parser.parse_args()


def ensure_credentials(args: argparse.Namespace) -> None:
    if not args.client_id or not args.client_secret:
        raise SystemExit("Both client id and client secret must be supplied via arguments or environment variables")



def build_transit_profile(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "datetime": args.birth_datetime,
        "coordinates": args.birth_coordinates,
        "birth_time_unknown": args.birth_time_unknown,
    }


def save_json(target: Path, data: Dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False))



def main() -> None:
    args = parse_args()
    ensure_credentials(args)

    current_coordinates = args.current_coordinates or args.birth_coordinates

    client = ProkeralaClient(args.client_id, args.client_secret)

    logger.info("Fetching natal chart data from Prokerala")
    try:
        natal_chart = client.get_kundli(
            coordinates=args.birth_coordinates,
            datetime_iso=args.birth_datetime,
            ayanamsa=args.ayanamsa,
            language=args.language,
        )
    except ProkeralaAPIError as exc:
        raise SystemExit(f"Failed to fetch natal chart: {exc}")

    logger.info("Fetching transit data from Prokerala")
    try:
        transit_data = client.get_transit_planet_position(
            profile=build_transit_profile(args),
            transit_datetime=args.transit_datetime,
            current_coordinates=current_coordinates,
            ayanamsa=args.ayanamsa,
            house_system=args.house_system,
            orb=args.orb,
            birth_time_rectification=args.birth_time_unknown,
            aspect_filter=args.aspect_filter,
            language=args.language,
        )
    except ProkeralaAPIError as exc:
        raise SystemExit(f"Failed to fetch transit data: {exc}")

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    natal_path = output_dir / "natal_chart.json"
    transit_path = output_dir / "transits.json"
    save_json(natal_path, natal_chart)
    save_json(transit_path, transit_data)

    logger.info("Saved natal chart to %s", natal_path)
    logger.info("Saved transit data to %s", transit_path)

    openai_api_key = os.getenv("OPENAI_API_KEY")
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_TOKEN")

    insights_text = ""
    try:
        insights_text = generate_insights(
            birth_details={
                "birth_datetime": args.birth_datetime,
                "birth_coordinates": args.birth_coordinates,
                "transit_datetime": args.transit_datetime,
                "current_coordinates": current_coordinates,
                "ayanamsa": args.ayanamsa,
                "house_system": args.house_system,
                "language": args.language,
            },
            natal_chart=natal_chart,
            transit_data=transit_data,
            openai_api_key=openai_api_key,
            deepseek_api_key=deepseek_api_key,
            openai_model=args.openai_model,
            deepseek_model=args.deepseek_model,
        )
    except InsightGenerationError as exc:
        logger.warning("Insight generation skipped: %s", exc)

    print("\n=== Natal Chart (raw) ===")
    print(json.dumps(natal_chart, indent=2, ensure_ascii=False))

    print("\n=== Current Transit Data (raw) ===")
    print(json.dumps(transit_data, indent=2, ensure_ascii=False))

    if insights_text:
        print("\n=== Generated Insights ===")
        print(insights_text)
    else:
        print("\nInsights were not generated. Check API key configuration and logs above.")


if __name__ == "__main__":
    main()
