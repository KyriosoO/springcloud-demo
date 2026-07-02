package com.dylan.authcenter.agent.permission.api;

/**
 * Agent 执行主体引用。首版仅支持 USER，字段与 agent-service ExecutionSubjectRef 保持同构。
 */
public record SubjectRefDto(
        String type,
        String id) {
}
