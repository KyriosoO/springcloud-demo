package com.dylan.baseline.agent.security.policy;

/** MySQL中不可变策略版本与active epoch的封闭读取结果。 */
public record StoredAgentSecurityPolicy(
        String policyVersion,
        String schemaVersion,
        String policyPayload,
        String policyDigest,
        long policyEpoch,
        long stateVersion) {

    public StoredAgentSecurityPolicy {
        requireText(policyVersion, "policyVersion");
        requireText(schemaVersion, "schemaVersion");
        requireText(policyPayload, "policyPayload");
        if (policyDigest == null || !policyDigest.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("policyDigest must be lowercase SHA-256");
        }
        if (policyEpoch < 1 || stateVersion < 1) {
            throw new IllegalArgumentException("policyEpoch and stateVersion must be positive");
        }
    }

    private static void requireText(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
    }
}
