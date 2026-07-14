package com.dylan.agent.metadata.authorization.resource;

/** 当前 CHAT/Conversation 阶段允许参与资源收紧的来源。 */
public enum ResourceLimitSource {
    PROFILE,
    POLICY,
    PERMISSION,
    REQUEST
}
