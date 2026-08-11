from __future__ import annotations

from .protocol import PUBLIC_ERROR_CODES


class PublicPolicyError(RuntimeError):
    """An evaluator-side error whose string is safe to expose."""

    def __init__(self, code: str):
        if code not in PUBLIC_ERROR_CODES:
            code = "POLICY_PROTOCOL_ERROR"
        self.code = code
        super().__init__(code)


def public_error_code(error: BaseException) -> str:
    if isinstance(error, PublicPolicyError):
        return error.code
    return "POLICY_PROTOCOL_ERROR"
