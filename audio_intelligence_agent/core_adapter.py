"""Adapter between the Ai_cheshm host capability container and Media Core."""

from __future__ import annotations

import asyncio
from typing import Any


class CoreCapabilityError(RuntimeError):
    """Raised when the host cannot satisfy a requested Core capability."""

    def __init__(
        self,
        message: str,
        *,
        capability: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.capability = capability
        self.cause_type = type(cause).__name__ if cause is not None else None
        self.detail = self._safe_detail(cause or self)

    @staticmethod
    def _safe_detail(exc: BaseException) -> str:
        detail = str(exc).strip() or type(exc).__name__
        replacements = (
            ("Authorization: Bearer ", "Authorization: Bearer [REDACTED]"),
            ("authorization=Bearer ", "authorization=Bearer [REDACTED]"),
            ("api_key=", "api_key=[REDACTED]"),
            ("api-key=", "api-key=[REDACTED]"),
            ("token=", "token=[REDACTED]"),
        )
        for old_value, new_value in replacements:
            if old_value in detail:
                prefix, _, suffix = detail.partition(old_value)
                suffix = suffix.split()[0] if suffix else ""
                detail = prefix + new_value + suffix
        return detail[:1200]


class CoreCapabilityGateway:
    """Resolve and execute provider-neutral Media Core capabilities.

    The preferred host service contract is a platform-injected
    context.capabilities["media_intelligence_core"] facade. A raw Media
    Core CapabilityContainer is also supported for local/integration use.
    """

    def __init__(self, service: Any, context: Any):
        self.service = service
        self.context = context
        self._core = None
        self._executor = None
        self._cancellation = None

    @property
    def core(self):
        if self._core is not None:
            return self._core

        try:
            host_core = getattr(self.service, "core", None)
        except Exception as exc:
            raise CoreCapabilityError(
                "Ai_Media_Intelligence_Core could not be resolved by the Host.",
                cause=exc,
            ) from exc

        if host_core is not None:
            self._core = host_core
            return self._core

        try:
            import media_intelligence as core
        except ImportError as exc:
            raise CoreCapabilityError(
                "Ai_Media_Intelligence_Core is not available in the Host or Agent runtime.",
                cause=exc,
            ) from exc

        self._core = core
        return self._core

    async def execute(
        self,
        capability: str,
        media: Any,
        *,
        options: dict[str, Any] | None = None,
    ) -> Any:
        payload = dict(options or {})

        service_execute = getattr(self.service, "execute", None)
        if callable(service_execute):
            try:
                result = service_execute(
                    capability,
                    media,
                    options=payload,
                    host_context=self.context,
                )
                if hasattr(result, "__await__"):
                    return await result
                return result
            except CoreCapabilityError:
                raise
            except Exception as exc:
                raise CoreCapabilityError(
                    f"Media Core capability '{capability}' could not be executed.",
                    capability=capability,
                    cause=exc,
                ) from exc

        try:
            from media_intelligence import CancellationToken, CapabilityExecutor, ExecutionRequest

            if self._executor is None:
                self._cancellation = CancellationToken()
                self._executor = CapabilityExecutor(self.service)

            provider = self._select_provider(self.service, capability)
            request = ExecutionRequest(
                capability=capability,
                media=media,
                provider=provider,
                correlation_id=str(self.context.execution_id),
                options=payload,
            )

            watcher = asyncio.create_task(self._watch_host_cancellation())
            try:
                return await self._executor.execute(
                    request,
                    cancellation=self._cancellation,
                )
            finally:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
        except CoreCapabilityError:
            raise
        except Exception as exc:
            raise CoreCapabilityError(
                f"Media Core capability '{capability}' could not be executed.",
                capability=capability,
                cause=exc,
            ) from exc

    async def _watch_host_cancellation(self) -> None:
        if self._cancellation is None:
            return

        while not self.context.is_cancelled():
            await asyncio.sleep(0.1)

        self._cancellation.cancel()

    def _select_provider(self, container: Any, capability: str) -> str | None:
        try:
            capability_obj = container.capabilities.get(capability)
        except Exception as exc:
            raise CoreCapabilityError(
                f"Media Core capability '{capability}' is not registered."
            ) from exc

        if capability in {
            "speaker-turn-analysis",
            "temporal-transcript-search",
            "audio-evidence",
        }:
            return None

        policy = self.context.metadata.get("media_intelligence_provider_policy", {})
        selected = policy.get(capability)
        if selected:
            return str(selected)

        try:
            providers = container.providers.providers_for(capability)
        except Exception:
            providers = ()

        if len(providers) == 1:
            return providers[0]

        provider_id = getattr(capability_obj, "provider_id", None)
        if provider_id:
            return str(provider_id)

        raise CoreCapabilityError(
            f"No provider policy is configured for Media Core capability '{capability}'."
        )


__all__ = ["CoreCapabilityError", "CoreCapabilityGateway"]
