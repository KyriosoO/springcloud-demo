package com.dylan.agent.adapter.api.operation;

import java.util.Optional;

/** 可记录到安全 operation metadata 的 provider/model 引用。 */
public record ProviderSafeIdentity(String providerId, Optional<String> modelRef) {

    public ProviderSafeIdentity {
        if (providerId == null || providerId.isBlank()) {
            throw new IllegalArgumentException("providerId must not be blank");
        }
        modelRef = modelRef == null ? Optional.empty() : modelRef;
        modelRef.ifPresent(value -> {
            if (value.isBlank()) {
                throw new IllegalArgumentException("modelRef must not be blank");
            }
        });
    }
}
