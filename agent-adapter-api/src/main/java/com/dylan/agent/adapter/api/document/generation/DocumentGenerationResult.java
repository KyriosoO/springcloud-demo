package com.dylan.agent.adapter.api.document.generation;

import java.util.List;

/** LLM 返回的候选回答或摘要。 */
public record DocumentGenerationResult(
        String answerText,
        String summaryText,
        List<String> summaryBullets,
        List<CitationBinding> citationBindings,
        String finishReason) {
}
