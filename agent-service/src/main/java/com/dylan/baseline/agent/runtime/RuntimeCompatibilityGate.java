package com.dylan.baseline.agent.runtime;

import com.dylan.baseline.agent.api.runtime.generated.ContractMetadata;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;

public final class RuntimeCompatibilityGate {
    private static final Pattern VERSION = Pattern.compile(
            "^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*)?(?:\\+[0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*)?$");
    private static final Pattern FINGERPRINT = Pattern.compile("^sha256:[a-f0-9]{64}$");
    public RuntimeCompatibilityDecision evaluate(
            ContractMetadata expected, ContractMetadata actual, String requiredCapability) {
        if (!valid(expected) || !valid(actual) || (requiredCapability != null && requiredCapability.isBlank())) {
            return reject(RuntimeCompatibilityReason.METADATA_INVALID, expected, actual, requiredCapability);
        }
        if (!expected.getContractVersion().equals(actual.getContractVersion())) {
            return reject(RuntimeCompatibilityReason.VERSION_MISMATCH, expected, actual, requiredCapability);
        }
        if (!expected.getContractFingerprint().equals(actual.getContractFingerprint())) {
            return reject(RuntimeCompatibilityReason.FINGERPRINT_MISMATCH, expected, actual, requiredCapability);
        }
        if (requiredCapability != null && !actual.getCapabilities().contains(requiredCapability)) {
            return reject(RuntimeCompatibilityReason.CAPABILITY_MISSING, expected, actual, requiredCapability);
        }
        return new RuntimeCompatibilityDecision(
                RuntimeCompatibilityStatus.ALLOW,
                RuntimeCompatibilityReason.COMPATIBLE,
                expected,
                actual,
                requiredCapability);
    }

    private static boolean valid(ContractMetadata metadata) {
        if (metadata == null || metadata.getContractVersion() == null
                || metadata.getContractFingerprint() == null || metadata.getCapabilities() == null) {
            return false;
        }
        if (!VERSION.matcher(metadata.getContractVersion()).matches()
                || !FINGERPRINT.matcher(metadata.getContractFingerprint()).matches()) {
            return false;
        }
        Set<String> capabilities = metadata.getCapabilities();
        if (capabilities.stream().anyMatch(value -> value == null || value.isBlank())) {
            return false;
        }
        List<String> actualOrder = new ArrayList<>(capabilities);
        List<String> sorted = actualOrder.stream().sorted().toList();
        return actualOrder.equals(sorted);
    }

    private static RuntimeCompatibilityDecision reject(
            RuntimeCompatibilityReason reason,
            ContractMetadata expected,
            ContractMetadata actual,
            String requiredCapability) {
        return new RuntimeCompatibilityDecision(
                RuntimeCompatibilityStatus.REJECT, reason, expected, actual, requiredCapability);
    }
}
