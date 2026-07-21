package com.dylan.agent.metadata.profile.model;

import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.Optional;

/** 不可变 behavior asset；只作为已评审 instructions 投影给 Runtime。 */
public record ProfileBehaviorAsset(
        ProfileBehaviorAssetRef ref,
        List<String> instructions,
        Optional<Locale> locale) {

    public ProfileBehaviorAsset {
        Objects.requireNonNull(ref, "ref must not be null");
        instructions = List.copyOf(Objects.requireNonNull(instructions, "instructions must not be null"));
        if (instructions.isEmpty() || instructions.size() > 20) {
            throw new IllegalArgumentException("instructions size must be 1..20");
        }
        for (String instruction : instructions) {
            String normalized = requireNonBlank(instruction, "instruction");
            if (normalized.length() > 500) {
                throw new IllegalArgumentException("instruction length must be <= 500");
            }
        }
        locale = Objects.requireNonNull(locale, "locale must not be null");
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
