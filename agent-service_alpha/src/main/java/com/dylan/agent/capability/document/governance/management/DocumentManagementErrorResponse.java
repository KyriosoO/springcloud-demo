package com.dylan.agent.capability.document.governance.management;

import java.util.Objects;

public record DocumentManagementErrorResponse(
        String contractVersion, DocumentManagementErrorCode code, String diagnosticId) {
    public DocumentManagementErrorResponse {
        if (!"DMW-1".equals(contractVersion)) throw new IllegalArgumentException("unsupported management contract");
        Objects.requireNonNull(code, "code must not be null");
        if (diagnosticId == null || !diagnosticId.matches("[A-Za-z0-9-]{8,80}")) {
            throw new IllegalArgumentException("diagnosticId must be opaque safe text");
        }
    }
}
