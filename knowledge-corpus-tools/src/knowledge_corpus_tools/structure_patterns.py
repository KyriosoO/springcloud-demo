"""Shared text structure patterns, independent of document parser dependencies."""

import re

CLAUSE_PATTERN = re.compile(r"^(第[一二三四五六七八九十百千0-9]+条)\s*")
