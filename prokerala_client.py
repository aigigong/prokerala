"""Client utilities for interacting with the Prokerala Astrology API."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Mapping, MutableMapping, Optional

import requests


TOKEN_URL = "https://api.prokerala.com/token"
DEFAULT_BASE_URL = "https://api.prokerala.com/v2"


class ProkeralaAuthenticationError(RuntimeError):
    """Raised when an access token cannot be acquired."""


class ProkeralaAPIError(RuntimeError):
    """Raised when an API request returns an unexpected response."""


@dataclass
class AccessToken:
    token: str
    expires_at: float

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - 60  # refresh a minute early


class ProkeralaClient:
    """Simple wrapper around the Prokerala astrology REST API."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._token: Optional[AccessToken] = None

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------
    def _refresh_token(self) -> AccessToken:
        response = self._session.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise ProkeralaAuthenticationError(
                f"Unable to fetch access token (status {response.status_code}): {response.text}"
            )
        payload = response.json()
        token = payload.get("access_token")
        expires_in = payload.get("expires_in", 0)
        if not token or not isinstance(token, str):
            raise ProkeralaAuthenticationError("Response missing access_token field")
        expires_at = time.time() + float(expires_in or 0)
        self._token = AccessToken(token=token, expires_at=expires_at)
        return self._token

    def _get_token(self) -> str:
        if self._token is None or self._token.is_expired:
            self._refresh_token()
        assert self._token is not None  # for mypy/static checkers
        return self._token.token

    # ------------------------------------------------------------------
    # Core request helper
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, *, params: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self._get_token()}"}
        response = self._session.request(method.upper(), url, headers=headers, params=params, timeout=30)
        if response.status_code != 200:
            raise ProkeralaAPIError(
                f"API request failed (status {response.status_code}) for {url}: {response.text}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ProkeralaAPIError(f"Invalid JSON in response from {url}") from exc

    # ------------------------------------------------------------------
    # Public helpers for frequently used endpoints
    # ------------------------------------------------------------------
    def get_kundli(
        self,
        *,
        coordinates: str,
        datetime_iso: str,
        ayanamsa: int = 0,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Fetches the natal chart (kundli) for the provided birth details."""
        params: MutableMapping[str, Any] = {
            "coordinates": coordinates,
            "datetime": datetime_iso,
            "ayanamsa": ayanamsa,
            "la": language,
        }
        return self._request("GET", "/astrology/kundli", params=params)

    def get_transit_planet_position(
        self,
        *,
        profile: Mapping[str, Any],
        transit_datetime: str,
        current_coordinates: str,
        ayanamsa: int = 0,
        house_system: str = "placidus",
        orb: float = 1.0,
        birth_time_rectification: bool = False,
        aspect_filter: str = "major",
        language: str = "en",
    ) -> Dict[str, Any]:
        """Fetch the transit planet positions for the supplied context."""

        params: Dict[str, Any] = {
            **serialize_object_param("profile", profile),
            "transit_datetime": transit_datetime,
            "current_coordinates": current_coordinates,
            "ayanamsa": ayanamsa,
            "house_system": house_system,
            "orb": orb,
            "birth_time_rectification": str(birth_time_rectification).lower(),
            "aspect_filter": aspect_filter,
            "la": language,
        }
        return self._request("GET", "/astrology/transit-planet-position", params=params)


# ----------------------------------------------------------------------
# Utility helpers
# ----------------------------------------------------------------------

def serialize_object_param(name: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Serialise a mapping into a flat dictionary suitable for query parameters.

    The Prokerala API expects nested objects to be encoded using the
    ``name[key]`` convention. This helper converts ``{"datetime": "..."}``
    into ``{"name[datetime]": "..."}``.
    """

    flattened: Dict[str, Any] = {}
    for key, value in payload.items():
        member = f"{name}[{key}]"
        if isinstance(value, (dict, list)):
            flattened[member] = json.dumps(value)
        elif isinstance(value, bool):
            flattened[member] = str(value).lower()
        else:
            flattened[member] = value
    return flattened
