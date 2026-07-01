package com.dylan.agent.kernel.port.model;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;

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
    private final AgentPlanKind planKind;
    private final ContractRef outputContract;
    private final Object candidateResult; // typed handler output

    public SecuredResult(String capabilityId, AgentPlanKind planKind,
                         ContractRef outputContract, Object candidateResult) {
        this.capabilityId = Objects.requireNonNull(capabilityId);
        this.planKind = Objects.requireNonNull(planKind);
        this.outputContract = Objects.requireNonNull(outputContract);
        this.candidateResult = Objects.requireNonNull(candidateResult);
    }

    public String capabilityId() { return capabilityId; }
    public AgentPlanKind planKind() { return planKind; }
    public ContractRef outputContract() { return outputContract; }
    public Object candidateResult() { return candidateResult; }
}
