package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.adapter.api.AdapterRole;

import java.util.Map;
import java.util.Objects;

/** D04 startup-time adapter availability view. */
public record AdapterAvailabilitySnapshot(Map<AdapterRegistrationSet.Key, Boolean> available) {
    public AdapterAvailabilitySnapshot {
        available = Map.copyOf(Objects.requireNonNull(available, "available must not be null"));
    }

    public boolean isAvailable(AdapterRole role, String domain) {
        return Boolean.TRUE.equals(available.get(new AdapterRegistrationSet.Key(role, domain)));
    }
}
