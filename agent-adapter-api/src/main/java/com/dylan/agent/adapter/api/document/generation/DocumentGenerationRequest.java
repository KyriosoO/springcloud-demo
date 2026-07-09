package com.dylan.agent.adapter.api.document.generation;

import com.dylan.agent.api.plan.DocumentPlanOperation;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;

/** 文档执行后 LLM 生成请求。 */
public record DocumentGenerationRequest(
        @NotBlank String requestId,
        @NotNull DocumentPlanOperation operation,
        @NotBlank String queryText,
        String model,
        @Valid @NotNull EvidenceContextPackage contextPackage,
        int maxOutputChars,
        @NotNull Instant deadline) {
}
