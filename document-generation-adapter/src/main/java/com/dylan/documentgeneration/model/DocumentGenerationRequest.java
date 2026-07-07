package com.dylan.documentgeneration.model;

import java.time.Instant;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record DocumentGenerationRequest(
        @NotBlank String requestId,
        @NotNull DocumentPlanOperation operation,
        @NotBlank String queryText,
        String model,
        @Valid @NotNull EvidenceContextPackage contextPackage,
        int maxOutputChars,
        @NotNull Instant deadline) {
}
