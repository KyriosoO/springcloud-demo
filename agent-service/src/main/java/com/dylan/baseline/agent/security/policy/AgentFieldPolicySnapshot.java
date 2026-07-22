package com.dylan.baseline.agent.security.policy;

import com.dylan.baseline.agent.security.authorization.LegacyAuthFieldView;
import java.util.Map;
import java.util.TreeMap;

/** 不含用户和角色关系的不可变Agent字段策略快照。 */
public record AgentFieldPolicySnapshot(
        String policyVersion,
        String policyDigest,
        Map<String, LegacyAuthFieldView> fieldPolicyByPermissionCode) {

    public AgentFieldPolicySnapshot {
        requireText(policyVersion, "policyVersion");
        requireText(policyDigest, "policyDigest");
        if (fieldPolicyByPermissionCode == null || fieldPolicyByPermissionCode.isEmpty()
                || fieldPolicyByPermissionCode.entrySet().stream().anyMatch(entry ->
                        entry.getKey() == null || entry.getKey().isBlank() || entry.getValue() == null)) {
            throw new IllegalArgumentException("fieldPolicyByPermissionCode must not be empty or invalid");
        }
        fieldPolicyByPermissionCode = Map.copyOf(new TreeMap<>(fieldPolicyByPermissionCode));
    }

    private static void requireText(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
    }
}
