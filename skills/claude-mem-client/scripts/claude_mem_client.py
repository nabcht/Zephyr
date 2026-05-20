# memory/claude_mem.py
"""Claude-Mem integration client for μZephyr.

Provides a thin wrapper around the Claude-Mem service used by μZephyr to store and retrieve
memory items. The client handles JSON encoding, basic authentication via an API key, and
error handling for network and response issues.
"""
import json
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

class ClaudeMemClient:
    """Client for interacting with the Claude-Mem API.

    Parameters
    ----------
    endpoint: str
        Base URL of the Claude-Mem service (e.g., ``"http://localhost:8000"``).
    api_key: str, optional
        Bearer token for authentication. If omitted, requests are made without the
        ``Authorization`` header.
    """

    def __init__(self, endpoint: str, api_key: Optional[str] = None) -> None:
        if not endpoint or not isinstance(endpoint, str):
            raise ValueError("endpoint must be a non‑empty string")
        self.endpoint = endpoint.rstrip('/')
        self.api_key = api_key

    def _request(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to POST ``payload`` to ``path`` and decode JSON response.
        """
        url = f"{self.endpoint}/{path.lstrip('/')}"
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request) as resp:
                resp_bytes = resp.read()
                resp_text = resp_bytes.decode("utf-8")
                return json.loads(resp_text)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Claude-Mem HTTP error {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Claude-Mem connection error: {e.reason}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError("Claude-Mem returned invalid JSON") from e

    def store_memory(self, key: str, content: Any) -> Dict[str, Any]:
        """Store a memory item.

        Parameters
        ----------
        key: str
            Unique identifier for the memory entry.
        content: Any
            JSON‑serialisable data to be stored.
        """
        if not key:
            raise ValueError("key must be a non‑empty string")
        payload = {"key": key, "content": content}
        return self._request("/store", payload)

    def retrieve_memory(self, key: str) -> Dict[str, Any]:
        """Retrieve a memory item by its ``key``.

        Returns the raw JSON object from Claude‑Mem.
        """
        if not key:
            raise ValueError("key must be a non‑empty string")
        payload = {"key": key}
        return self._request("/retrieve", payload)
