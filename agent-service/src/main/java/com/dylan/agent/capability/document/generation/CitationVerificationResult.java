package com.dylan.agent.capability.document.generation;

import com.dylan.agent.api.response.GroundingStatus;

import java.util.List;

/** 引用校验结果。 */
public record CitationVerificationResult(
        GroundingStatus status,
        int removedClaimCount,
        List<String> invalidCitationIds,
        String fallbackReason) {
}
