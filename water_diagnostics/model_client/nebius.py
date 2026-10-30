"""Small OpenAI-compatible HTTP client. Never log credentials or API bodies."""

from urllib.parse import urlsplit

import httpx

from water_diagnostics.config import DEFAULT_MODEL, Settings
from water_diagnostics.model_client.budget import BudgetError, CostGuard


class ModelClientError(RuntimeError):
    """Safe-to-display error, with no provider response body or authentication."""


class NebiusClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None,
                 budget: CostGuard | None = None):
        if not settings.nebius_api_key.get_secret_value().strip():
            raise ModelClientError("Nebius key is missing. Enter NEBIUS_API_KEY in the local .env file.")
        endpoint = urlsplit(settings.nebius_base_url)
        if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
            raise ModelClientError("Nebius endpoint must be a plain HTTPS URL without embedded credentials or query parameters.")
        self.model = settings.nebius_model
        # Offline mocked transports do not bill and need no persistent ledger.
        self.budget = budget or (CostGuard() if transport is None else None)
        self._http = httpx.Client(
            base_url=settings.nebius_base_url.rstrip("/") + "/",
            headers={"Authorization": "Bearer " + settings.nebius_api_key.get_secret_value()},
            timeout=httpx.Timeout(90.0, connect=10.0), follow_redirects=False, transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def complete(self, messages: list[dict], tools: list[dict] | None = None,
                 max_tokens: int = 4096) -> dict:
        payload = {"model": self.model, "messages": messages, "temperature": 0,
                   "max_tokens": max_tokens}
        if self.model == DEFAULT_MODEL:
            # NVIDIA documents direct tool calling with thinking disabled. This
            # avoids exhausting a small response budget on a hidden reasoning
            # trace. The Nebius endpoint was verified with this parameter.
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        if tools:
            # At the report stage only submit_report is offered. An explicit
            # choice avoids another tool-selection/free-text generation step.
            choice = ({"type": "function", "function": {"name": tools[0]["function"]["name"]}}
                      if len(tools) == 1 else "auto")
            payload.update(tools=tools, tool_choice=choice)
        try:
            reservation = self.budget.reserve(self.model, payload) if self.budget else None
        except BudgetError as error:
            raise ModelClientError(str(error)) from None
        try:
            response = self._http.post("chat/completions", json=payload)
        except httpx.TimeoutException:
            raise ModelClientError("Nebius request timed out (10-second connection / 90-second response limit). No automatic retry; usage may still be billed.") from None
        except httpx.HTTPError:
            raise ModelClientError("Nebius connection failed before a usable response arrived. No automatic retry; check connectivity and the configured endpoint.") from None
        if response.status_code != 200:
            raise ModelClientError(f"Nebius returned HTTP {response.status_code}; check credentials, model availability and credit balance.")
        try:
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError()
            if self.budget:
                self.budget.record_usage(reservation, body.get("usage"))
            choice = body["choices"][0]
            message = choice["message"]
            if choice.get("finish_reason") == "length":
                raise ModelClientError("Nebius response reached its token limit; no partial report was accepted.")
            if not isinstance(message, dict) or message.get("role") != "assistant":
                raise ValueError()
            # Deliberately omit reasoning text, provider metadata and raw logs.
            return {"role": "assistant", "content": message.get("content"),
                    **({"tool_calls": message["tool_calls"]} if message.get("tool_calls") else {})}
        except (ValueError, KeyError, IndexError, TypeError):
            raise ModelClientError("Nebius returned an unexpected response format.") from None
        except BudgetError:
            raise ModelClientError("The response arrived but usage could not be recorded; review the applicable spending guard before another request.") from None

    def ping(self) -> None:
        """One short request; do not print the returned model text."""
        message = self.complete([{"role": "user", "content": "Reply with OK only."}], max_tokens=256)
        if not isinstance(message.get("content"), str) or not message["content"].strip():
            raise ModelClientError("Nebius answered, but supplied no visible text for the connection check.")
