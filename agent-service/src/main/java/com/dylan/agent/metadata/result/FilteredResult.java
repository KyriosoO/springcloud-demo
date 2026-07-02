package com.dylan.agent.metadata.result;

import com.dylan.agent.api.response.AgentResultPayload;

import java.util.Objects;

/** Projector 内部不可变 filtered candidate。 */
public record FilteredResult<O extends AgentResultPayload>(
        O payload,
        String safeMessage,
        String safeSummary) {
    public FilteredResult {
        Objects.requireNonNull(payload, "payload must not be null");
        safeMessage = requireNonBlank(safeMessage, "safeMessage");
        safeSummary = requireNonBlank(safeSummary, "safeSummary");
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
