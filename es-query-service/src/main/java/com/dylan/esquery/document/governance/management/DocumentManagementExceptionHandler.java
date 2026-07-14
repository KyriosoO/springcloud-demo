package com.dylan.esquery.document.governance.management;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.http.converter.HttpMessageNotReadableException;
import java.util.UUID;

@RestControllerAdvice(assignableTypes=DocumentIndexManagementController.class)
public final class DocumentManagementExceptionHandler {
    @ExceptionHandler(AccessDeniedException.class) ResponseEntity<DocumentManagementErrorResponse> denied(AccessDeniedException ex){boolean authentication=ex.getMessage()!=null&&ex.getMessage().contains("authentication");return response(authentication?HttpStatus.UNAUTHORIZED:HttpStatus.FORBIDDEN,authentication?DocumentManagementErrorCode.AUTHENTICATION_REQUIRED:DocumentManagementErrorCode.SCOPE_REQUIRED);}
    @ExceptionHandler(SecurityException.class) ResponseEntity<DocumentManagementErrorResponse> approval(SecurityException ex){return response(HttpStatus.FORBIDDEN,ex.getMessage()!=null&&ex.getMessage().contains("unavailable")?DocumentManagementErrorCode.APPROVAL_REQUIRED:DocumentManagementErrorCode.APPROVAL_INVALID);}
    @ExceptionHandler({IllegalArgumentException.class,HttpMessageNotReadableException.class,MethodArgumentNotValidException.class}) ResponseEntity<DocumentManagementErrorResponse> invalid(Exception ex){return response(HttpStatus.BAD_REQUEST,DocumentManagementErrorCode.INVALID_REQUEST);}
    @ExceptionHandler(IllegalStateException.class) ResponseEntity<DocumentManagementErrorResponse> state(IllegalStateException ex){
        String message=ex.getMessage()==null?"":ex.getMessage();
        if(message.contains("idempotency"))return response(HttpStatus.CONFLICT,DocumentManagementErrorCode.IDEMPOTENCY_CONFLICT);
        if(message.contains("expected current"))return response(HttpStatus.CONFLICT,DocumentManagementErrorCode.EXPECTED_STATE_MISMATCH);
        if(message.contains("PASSED")||message.contains("rollback target"))return response(HttpStatus.CONFLICT,DocumentManagementErrorCode.REPORT_NOT_CURRENT);
        if(message.contains("emergency"))return response(HttpStatus.CONFLICT,DocumentManagementErrorCode.EMERGENCY_BLOCKED);
        if(message.contains("deadline"))return response(HttpStatus.REQUEST_TIMEOUT,DocumentManagementErrorCode.DEADLINE_EXCEEDED);
        if(message.contains("actual state"))return response(HttpStatus.SERVICE_UNAVAILABLE,DocumentManagementErrorCode.ACTUAL_STATE_UNKNOWN);
        if(message.contains("active change")||message.contains("reconcilable"))return response(HttpStatus.CONFLICT,DocumentManagementErrorCode.CHANGE_IN_PROGRESS);
        return response(HttpStatus.SERVICE_UNAVAILABLE,DocumentManagementErrorCode.INTERNAL_UNAVAILABLE);
    }
    private static ResponseEntity<DocumentManagementErrorResponse> response(HttpStatus status,DocumentManagementErrorCode code){return ResponseEntity.status(status).body(new DocumentManagementErrorResponse("DMERR-1",code,UUID.randomUUID().toString()));}
}
