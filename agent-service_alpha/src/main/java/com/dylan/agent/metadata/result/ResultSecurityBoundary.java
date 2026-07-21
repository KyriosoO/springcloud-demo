package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.response.AgentResultPayload;
import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.kernel.port.ResultSecurityPort;
import com.dylan.agent.kernel.port.model.SecuredResult;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.kernel.resource.EffectiveCapabilityResourceLimits;
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
    public SecuredResult secure(
            Object candidate,
            ContractRef outputContract,
            ExecutionScope scope,
            EffectiveCapabilityResourceLimits limits) {
        Objects.requireNonNull(candidate, "candidate must not be null");
        Objects.requireNonNull(outputContract, "outputContract must not be null");
        Objects.requireNonNull(scope, "scope must not be null");
        Objects.requireNonNull(limits, "limits must not be null");
        if (!limits.reference().equals(scope.resourceLimits().reference())) {
            throw new IllegalStateException("result security resource limit binding mismatch");
        }
        Class<?> expectedType = contractRegistry.require(outputContract).javaType();
        if (!expectedType.isInstance(candidate)) {
            throw new IllegalStateException("candidate result does not match output contract");
        }
        ResultSecurityProjector<?> projector = projectorRegistry.require(outputContract);
        FilteredResult<?> filtered = projector.filterUntyped((AgentResultPayload) candidate, scope, limits);
        if (!expectedType.isInstance(filtered.payload())) {
            throw new IllegalStateException("filtered result does not match output contract");
        }
        byte[] canonicalPayload = jsonCodec.serialize(filtered.payload(), expectedType);
        if (outputContract.equals(AgentExecutionContracts.QUERY_RESULT)
                || outputContract.equals(AgentExecutionContracts.QUERY_PREVIEW_RESULT)
                || outputContract.equals(AgentExecutionContracts.AGGREGATE_RESULT)) {
            long maxResultBytes = limits.require(
                    AgentExecutionContracts.STANDARD_RESOURCE_LIMIT,
                    com.dylan.agent.adapter.api.operation.StandardCapabilityResourceLimit.class)
                    .maxResultBytes();
            if (canonicalPayload.length > maxResultBytes) {
                throw new IllegalStateException("secured result exceeds effective result byte limit");
            }
        }
        return new SecuredResult(
                outputContract,
                canonicalPayload,
                filtered.safeMessage(),
                filtered.safeSummary());
    }
}
