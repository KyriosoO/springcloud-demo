package com.dylan.esquery.document;

import java.time.Instant;

/** 07 PASSED report 的 one-time immutable 运行投影。 */
public record DocumentReleaseAttestation(
        String validationReportRef,
        String validationReportDigest,
        String manifestDigest,
        Instant attestedAt,
        String attestationDigest) {
}
