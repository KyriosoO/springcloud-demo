package com.dylan.documentgeneration.model;

import java.util.List;

public record DocumentGenerationResult(
        String answerText,
        String summaryText,
        List<String> summaryBullets,
        List<CitationBinding> citationBindings,
        String finishReason) {
}
