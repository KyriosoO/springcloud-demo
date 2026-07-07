package com.dylan.esquery.service;

import java.time.Instant;
import java.util.List;

/** 文档 alias 切换和回滚的脱敏审计记录。 */
public record AliasOperationAudit(
        String alias,
        String operation,
        List<String> fromIndexes,
        String toIndex,
        String taskIdPrefix,
        String digestPrefix,
        String operatorRefHash,
        String result,
        String failureReason,
        long durationMs,
        Instant createdAt) {
}
