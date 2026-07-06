package com.dylan.agent.capability.document.generation;

/** LLM 证据上下文和输出预算。 */
public record DocumentContextBudget(
        int maxContextChars,
        int maxEvidenceChars,
        int maxEvidenceCount,
        int maxOutputChars) {
}
