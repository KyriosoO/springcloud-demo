package com.dylan.agent.kernel.infrastructure;

import java.util.Objects;

/** 生成文本候选中 citation 到 evidence 的封闭引用。 */
public record CandidateCitationReference(String citationId, String evidenceRefId) {

    public CandidateCitationReference {
        citationId = requireNonBlank(citationId, "citationId");
        evidenceRefId = requireNonBlank(evidenceRefId, "evidenceRefId");
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
