from __future__ import annotations


class KnowledgeError(ValueError):
    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class KnowledgeConfigurationError(KnowledgeError):
    pass


class KnowledgeInputError(KnowledgeError):
    pass


class KnowledgeStageContractError(KnowledgeError):
    pass

