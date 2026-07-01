package com.dylan.agent.planning.model;

/**
 * Planning 失败信息，由 D02_00 唯一负责。
 *
 * <p>携带安全 error code、stage 和 diagnostic ID。由 Entry/Lifecycle 映射为 Agent API ErrorCode。
 * 不包含 Raw/Validated Plan、Context payload、权限表达式、Runtime 原始响应或栈信息。
 */
public final class PlanningFailure {

    private final String safeErrorCode;
    private final String stage;
    private final String diagnosticId;
    private final String safeMessage;

    public PlanningFailure(String safeErrorCode, String stage, String diagnosticId, String safeMessage) {
        this.safeErrorCode = java.util.Objects.requireNonNull(safeErrorCode);
        this.stage = java.util.Objects.requireNonNull(stage);
        this.diagnosticId = java.util.Objects.requireNonNull(diagnosticId);
        this.safeMessage = java.util.Objects.requireNonNull(safeMessage);
    }

    public String safeErrorCode() { return safeErrorCode; }
    public String stage() { return stage; }
    public String diagnosticId() { return diagnosticId; }
    public String safeMessage() { return safeMessage; }
}
