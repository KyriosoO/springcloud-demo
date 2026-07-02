package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.response.AgentResultPayload;
import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.kernel.port.ResultSecurityPort;
import com.dylan.agent.kernel.port.model.SecuredResult;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;

import java.util.Objects;

/** 结果安全边界：校验契约、执行一次过滤并序列化规范字节。 */
public final class ResultSecurityBoundary implements ResultSecurityPort {

    private final ContractRegistry contractRegistry;
    private final ResultSecurityProjectorRegistry projectorRegistry;
    private final PayloadJsonCodec jsonCodec;

    public ResultSecurityBoundary(
            ContractRegistry contractRegistry,
            ResultSecurityProjectorRegistry projectorRegistry,
            PayloadJsonCodec jsonCodec) {
        this.contractRegistry = Objects.requireNonNull(contractRegistry);
        this.projectorRegistry = Objects.requireNonNull(projectorRegistry);
        this.jsonCodec = Objects.requireNonNull(jsonCodec);
    }

    @Override
    public SecuredResult secure(Object candidate, ContractRef outputContract, ExecutionScope scope) {
        Objects.requireNonNull(candidate, "candidate must not be null");
        Objects.requireNonNull(outputContract, "outputContract must not be null");
        Objects.requireNonNull(scope, "scope must not be null");
        Class<?> expectedType = contractRegistry.require(outputContract).javaType();
        if (!expectedType.isInstance(candidate)) {
            throw new IllegalStateException("candidate result does not match output contract");
        }
        ResultSecurityProjector<?> projector = projectorRegistry.require(outputContract);
        FilteredResult<?> filtered = projector.filterUntyped((AgentResultPayload) candidate, scope);
        if (!expectedType.isInstance(filtered.payload())) {
            throw new IllegalStateException("filtered result does not match output contract");
        }
        return new SecuredResult(
                outputContract,
                jsonCodec.serialize(filtered.payload(), expectedType),
                filtered.safeMessage(),
                filtered.safeSummary());
    }
}
