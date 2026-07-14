package com.dylan.documentprovider;

import com.dylan.agent.adapter.api.document.provider.DocumentProviderWireError;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
final class DocumentProviderExceptionHandler {
    @ExceptionHandler(ProviderAdapterException.class)
    ResponseEntity<DocumentProviderWireError> handle(ProviderAdapterException ex) {
        return ResponseEntity.status(HttpStatus.CONFLICT).body(new DocumentProviderWireError(
                "DPW-1", ex.operationId, ex.operationType, ex.requestDigest, ex.code, ex.diagnosticId));
    }
}
