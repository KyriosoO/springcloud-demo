package com.dylan.agent.capability.document.generation;

import com.dylan.agent.api.response.GroundingStatus;

/** 不携带 Provider 无效ID原值的本地引用校验结果。 */
public record CitationVerificationResult(
        GroundingStatus status,
        int boundUnitCount,
        int visibleCitationCount,
        String reasonCode) {
    public boolean verified() { return status == GroundingStatus.VERIFIED || status == GroundingStatus.PARTIAL; }
}
