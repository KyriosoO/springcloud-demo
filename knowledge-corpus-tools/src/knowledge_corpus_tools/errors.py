from __future__ import annotations


class CorpusError(RuntimeError):
    """Base fail-closed error."""


class ContractError(CorpusError):
    """Strict data contract violation."""


class SafetyError(CorpusError):
    """Input or remote asset violates a safety boundary."""


class StateConflict(CorpusError):
    """Observed mutable state differs from the frozen precondition."""

