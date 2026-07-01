package com.dylan.agent.adapter.api;

/** Adapter 层异常，包含安全消息（不泄露内部细节）和可选的原始异常。 */
public class AgentAdapterException extends RuntimeException {

    private final String safeMessage;

    public AgentAdapterException(String safeMessage) {
        super(safeMessage);
        this.safeMessage = safeMessage;
    }

    public AgentAdapterException(String safeMessage, Throwable cause) {
        super(safeMessage, cause);
        this.safeMessage = safeMessage;
    }

    public String getSafeMessage() { return safeMessage; }
}
