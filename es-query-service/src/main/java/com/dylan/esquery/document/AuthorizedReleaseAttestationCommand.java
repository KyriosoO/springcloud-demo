package com.dylan.esquery.document;

import java.time.Instant;

/** 仅供 07 governance use case 构造的内部授权命令。 */
public record AuthorizedReleaseAttestationCommand(
        String physicalIndex,
        String manifestDigest,
        String validationReportRef,
        String validationReportDigest,
        Instant deadline) {
    public AuthorizedReleaseAttestationCommand {
        if (physicalIndex == null || !physicalIndex.startsWith("agent-doc-")
                || manifestDigest == null || !manifestDigest.matches("[0-9a-f]{64}")
                || validationReportRef == null || validationReportRef.isBlank()
                || validationReportDigest == null || !validationReportDigest.matches("[0-9a-f]{64}")
                || deadline == null) throw new IllegalArgumentException("release attestation command invalid");
    }
}
