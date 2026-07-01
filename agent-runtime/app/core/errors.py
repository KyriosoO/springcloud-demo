"""
Runtime 异常类型。
"""


class RuntimePlanError(Exception):
    """LLM 输出无法修复为合法 plan。"""
    def __init__(self, code: str, safe_message: str, request_id: str | None = None):
        self.code = code
        self.safe_message = safe_message
        self.request_id = request_id
        super().__init__(safe_message)


class RuntimeAuthError(Exception):
    """共享密钥缺失或无效。"""


class RuntimeProviderError(Exception):
    """LLM provider 返回异常。"""
    def __init__(self, message: str, request_id: str | None = None):
        self.request_id = request_id
        super().__init__(message)


class RuntimeTimeoutError(Exception):
    """LLM provider 超时。"""
    def __init__(self, message: str, request_id: str | None = None):
        self.request_id = request_id
        super().__init__(message)
