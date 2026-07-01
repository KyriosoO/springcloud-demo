package com.dylan.mqprocedureserver.controller;

import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * Transaction HTTP 接口的安全异常映射。
 */
@RestControllerAdvice(assignableTypes = TransactionController.class)
public class TransactionExceptionHandler {

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, String>> handleInvalidRequest(IllegalArgumentException ex) {
        return ResponseEntity.badRequest().body(Map.of(
                "code", "INVALID_TRANSACTION_SEARCH_REQUEST",
                "message", ex.getMessage()));
    }
}
