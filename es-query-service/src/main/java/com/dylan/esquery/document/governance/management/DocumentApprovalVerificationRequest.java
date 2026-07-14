package com.dylan.esquery.document.governance.management;

import java.time.Instant;
import java.util.Optional;

public record DocumentApprovalVerificationRequest(DocumentManagementOperation operation,String unitKeyDigest,
        String expectedStateDigest,String targetStateDigest,Optional<String> validationReportId,
        String authorizationRequestDigest,Instant deadline) {}
