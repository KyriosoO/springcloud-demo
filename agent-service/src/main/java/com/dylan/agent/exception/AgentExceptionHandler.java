package com.dylan.agent.exception;

import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import com.dylan.agent.api.enums.AgentErrorCode;
import com.dylan.agent.api.enums.AgentResponseType;
import com.dylan.agent.api.response.AgentChatResponse;

/**
 * Agent 全局异常处理器。
 * 所有响应均为统一 AgentChatResponse(type=ERROR)，不返回堆栈。
 */
@RestControllerAdvice
public class AgentExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(AgentExceptionHandler.class);

    @ExceptionHandler(AgentException.class)
    public ResponseEntity<AgentChatResponse> handleAgent(AgentException ex) {
        log.warn("Agent exception: errorCode={}, conversationId={}, turnId={}",
                ex.getErrorCode(), ex.getConversationId(), ex.getTurnId());
        AgentChatResponse resp = buildError(ex.getConversationId(), ex.getTurnId(),
                ex.getErrorCode(), ex.getSafeMessage());
        return ResponseEntity.status(ex.getHttpStatus()).body(resp);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<AgentChatResponse> handleValidation(MethodArgumentNotValidException ex) {
        AgentChatResponse resp = buildError(null, null,
                AgentErrorCode.AGENT_INVALID_REQUEST, "请求参数不合法。");
        return ResponseEntity.badRequest().body(resp);
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<AgentChatResponse> handleUnreadable(HttpMessageNotReadableException ex) {
        AgentChatResponse resp = buildError(null, null,
                AgentErrorCode.AGENT_INVALID_REQUEST, "请求体无法解析。");
        return ResponseEntity.badRequest().body(resp);
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<AgentChatResponse> handleUnknown(Exception ex) {
        String ref = UUID.randomUUID().toString().substring(0, 8);
        log.error("Unhandled exception ref={}", ref, ex);
        AgentChatResponse resp = buildError(null, null,
                AgentErrorCode.AGENT_INTERNAL_ERROR, "系统内部错误，请稍后重试。ref=" + ref);
        return ResponseEntity.internalServerError().body(resp);
    }

    private AgentChatResponse buildError(String conversationId, String turnId,
                                         AgentErrorCode errorCode, String message) {
        AgentChatResponse resp = new AgentChatResponse();
        resp.setConversationId(conversationId);
        resp.setTurnId(turnId);
        resp.setType(AgentResponseType.ERROR);
        resp.setMessage(message);
        resp.setSummary(message);
        resp.setErrorCode(errorCode);
        return resp;
    }
}
