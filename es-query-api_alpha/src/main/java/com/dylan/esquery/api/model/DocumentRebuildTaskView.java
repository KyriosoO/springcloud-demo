package com.dylan.esquery.api.model;

import java.time.Instant;

/** 对管理 caller 可见的安全 rebuild task 投影。 */
public record DocumentRebuildTaskView(
        String taskId,
        DocumentCorpusKeyDto corpusKey,
        String targetPhysicalIndexSafeRef,
        DocumentRebuildStatus status,
        long documentsRead,
        long chunksIndexed,
        String failureCode,
        String diagnosticId,
        Instant createdAt,
        Instant updatedAt) {}
