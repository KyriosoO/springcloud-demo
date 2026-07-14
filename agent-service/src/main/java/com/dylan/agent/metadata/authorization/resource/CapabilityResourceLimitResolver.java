package com.dylan.agent.metadata.authorization.resource;

import com.dylan.agent.adapter.api.operation.CapabilityResourceLimit;
import com.dylan.agent.kernel.resource.CapabilityResourceLimitContract;
import com.dylan.agent.kernel.resource.CapabilityResourceLimitDeclaration;
import com.dylan.agent.kernel.resource.CapabilityResourceLimitRegistry;
import com.dylan.agent.kernel.resource.EffectiveCapabilityResourceLimits;
import com.dylan.agent.kernel.resource.ResourceLimitBindingIdentity;

import java.time.Instant;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/** 对 Definition/Profile/Policy/Permission/Request 做唯一、单调的强类型求交。 */
public final class CapabilityResourceLimitResolver {

    private final CapabilityResourceLimitRegistry registry;

    public CapabilityResourceLimitResolver(CapabilityResourceLimitRegistry registry) {
        this.registry = Objects.requireNonNull(registry, "registry must not be null");
    }

    public EffectiveCapabilityResourceLimits resolve(
            String invocationId,
            String requestCorrelationId,
            String registrationIdentity,
            String authorizationEvidenceDigest,
            CapabilityResourceLimitDeclaration<?> declaration,
            List<CapabilityResourceLimitContribution<?>> contributions,
            Instant frozenAt) {
        Objects.requireNonNull(declaration, "declaration must not be null");
        Objects.requireNonNull(contributions, "contributions must not be null");
        return resolveTyped(
                invocationId,
                requestCorrelationId,
                registrationIdentity,
                authorizationEvidenceDigest,
                declaration,
                contributions,
                frozenAt);
    }

    private <T extends CapabilityResourceLimit> EffectiveCapabilityResourceLimits resolveTyped(
            String invocationId,
            String requestCorrelationId,
            String registrationIdentity,
            String authorizationEvidenceDigest,
            CapabilityResourceLimitDeclaration<T> declaration,
            List<CapabilityResourceLimitContribution<?>> contributions,
            Instant frozenAt) {
        CapabilityResourceLimitContract<T> contract = registry.require(
                declaration.contractRef(), declaration.limitType());
        if (!contract.supportedDimensions().containsAll(declaration.applicableDimensions())) {
            throw new IllegalArgumentException("declaration contains unsupported resource dimensions");
        }
        contract.validate(declaration.intrinsicUpperBound());

        Map<ResourceLimitSource, CapabilityResourceLimitContribution<T>> indexed = new EnumMap<>(ResourceLimitSource.class);
        for (CapabilityResourceLimitContribution<?> raw : contributions) {
            if (!declaration.contractRef().equals(raw.contractRef())
                    || !declaration.limitType().equals(raw.limitType())) {
                throw new IllegalArgumentException("resource limit contribution contract/type mismatch");
            }
            @SuppressWarnings("unchecked")
            CapabilityResourceLimitContribution<T> contribution =
                    (CapabilityResourceLimitContribution<T>) raw;
            if (indexed.putIfAbsent(contribution.source(), contribution) != null) {
                throw new IllegalArgumentException("duplicate resource limit source: " + contribution.source());
            }
        }
        requireSource(indexed, ResourceLimitSource.PROFILE);
        requireSource(indexed, ResourceLimitSource.POLICY);
        requireSource(indexed, ResourceLimitSource.PERMISSION);

        T current = declaration.intrinsicUpperBound();
        for (ResourceLimitSource source : List.of(
                ResourceLimitSource.PROFILE,
                ResourceLimitSource.POLICY,
                ResourceLimitSource.PERMISSION)) {
            T next = indexed.get(source).upperBound();
            contract.validate(next);
            current = intersectAndProve(contract, current, next);
        }
        CapabilityResourceLimitContribution<T> request = indexed.get(ResourceLimitSource.REQUEST);
        if (request != null) {
            contract.validate(request.upperBound());
            if (!contract.isSameOrStricter(request.upperBound(), current)) {
                throw new IllegalArgumentException("request resource limit would widen authorized limits");
            }
            current = intersectAndProve(contract, current, request.upperBound());
        }
        contract.validate(current);
        String digest = contract.canonicalDigest(current);
        ResourceLimitBindingIdentity binding = new ResourceLimitBindingIdentity(
                invocationId,
                requestCorrelationId,
                registrationIdentity,
                authorizationEvidenceDigest,
                frozenAt);
        return new EffectiveCapabilityResourceLimits(
                declaration.contractRef(), declaration.limitType(), current, digest, binding);
    }

    private static <T extends CapabilityResourceLimit> T intersectAndProve(
            CapabilityResourceLimitContract<T> contract,
            T left,
            T right) {
        T result = contract.intersect(left, right);
        contract.validate(result);
        if (!contract.isSameOrStricter(result, left)
                || !contract.isSameOrStricter(result, right)) {
            throw new IllegalStateException("resource limit intersection is not monotonic");
        }
        return result;
    }

    private static void requireSource(
            Map<ResourceLimitSource, ?> indexed,
            ResourceLimitSource source) {
        if (!indexed.containsKey(source)) {
            throw new IllegalArgumentException("missing required resource limit source: " + source);
        }
    }
}
