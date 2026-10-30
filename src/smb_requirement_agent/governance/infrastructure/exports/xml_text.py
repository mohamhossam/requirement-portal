"""Text that Office Open XML cannot carry.

XML 1.0 forbids most C0 control characters. openpyxl and python-docx both fail on them,
openpyxl by writing a workbook Excel repairs, lxml with a bare ValueError that would surface
as a 500. Each exporter checks here first and raises its own format error instead.
"""

from __future__ import annotations

import re
from collections.abc import Callable

ILLEGAL_XML = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


def require_xml_safe(value: str, error: Callable[[], Exception]) -> str:
    if ILLEGAL_XML.search(value):
        raise error()
    return value
