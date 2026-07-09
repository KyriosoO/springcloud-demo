package com.dylan.esquery.service;

import com.dylan.esquery.api.model.RebuildTask;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.TreeMap;

/** 本地文档索引验证报告，不保存正文、向量或权限表达式。 */
public record DocumentIndexValidationReport(
        String validationReportId,
        String taskId,
        String alias,
        String targetIndex,
        String domain,
        String materialType,
        String retrievalProfile,
        String profileVersion,
        String indexVersion,
        String goldSetVersion,
        String validatorVersion,
        String mappingHash,
        String sampleHash,
        String aclProbeHash,
        String embeddingModel,
        int embeddingDimension,
        String citationFieldStatus,
        double minimumTopKHitRate,
        double actualTopKHitRate,
        int permissionLeakCount,
        boolean rollbackReady,
        Map<String, Double> metrics,
        List<String> blockingReasons,
        String status,
        String validationDigest,
        Instant createdAt) {

    static DocumentIndexValidationReport localPassed(RebuildTask task, String validatorVersion) {
        Objects.requireNonNull(task, "task must not be null");
        DocumentRetrievalValidationRequest request = new DocumentRetrievalValidationRequest(
                task.getTaskId(),
                "LOCAL",
                "LOCAL",
                "LOCAL",
                "LOCAL",
                task.getIndex(),
                value(task.getTargetIndex()),
                "LOCAL_SMOKE_V1",
                true,
                true,
                true,
                1.0d,
                1.0d,
                0,
                List.of(),
                Map.of());
        return passed(task, validatorVersion, request);
    }

    static DocumentIndexValidationReport passed(
            RebuildTask task,
            String validatorVersion,
            DocumentRetrievalValidationRequest request) {
        Objects.requireNonNull(task, "task must not be null");
        Objects.requireNonNull(request, "request must not be null");
        String reportId = sha256(String.join("|",
                value(request.indexVersion()),
                value(request.profileVersion()),
                value(request.goldSetVersion()),
                validatorVersion)).substring(0, 24);
        String metricsDigestText = stableMetricsText(request.metrics());
        String mappingHash = sha256("mapping|" + value(task.getTargetIndex()) + "|" + value(request.indexVersion()));
        String sampleHash = sha256("sample|" + task.getTotalIndexed() + "|" + value(task.getLastCursor())
                + "|" + value(request.goldSetVersion()));
        String aclProbeHash = sha256("acl|" + value(task.getIndex()) + "|" + value(task.getTargetIndex())
                + "|" + request.permissionLeakCount());
        List<String> blockingReasons = List.copyOf(validationFailures(request));
        String digest = sha256(String.join("|",
                validatorVersion,
                reportId,
                value(task.getTaskId()),
                value(task.getIndex()),
                value(task.getTargetIndex()),
                value(request.domain()),
                value(request.materialType()),
                value(request.retrievalProfile()),
                value(request.profileVersion()),
                value(request.indexVersion()),
                value(request.goldSetVersion()),
                value(task.getType()),
                value(task.getStatus()),
                String.valueOf(task.getTotalIndexed()),
                value(task.getLastCursor()),
                mappingHash,
                sampleHash,
                aclProbeHash,
                "LOCAL",
                "0",
                String.valueOf(request.minimumTopKHitRate()),
                String.valueOf(request.actualTopKHitRate()),
                String.valueOf(request.permissionLeakCount()),
                String.valueOf(request.rollbackDryRunReady()),
                metricsDigestText,
                String.join(",", blockingReasons),
                "PASSED"));
        return new DocumentIndexValidationReport(
                reportId,
                task.getTaskId(),
                task.getIndex(),
                task.getTargetIndex(),
                request.domain(),
                request.materialType(),
                request.retrievalProfile(),
                request.profileVersion(),
                request.indexVersion(),
                request.goldSetVersion(),
                validatorVersion,
                mappingHash,
                sampleHash,
                aclProbeHash,
                "LOCAL",
                0,
                "PASSED",
                request.minimumTopKHitRate(),
                request.actualTopKHitRate(),
                request.permissionLeakCount(),
                request.rollbackDryRunReady(),
                Map.copyOf(request.metrics() == null ? Map.of() : request.metrics()),
                blockingReasons,
                "PASSED",
                digest,
                Instant.now());
    }

    static List<String> validationFailures(DocumentRetrievalValidationRequest request) {
        java.util.ArrayList<String> failures = new java.util.ArrayList<>();
        if (!request.schemaValidated()) {
            failures.add("SCHEMA_VALIDATION_FAILED");
        }
        if (!request.aclValidated()) {
            failures.add("ACL_VALIDATION_FAILED");
        }
        if (!request.rollbackDryRunReady()) {
            failures.add("ROLLBACK_DRY_RUN_FAILED");
        }
        if (request.permissionLeakCount() > 0) {
            failures.add("PERMISSION_LEAK");
        }
        if (request.actualTopKHitRate() < request.minimumTopKHitRate()) {
            failures.add("GOLD_QUERY_HIT_RATE_LOW");
        }
        return List.copyOf(failures);
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

    private static String stableMetricsText(Map<String, Double> metrics) {
        if (metrics == null || metrics.isEmpty()) {
            return "{}";
        }
        return new TreeMap<>(metrics).toString();
    }
}
