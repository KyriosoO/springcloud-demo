package com.dylan.documentgeneration.model;

public record DocumentContextBudget(
        int maxContextChars,
        int maxEvidenceChars,
        int maxEvidenceCount,
        int maxOutputChars) {
}
