package com.dylan.agent.capability.document.generation;

import com.dylan.agent.api.plan.DocumentPlanOperation;

import java.time.Instant;

/** 文档执行后 LLM 生成请求。 */
public record DocumentGenerationRequest(
        String requestId,
        DocumentPlanOperation operation,
        String queryText,
        String model,
        EvidenceContextPackage contextPackage,
        int maxOutputChars,
        Instant deadline) {
}
