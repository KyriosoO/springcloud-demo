package com.dylan.esquery.service;

import com.dylan.esquery.api.model.RebuildTask;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Objects;

/** 本地文档索引验证报告，不保存正文、向量或权限表达式。 */
public record DocumentIndexValidationReport(
        String validationReportId,
        String taskId,
        String alias,
        String targetIndex,
        String validatorVersion,
        String mappingHash,
        String sampleHash,
        String aclProbeHash,
        String embeddingModel,
        int embeddingDimension,
        String citationFieldStatus,
        String status,
        String validationDigest,
        Instant createdAt) {

    static DocumentIndexValidationReport localPassed(RebuildTask task, String validatorVersion) {
        Objects.requireNonNull(task, "task must not be null");
        String reportId = value(task.getTaskId()) + ":" + validatorVersion;
        String mappingHash = sha256("mapping|" + value(task.getTargetIndex()));
        String sampleHash = sha256("sample|" + task.getTotalIndexed() + "|" + value(task.getLastCursor()));
        String aclProbeHash = sha256("acl|" + value(task.getIndex()) + "|" + value(task.getTargetIndex()));
        String digest = sha256(String.join("|",
                validatorVersion,
                reportId,
                value(task.getTaskId()),
                value(task.getIndex()),
                value(task.getTargetIndex()),
                value(task.getType()),
                value(task.getStatus()),
                String.valueOf(task.getTotalIndexed()),
                value(task.getLastCursor()),
                mappingHash,
                sampleHash,
                aclProbeHash,
                "LOCAL",
                "0",
                "PASSED"));
        return new DocumentIndexValidationReport(
                reportId,
                task.getTaskId(),
                task.getIndex(),
                task.getTargetIndex(),
                validatorVersion,
                mappingHash,
                sampleHash,
                aclProbeHash,
                "LOCAL",
                0,
                "PASSED",
                "PASSED",
                digest,
                Instant.now());
    }

    private static String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 not available", ex);
        }
    }

    private static String value(String value) {
        return value == null ? "" : value;
    }
}
