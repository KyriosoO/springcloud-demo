package com.dylan.agent.kernel.definition;

import com.dylan.agent.api.context.AggregateCapabilityContextPayload;
import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.plan.AggregateAgentPlan;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.response.AggregateAgentResultPayload;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.kernel.registration.CapabilityRegistration;

import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/** capability execution contracts 的 Java-only contract resolution table。 */
public final class ContractRegistry {

    private final Map<ContractRef, ContractDescriptor> descriptors;

    private ContractRegistry(Map<ContractRef, ContractDescriptor> descriptors) {
        this.descriptors = Map.copyOf(descriptors);
    }

    public static ContractRegistry from(Collection<CapabilityRegistration<?, ?, ?>> registrations) {
        Objects.requireNonNull(registrations, "registrations must not be null");
        Map<ContractRef, ContractDescriptor> map = new LinkedHashMap<>();
        register(map, AgentExecutionContracts.QUERY_PLAN, QueryAgentPlan.class);
        register(map, AgentExecutionContracts.AGGREGATE_PLAN, AggregateAgentPlan.class);
        register(map, AgentExecutionContracts.QUERY_RESULT, QueryAgentResultPayload.class);
        register(map, AgentExecutionContracts.AGGREGATE_RESULT, AggregateAgentResultPayload.class);
        register(map, AgentExecutionContracts.QUERY_CONTEXT, QueryCapabilityContextPayload.class);
        register(map, AgentExecutionContracts.AGGREGATE_CONTEXT, AggregateCapabilityContextPayload.class);

        for (CapabilityRegistration<?, ?, ?> registration : registrations) {
            register(map, registration.definition().inputContract(), registration.rawPlanType());
            register(map, registration.definition().outputContract(), registration.outputType());
            registration.definition().contextAccess().reads()
                    .forEach(read -> register(map, read.contractRef(), read.payloadType()));
            registration.definition().contextAccess().writes()
                    .forEach(write -> register(map, write.contractRef(), write.payloadType()));
        }
        return new ContractRegistry(map);
    }

    private static void register(Map<ContractRef, ContractDescriptor> map,
                                 ContractRef ref,
                                 Class<?> javaType) {
        ContractDescriptor descriptor =
                new ContractDescriptor(ref, javaType, structuralDigest(javaType));
        ContractDescriptor existing = map.putIfAbsent(ref, descriptor);
        if (existing != null && !existing.equals(descriptor)) {
            throw new IllegalStateException("ContractRef maps to multiple Java structures: " + ref);
        }
    }

    private static String structuralDigest(Class<?> javaType) {
        return javaType.getName();
    }

    public ContractDescriptor require(ContractRef ref) {
        ContractDescriptor descriptor = descriptors.get(ref);
        if (descriptor == null) {
            throw new IllegalArgumentException("unknown ContractRef: " + ref);
        }
        return descriptor;
    }

    public boolean isCompatible(ContractRef stored, ContractRef requested) {
        return require(stored).equals(require(requested));
    }

    public Set<ContractRef> all() {
        return descriptors.keySet();
    }

    public String runtimeSchemaRef(ContractRef ref) {
        Class<?> javaType = require(ref).javaType();
        if (javaType == QueryAgentPlan.class || javaType == AggregateAgentPlan.class) {
            return "#/components/schemas/" + javaType.getSimpleName();
        }
        throw new IllegalArgumentException("ContractRef is not a D01 runtime schema root: " + ref);
    }

    public record ContractDescriptor(ContractRef ref, Class<?> javaType, String structuralDigest) {
        public ContractDescriptor {
            Objects.requireNonNull(ref, "ref must not be null");
            Objects.requireNonNull(javaType, "javaType must not be null");
            Objects.requireNonNull(structuralDigest, "structuralDigest must not be null");
        }
    }
}
