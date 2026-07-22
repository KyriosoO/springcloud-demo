package com.dylan.baseline.agent.security.migration;

import com.dylan.baseline.agent.security.authorization.LegacyAuthFieldView;
import java.util.Optional;

/** 一次字段迁移裁决的低敏感观察结果；不包含主体、tenant或规则正文。 */
public record AuthFieldMigrationResolution(
        LegacyAuthFieldView effectiveFields,
        Optional<AuthFieldMigrationDiffClass> observedDiffClass,
        boolean legacyUsedForDecision) {

    public AuthFieldMigrationResolution {
        if (effectiveFields == null || observedDiffClass == null) {
            throw new IllegalArgumentException("migration resolution parts must not be null");
        }
    }
}
