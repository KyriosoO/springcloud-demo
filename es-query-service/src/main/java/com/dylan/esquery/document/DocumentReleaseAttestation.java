package com.dylan.esquery.document;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;

/** 07 PASSED report 的 one-time immutable 运行投影。 */
public record DocumentReleaseAttestation(
        String validationReportRef,
        String validationReportDigest,
        String manifestDigest,
        Instant attestedAt,
        String attestationDigest) {
    public DocumentReleaseAttestation {
        if (validationReportRef == null || validationReportRef.isBlank()
                || !digest(validationReportDigest) || !digest(manifestDigest)
                || attestedAt == null || !digest(attestationDigest)
                || !attestationDigest.equals(canonicalDigest(
                validationReportRef, validationReportDigest, manifestDigest))) {
            throw new IllegalArgumentException("document release attestation invalid");
        }
    }

    public static String canonicalDigest(
            String validationReportRef,
            String validationReportDigest,
            String manifestDigest) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for (String value : new String[]{"ATTEST-1", validationReportRef, validationReportDigest, manifestDigest}) {
                byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
                digest.update(ByteBuffer.allocate(Integer.BYTES).putInt(bytes.length).array());
                digest.update(bytes);
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (Exception ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }

    private static boolean digest(String value) {
        return value != null && value.matches("[0-9a-f]{64}");
    }
}
