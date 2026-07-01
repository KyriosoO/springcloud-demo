package com.dylan.agent.kernel.port.model;

import java.util.Objects;

/**
 * Execution Core 提交给 metadata 安全边界的已验证结果，由 D02_01 所有。
 *
 * <p>字段为 capabilityId、planKind、output ContractRef、类型化且已通过
 * Validation/Handler 校验的候选结果对象。本结构不包含原始 Raw Plan、
 * Context payload 或权限表达式。</p>
 */
public final class SecuredResult {

    private final String capabilityId;
    private final Object planKind; // AgentPlanKind after D01 activation
    private final String outputContractRef; // JSON Pointer from Registration
    private final Object candidateResult; // typed handler output

    public SecuredResult(String capabilityId, Object planKind,
                         String outputContractRef, Object candidateResult) {
        this.capabilityId = Objects.requireNonNull(capabilityId);
        this.planKind = Objects.requireNonNull(planKind);
        this.outputContractRef = Objects.requireNonNull(outputContractRef);
        this.candidateResult = Objects.requireNonNull(candidateResult);
    }

    public String capabilityId() { return capabilityId; }
    public Object planKind() { return planKind; }
    public String outputContractRef() { return outputContractRef; }
    public Object candidateResult() { return candidateResult; }
}
