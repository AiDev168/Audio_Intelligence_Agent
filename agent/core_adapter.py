"""Adapter between the Ai_cheshm host capability container and Media Core."""
from __future__ import annotations

from typing import Any


class CoreCapabilityError(RuntimeError):
    """Raised when the host cannot satisfy a requested Core capability."""


class CoreCapabilityGateway:
    """Resolve and execute provider-neutral Media Core capabilities.

    Preferred host contract:
        context.capabilities["media_intelligence_core"]

    The injected service may expose an execute method itself, or it may be a raw
    Media Core CapabilityContainer. Provider selection stays outside the Agent
    and is read from host execution metadata when a raw container is used.
    """

    def __init__(self, service: Any, context: Any):
        self.service = service
        self.context = context
        self._core = None
        self._executor = None
        self._cancellation = None

    @property
    def core(self):
        if self._core is None:
            try:
                import media_intelligence as core
            except ImportError as exc:
                raise CoreCapabilityError(
                    "Ai_Media_Intelligence_Core is not installed in the Agent runtime."
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
            result = service_execute(
                capability,
                media,
                options=payload,
                host_context=self.context,
            )
            if hasattr(result, "__await__"):
                return await result
            return result

        container = self.service
        try:
            from media_intelligence import CapabilityExecutor, CancellationToken, ExecutionRequest

            if self._executor is None:
                self._cancellation = CancellationToken()
                self._executor = CapabilityExecutor(container)

            provider = self._select_provider(container, capability)
            request = ExecutionRequest(
                capability=capability,
                media=media,
                provider=provider,
                correlation_id=str(self.context.execution_id),
                options=payload,
            )
            return await self._executor.execute(request, cancellation=self._cancellation)
        except CoreCapabilityError:
            raise
        except Exception as exc:
            raise CoreCapabilityError(
                f"Media Core capability '{capability}' could not be executed."
            ) from exc

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
