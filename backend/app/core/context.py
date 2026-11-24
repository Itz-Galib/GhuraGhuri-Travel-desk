"""Request-scoped context values (request id) shared by logging and errors."""

from contextvars import ContextVar

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
