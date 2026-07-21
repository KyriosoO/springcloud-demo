package com.dylan.agent.api.response;

/** 生成文本和引用证据的绑定校验状态。 */
public enum GroundingStatus {
    VERIFIED,
    PARTIAL,
    UNVERIFIED,
    NO_EVIDENCE
}
