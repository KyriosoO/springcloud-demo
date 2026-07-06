package com.dylan.agent.kernel.core;

import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.invocation.model.CancellationToken;
import com.dylan.agent.kernel.port.model.ExecutionValidationProjection;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

import java.time.Instant;
import java.util.List;

public final class ExecutionValidationContextTestSupport {

    private ExecutionValidationContextTestSupport() {
    }

    public static ExecutionValidationContext documentContext(
            String capabilityId,
            ExecutionScope scope,
            ExecutionValidationProjection projection,
            Instant absoluteDeadline,
            CancellationToken cancellation) {
        return new ExecutionValidationContext(
                capabilityId,
                AgentPlanKind.DOCUMENT,
                AgentDomainMode.REQUIRED,
                scope,
                projection,
                null,
                List.of(),
                absoluteDeadline,
                cancellation);
    }
}
