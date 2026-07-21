package com.dylan.agent.kernel.core;

import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.kernel.port.model.ApprovedContextWrite;
import com.dylan.agent.kernel.port.model.SecuredResult;

import java.util.List;
import java.util.Objects;

public final class ExecutionSuccess implements ExecutionOutcome {

    private final SecuredResult securedResult;
    private final List<ApprovedContextWrite> approvedContextWrites;
    private final String capabilityId;
    private final AgentPlanKind planKind;

    public ExecutionSuccess(SecuredResult securedResult,
                            List<ApprovedContextWrite> approvedContextWrites,
                            String capabilityId,
                            AgentPlanKind planKind) {
        this.securedResult = Objects.requireNonNull(securedResult);
        this.approvedContextWrites = List.copyOf(approvedContextWrites == null ? List.of() : approvedContextWrites);
        this.capabilityId = Objects.requireNonNull(capabilityId);
        this.planKind = Objects.requireNonNull(planKind);
    }

    public SecuredResult securedResult() { return securedResult; }
    public List<ApprovedContextWrite> approvedContextWrites() { return approvedContextWrites; }
    public String capabilityId() { return capabilityId; }
    public AgentPlanKind planKind() { return planKind; }
}
