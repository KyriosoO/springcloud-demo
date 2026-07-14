package com.dylan.agent.capability.document.governance.emergency;

import com.dylan.agent.capability.document.governance.management.DocumentManagementErrorCode;
import com.dylan.agent.capability.document.governance.management.DocumentManagementErrorResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;

import java.util.UUID;

@RestControllerAdvice(assignableTypes = {DocumentEmergencyGateEvidenceController.class,DocumentEmergencyManagementController.class,
        com.dylan.agent.capability.document.governance.provider.DocumentProviderManagementController.class,
        com.dylan.agent.capability.document.governance.provider.DocumentGovernanceChangeController.class})
public class DocumentEmergencyGateEvidenceExceptionHandler {
    @ExceptionHandler(AccessDeniedException.class)
    ResponseEntity<DocumentManagementErrorResponse> denied(AccessDeniedException ex) {
        return response(HttpStatus.FORBIDDEN, ex.getMessage()!=null&&ex.getMessage().contains("authentication")
                ?DocumentManagementErrorCode.AUTHENTICATION_REQUIRED:DocumentManagementErrorCode.SCOPE_REQUIRED);
    }

    @ExceptionHandler(SecurityException.class)
    ResponseEntity<DocumentManagementErrorResponse> approvalDenied(SecurityException ex) {
        return response(HttpStatus.FORBIDDEN, ex.getMessage()!=null&&ex.getMessage().contains("unavailable")
                ?DocumentManagementErrorCode.APPROVAL_REQUIRED:DocumentManagementErrorCode.APPROVAL_INVALID);
    }

    @ExceptionHandler({IllegalArgumentException.class,HttpMessageNotReadableException.class,MethodArgumentNotValidException.class})
    ResponseEntity<DocumentManagementErrorResponse> invalid(Exception ignored) {
        return response(HttpStatus.BAD_REQUEST, DocumentManagementErrorCode.INVALID_REQUEST);
    }

    @ExceptionHandler(IllegalStateException.class)
    ResponseEntity<DocumentManagementErrorResponse> unavailable(IllegalStateException ex) {
        String message=ex.getMessage()==null?"":ex.getMessage();
        if(message.contains("idempotency"))return response(HttpStatus.CONFLICT,DocumentManagementErrorCode.IDEMPOTENCY_CONFLICT);
        if(message.contains("expected current")||message.contains("expected row")||message.contains("CAS conflict"))return response(HttpStatus.CONFLICT,DocumentManagementErrorCode.EXPECTED_STATE_MISMATCH);
        if(message.contains("PASSED")||message.contains("rollback target"))return response(HttpStatus.CONFLICT,DocumentManagementErrorCode.REPORT_NOT_CURRENT);
        if(message.contains("emergency"))return response(HttpStatus.CONFLICT,DocumentManagementErrorCode.EMERGENCY_BLOCKED);
        if(message.contains("deadline"))return response(HttpStatus.CONFLICT,DocumentManagementErrorCode.DEADLINE_EXCEEDED);
        if(message.contains("reconcilable")||message.contains("active change"))return response(HttpStatus.CONFLICT,DocumentManagementErrorCode.CHANGE_IN_PROGRESS);
        if(message.contains("actual state"))return response(HttpStatus.SERVICE_UNAVAILABLE,DocumentManagementErrorCode.ACTUAL_STATE_UNKNOWN);
        return response(HttpStatus.SERVICE_UNAVAILABLE, DocumentManagementErrorCode.INTERNAL_UNAVAILABLE);
    }

    private static ResponseEntity<DocumentManagementErrorResponse> response(
            HttpStatus status, DocumentManagementErrorCode code) {
        return ResponseEntity.status(status).body(new DocumentManagementErrorResponse(
                "DMERR-1", code, "DMERR-" + UUID.randomUUID().toString().substring(0, 12)));
    }
}
