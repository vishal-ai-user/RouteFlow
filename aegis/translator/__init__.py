"""AEGIS Translator — Protocol translation between client payloads and internal models."""

from aegis.translator.request import translate_request
from aegis.translator.response import translate_response

__all__ = [
    "translate_request",
    "translate_response",
]
