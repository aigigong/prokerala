"""Client helpers for interacting with the Prokerala Astrology API."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterator, Mapping, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class ProkeralaAPIError(RuntimeError):
    """Raised when the Prokerala API responds with an error status."""


@dataclass
class OAuthToken:
    access_token: str
    token_type: str
    expires_in: int
    created_at: float

    @property
    def is_expired(self) -> bool:
        # Refresh slightly before actual expiry to avoid edge cases.
        return time.time() >= self.created_at + max(self.expires_in - 30, 0)


class ProkeralaAstrologyClient:
    """Thin wrapper around the Prokerala Astrology REST API."""

    token_url = "https://api.prokerala.com/token"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        base_url: str = "https://api.prokerala.com/v2",
        session: Optional[requests.Session] = None,
    ) -> None:
        if not client_id or not client_secret:
            raise ValueError("client_id and client_secret are required")

        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._token: Optional[OAuthToken] = None

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------
    def _request_token(self) -> OAuthToken:
        logger.debug("Requesting OAuth token from Prokerala")
        response = self._session.post(
            self.token_url,
            data=
            {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise ProkeralaAPIError(
                f"Token request failed with status {response.status_code}: {response.text}"
            )
        payload = response.json()
        logger.debug("Received OAuth token payload: %s", payload)
        return OAuthToken(
            access_token=payload["access_token"],
            token_type=payload.get("token_type", "Bearer"),
            expires_in=int(payload.get("expires_in", 3600)),
            created_at=time.time(),
        )

    def _ensure_token(self) -> OAuthToken:
        if self._token is None or self._token.is_expired:
            self._token = self._request_token()
        return self._token

    # ------------------------------------------------------------------
    # Low level request helper
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, *, params: Optional[Mapping[str, str]] = None) -> Mapping[str, object]:
        token = self._ensure_token()
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"{token.token_type} {token.access_token}"}
        logger.debug("Sending %s request to %s with params %s", method, url, params)
        response = self._session.request(method, url, params=params, headers=headers, timeout=60)
        if response.status_code >= 400:
            raise ProkeralaAPIError(
                f"API request to {path} failed with status {response.status_code}: {response.text}"
            )
        logger.debug("Response from %s: %s", path, response.text)
        return response.json()

    # ------------------------------------------------------------------
    # Public helpers for commonly used endpoints
    # ------------------------------------------------------------------
    def get_natal_chart(
        self,
        *,
        profile: Mapping[str, object],
        house_system: str,
        orb: str,
        language: Optional[str] = None,
        birth_time_rectification: Optional[str] = None,
        aspect_filter: Optional[str] = None,
        ayanamsa: Optional[int] = None,
    ) -> Mapping[str, object]:
        params = dict(self._flatten_object("profile", profile))
        params.update(
            {
                "house_system": house_system,
                "orb": orb,
            }
        )
        if language:
            params["la"] = language
        if birth_time_rectification:
            params["birth_time_rectification"] = birth_time_rectification
        if aspect_filter:
            params["aspect_filter"] = aspect_filter
        if ayanamsa is not None:
            params["ayanamsa"] = str(ayanamsa)
        return self._request("GET", "/astrology/natal-chart", params=params)

    def get_natal_planet_positions(
        self,
        *,
        profile: Mapping[str, object],
        house_system: str,
        orb: str,
        language: Optional[str] = None,
        birth_time_rectification: Optional[str] = None,
        ayanamsa: Optional[int] = None,
    ) -> Mapping[str, object]:
        params = dict(self._flatten_object("profile", profile))
        params.update(
            {
                "house_system": house_system,
                "orb": orb,
            }
        )
        if language:
            params["la"] = language
        if birth_time_rectification:
            params["birth_time_rectification"] = birth_time_rectification
        if ayanamsa is not None:
            params["ayanamsa"] = str(ayanamsa)
        return self._request("GET", "/astrology/natal-planet-position", params=params)

    def get_transit_positions(
        self,
        *,
        profile: Mapping[str, object],
        transit_datetime: str,
        current_coordinates: str,
        house_system: str,
        orb: str,
        language: Optional[str] = None,
        birth_time_rectification: Optional[str] = None,
        ayanamsa: Optional[int] = None,
    ) -> Mapping[str, object]:
        params = dict(self._flatten_object("profile", profile))
        params.update(
            {
                "transit_datetime": transit_datetime,
                "current_coordinates": current_coordinates,
                "house_system": house_system,
                "orb": orb,
            }
        )
        if language:
            params["la"] = language
        if birth_time_rectification:
            params["birth_time_rectification"] = birth_time_rectification
        if ayanamsa is not None:
            params["ayanamsa"] = str(ayanamsa)
        return self._request("GET", "/astrology/transit-planet-position", params=params)

    # ------------------------------------------------------------------
    @staticmethod
    def _flatten_object(prefix: str, data: Mapping[str, object]) -> Iterator[Tuple[str, str]]:
        for key, value in data.items():
            if value is None:
                continue
            if isinstance(value, bool):
                value_str = str(value).lower()
            else:
                value_str = str(value)
            yield f"{prefix}[{key}]", value_str


__all__ = [
    "ProkeralaAstrologyClient",
    "ProkeralaAPIError",
]
