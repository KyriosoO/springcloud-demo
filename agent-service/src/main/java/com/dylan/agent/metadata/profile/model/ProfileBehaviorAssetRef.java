package com.dylan.agent.metadata.profile.model;

import java.util.Objects;

/** Exact version reference for reviewed profile behavior instructions. */
public record ProfileBehaviorAssetRef(String assetId, String version) {
    public ProfileBehaviorAssetRef {
        assetId = requireNonBlank(assetId, "assetId");
        version = requireNonBlank(version, "version");
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
