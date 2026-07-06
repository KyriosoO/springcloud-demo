package com.dylan.agent.capability.document.generation;

import java.util.Map;

/** 进入 LLM 的单条已裁剪证据。 */
public record DocumentEvidenceContextItem(
        String citationId,
        String text,
        Map<String, Object> metadata) {
}
