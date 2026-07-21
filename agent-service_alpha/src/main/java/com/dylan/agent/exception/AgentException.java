package com.dylan.agent.exception;

import org.springframework.http.HttpStatus;

import com.dylan.agent.api.enums.AgentErrorCode;

/**
 * Agent 统一异常基类。
 * 只接受安全消息，原始 cause 仅用于服务端堆栈。
 */
public class AgentException extends RuntimeException {

    private final AgentErrorCode errorCode;
    private final HttpStatus httpStatus;
    private final String safeMessage;
    private String conversationId;
    private String turnId;

    public AgentException(AgentErrorCode errorCode, HttpStatus httpStatus, String safeMessage) {
        super(safeMessage);
        this.errorCode = errorCode;
        this.httpStatus = httpStatus;
        this.safeMessage = safeMessage;
    }

    public AgentException(AgentErrorCode errorCode, HttpStatus httpStatus, String safeMessage, Throwable cause) {
        super(safeMessage, cause);
        this.errorCode = errorCode;
        this.httpStatus = httpStatus;
        this.safeMessage = safeMessage;
    }

    /** 设置异常上下文（conversationId + turnId），用于日志和错误响应。 */
    public AgentException withContext(String conversationId, String turnId) {
        this.conversationId = conversationId;
        this.turnId = turnId;
        return this;
    }

    public AgentErrorCode getErrorCode() { return errorCode; }
    public HttpStatus getHttpStatus() { return httpStatus; }
    public String getSafeMessage() { return safeMessage; }
    public String getConversationId() { return conversationId; }
    public String getTurnId() { return turnId; }
}
