package com.dylan.agent.capability.document.governance.management;

import java.time.Instant;
import java.util.Optional;

public record DocumentApprovalVerificationRequest(
        DocumentManagementOperation operation,
        String unitKeyDigest,
        String expectedStateDigest,
        String targetStateDigest,
        Optional<String> validationReportId,
        String authorizationRequestDigest,
        Instant deadline) {
    public DocumentApprovalVerificationRequest {
        java.util.Objects.requireNonNull(operation);
        digest(unitKeyDigest,"unitKeyDigest"); digest(expectedStateDigest,"expectedStateDigest");
        digest(targetStateDigest,"targetStateDigest"); digest(authorizationRequestDigest,"authorizationRequestDigest");
        validationReportId=validationReportId==null?Optional.empty():validationReportId;
        java.util.Objects.requireNonNull(deadline);
    }
    private static void digest(String value,String name){if(value==null||!value.matches("[0-9a-f]{64}"))throw new IllegalArgumentException(name+" must be SHA-256 hex");}
}
