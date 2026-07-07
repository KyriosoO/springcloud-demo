package com.dylan.documentgeneration.model;

import java.util.Map;

public record DocumentEvidenceContextItem(
        String citationId,
        String text,
        Map<String, Object> metadata) {
}
