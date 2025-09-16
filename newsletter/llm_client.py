"""Unified LLM client helpers supporting Gemini and OpenRouter."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import requests

LOGGER = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-1.5-pro-latest"
DEFAULT_OPENROUTER_MODEL = "openrouter/auto"


class LLMError(RuntimeError):
    """Raised when an LLM provider fails to return a usable response."""


@dataclass(slots=True)
class GeminiClient:
    api_key: str
    model: str = DEFAULT_GEMINI_MODEL
    timeout: float = 60.0

    def generate_json(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 2048,
    ) -> Dict[str, Any]:
        text = self._generate_text(
            prompt,
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:  # noqa: PERF203 - richer message is helpful for ops
            raise LLMError(f"Gemini returned non-JSON output: {text!r}") from exc

    def _generate_text(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str] = None,
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        params = {"key": self.api_key}
        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": "application/json",
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        attempt = 0
        while True:
            attempt += 1
            try:
                response = requests.post(url, params=params, json=payload, timeout=self.timeout)
            except requests.RequestException as exc:  # noqa: PERF203
                if attempt >= 3:
                    raise LLMError(f"Gemini transport error: {exc}") from exc
                backoff = min(2 ** (attempt - 1), 30)
                LOGGER.warning(
                    "Gemini transport error (attempt %s): %s; retrying in %ss",
                    attempt,
                    exc,
                    backoff,
                )
                time.sleep(backoff)
                continue

            if response.status_code == 429:
                data = _safe_json(response)
                if attempt >= 3:
                    raise LLMError(f"Gemini quota exceeded: {data.get('error', response.text)}")
                delay = _extract_retry_delay(data) or min(5 * attempt, 60)
                LOGGER.warning(
                    "Gemini quota hit (attempt %s); sleeping for %ss before retrying.",
                    attempt,
                    delay,
                )
                time.sleep(delay)
                continue

            try:
                response.raise_for_status()
            except requests.HTTPError as exc:  # noqa: PERF203
                if attempt >= 3:
                    raise LLMError(f"Gemini request failed: {response.text}") from exc
                backoff = min(2 ** attempt, 30)
                LOGGER.warning(
                    "Gemini HTTP error %s on attempt %s; retrying in %ss.",
                    response.status_code,
                    attempt,
                    backoff,
                )
                time.sleep(backoff)
                continue

            data = _safe_json(response)
            if "error" in data:
                message = data["error"].get("message", "unknown error")
                raise LLMError(f"Gemini API error: {message}")
            try:
                candidates = data["candidates"]
                if not candidates:
                    raise KeyError("empty candidates")
                content = candidates[0]["content"]
                parts = content.get("parts", [])
            except KeyError as exc:
                raise LLMError(f"Gemini response missing expected fields: {data}") from exc
            text_parts = [part.get("text", "") for part in parts if "text" in part]
            text = "".join(text_parts).strip()
            if not text:
                raise LLMError(f"Gemini returned empty content: {data}")
            return text


@dataclass(slots=True)
class OpenRouterClient:
    api_key: str
    model: str = DEFAULT_OPENROUTER_MODEL
    timeout: float = 60.0
    site_url: str = "https://weekly-newsletter.local"
    app_name: str = "Weekly Newsletter"

    def generate_json(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 2048,
    ) -> Dict[str, Any]:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.app_name,
        }
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "response_format": {"type": "json_object"},
        }

        attempt = 0
        while True:
            attempt += 1
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            except requests.RequestException as exc:  # noqa: PERF203
                if attempt >= 3:
                    raise LLMError(f"OpenRouter transport error: {exc}") from exc
                backoff = min(2 ** (attempt - 1), 30)
                LOGGER.warning(
                    "OpenRouter transport error (attempt %s): %s; retrying in %ss",
                    attempt,
                    exc,
                    backoff,
                )
                time.sleep(backoff)
                continue

            if response.status_code == 429:
                data = _safe_json(response)
                if attempt >= 3:
                    raise LLMError(f"OpenRouter quota exceeded: {data}")
                delay = _extract_retry_after(response, data) or min(5 * attempt, 60)
                LOGGER.warning(
                    "OpenRouter quota hit (attempt %s); sleeping for %ss before retrying.",
                    attempt,
                    delay,
                )
                time.sleep(delay)
                continue

            try:
                response.raise_for_status()
            except requests.HTTPError as exc:  # noqa: PERF203
                if attempt >= 3:
                    raise LLMError(f"OpenRouter request failed: {response.text}") from exc
                backoff = min(2 ** attempt, 30)
                LOGGER.warning(
                    "OpenRouter HTTP error %s on attempt %s; retrying in %ss.",
                    response.status_code,
                    attempt,
                    backoff,
                )
                time.sleep(backoff)
                continue

            data = _safe_json(response)
            if "error" in data:
                raise LLMError(f"OpenRouter API error: {data['error']}")
            try:
                choices = data["choices"]
                if not choices:
                    raise KeyError("empty choices")
                message = choices[0]["message"]
                content = message.get("content")
            except KeyError as exc:
                raise LLMError(f"OpenRouter response missing expected fields: {data}") from exc
            if isinstance(content, list):
                # Some models may return structured content parts similar to Gemini.
                text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
                text = "".join(text_parts).strip()
            else:
                text = str(content).strip()
            if not text:
                raise LLMError(f"OpenRouter returned empty content: {data}")
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:  # noqa: PERF203
                raise LLMError(f"OpenRouter returned non-JSON output: {text!r}") from exc


@lru_cache(maxsize=1)
def get_llm_client() -> GeminiClient | OpenRouterClient:
    """Create (and cache) an LLM client based on environment configuration."""

    _load_dotenv_if_needed()
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    if provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise LLMError("Environment variable OPENROUTER_API_KEY is required for LLM_PROVIDER=openrouter")
        model = os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
        timeout = float(os.getenv("OPENROUTER_TIMEOUT", "60"))
        site_url = os.getenv("OPENROUTER_SITE_URL", "https://weekly-newsletter.local")
        app_name = os.getenv("OPENROUTER_APP_NAME", "Weekly Newsletter")
        return OpenRouterClient(
            api_key=api_key,
            model=model,
            timeout=timeout,
            site_url=site_url,
            app_name=app_name,
        )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise LLMError("Environment variable GEMINI_API_KEY is required (or set LLM_PROVIDER=openrouter)")
    model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    timeout = float(os.getenv("GEMINI_TIMEOUT", "60"))
    return GeminiClient(api_key=api_key, model=model, timeout=timeout)


_DOTENV_LOADED = False


def _load_dotenv_if_needed() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    candidates = [Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"]
    for path in candidates:
        if not path.exists():
            continue
        try:
            _apply_dotenv(path)
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Failed to load .env from %s: %s", path, exc)


def _apply_dotenv(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        cleaned = _strip_quotes(value.strip())
        os.environ[key] = cleaned


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _safe_json(response: requests.Response) -> Dict[str, Any]:
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}


def _extract_retry_delay(data: Dict[str, Any]) -> Optional[float]:
    details = data.get("error", {}).get("details", [])
    for detail in details:
        if not isinstance(detail, dict):
            continue
        if detail.get("@type") != "type.googleapis.com/google.rpc.RetryInfo":
            continue
        retry_delay = detail.get("retryDelay")
        if isinstance(retry_delay, str):
            parsed = _parse_duration_seconds(retry_delay)
            if parsed is not None:
                return parsed
    return None


def _extract_retry_after(response: requests.Response, data: Dict[str, Any]) -> Optional[float]:
    header_retry = response.headers.get("retry-after")
    if header_retry:
        parsed = _parse_duration_seconds(header_retry)
        if parsed is not None:
            return parsed
    error = data.get("error")
    if isinstance(error, dict):
        retry = error.get("retry_after")
        if isinstance(retry, (int, float)):
            return float(retry)
        if isinstance(retry, str):
            parsed = _parse_duration_seconds(retry)
            if parsed is not None:
                return parsed
    return None


def _parse_duration_seconds(raw: str) -> Optional[float]:
    raw = raw.strip()
    if raw.endswith("s"):
        raw = raw[:-1]
    try:
        return float(raw)
    except ValueError:
        return None


__all__ = ["LLMError", "GeminiClient", "OpenRouterClient", "get_llm_client"]
