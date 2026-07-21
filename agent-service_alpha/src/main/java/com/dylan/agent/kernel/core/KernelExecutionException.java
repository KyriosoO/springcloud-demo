package com.dylan.agent.kernel.core;

import com.dylan.agent.invocation.model.KernelErrorCode;

import java.util.Objects;

/** 执行内核内部使用的安全失败信号，携带可对用户展示的安全消息。 */
public class KernelExecutionException extends RuntimeException {

    private final KernelErrorCode errorCode;
    private final String safeMessage;

    public KernelExecutionException(KernelErrorCode errorCode, String safeMessage) {
        super(Objects.requireNonNull(safeMessage, "safeMessage must not be null"));
        this.errorCode = Objects.requireNonNull(errorCode, "errorCode must not be null");
        this.safeMessage = safeMessage;
    }

    public KernelErrorCode errorCode() {
        return errorCode;
    }

    public String safeMessage() {
        return safeMessage;
    }
}
