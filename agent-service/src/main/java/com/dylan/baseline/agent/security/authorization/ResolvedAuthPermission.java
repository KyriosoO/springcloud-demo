package com.dylan.baseline.agent.security.authorization;

/** 将Auth上界与迁移期旧字段视图显式分区，防止旧字段进入最终权威模型。 */
public record ResolvedAuthPermission(
        AuthAuthorizationFacts authorizationFacts,
        LegacyAuthFieldView legacyFieldView) {

    public ResolvedAuthPermission {
        if (authorizationFacts == null || legacyFieldView == null) {
            throw new IllegalArgumentException("resolved Auth permission parts must not be null");
        }
    }
}
