package com.dylan.baseline.agent.runtime;

import com.dylan.baseline.agent.api.runtime.generated.ContractMetadata;

public record RuntimeCompatibilityDecision(
        RuntimeCompatibilityStatus status,
        RuntimeCompatibilityReason reason,
        ContractMetadata expected,
        ContractMetadata actual,
        String requiredCapability) {
}
