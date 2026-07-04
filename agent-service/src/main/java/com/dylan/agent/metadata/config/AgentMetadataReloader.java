package com.dylan.agent.metadata.config;

import com.dylan.agent.metadata.crypto.port.PayloadKeyProvider;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.domain.port.CanonicalFunctionRef;
import com.dylan.agent.metadata.domain.port.CanonicalOperatorRef;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;
import com.dylan.agent.metadata.domain.port.DomainMetadataReferenceSet;
import com.dylan.agent.metadata.policy.model.DomainSecurityConstraints;

import java.time.Clock;
import java.time.Instant;
import java.util.Set;
import java.util.Objects;
import java.util.stream.Collectors;

/** 原子 reload seam。完整 candidate 转换归 D03，本类只负责发布语义。 */
public final class AgentMetadataReloader {

    private final AgentMetadataStore store;
    private final DomainMetadataPort domainMetadataPort;
    private final PayloadKeyProvider payloadKeyProvider;
    private final Clock clock;

    public AgentMetadataReloader(
            AgentMetadataStore store,
            DomainMetadataPort domainMetadataPort,
            PayloadKeyProvider payloadKeyProvider,
            Clock clock) {
        this.store = Objects.requireNonNull(store);
        this.domainMetadataPort = Objects.requireNonNull(domainMetadataPort);
        this.payloadKeyProvider = Objects.requireNonNull(payloadKeyProvider);
        this.clock = Objects.requireNonNull(clock);
    }

    public AgentMetadataBundle publishValidated(AgentMetadataBundle candidate) {
        Objects.requireNonNull(candidate, "candidate must not be null");
        AgentMetadataBundle current = store.current();
        if (current.bundleVersion().equals(candidate.bundleVersion())
                && !current.bundleDigest().equals(candidate.bundleDigest())) {
            throw new IllegalStateException("same metadata bundleVersion cannot change digest");
        }
        AgentMetadataPropertiesValidator.validate(candidate, payloadKeyProvider);
        Instant deadline = clock.instant().plusSeconds(30);
        domainMetadataPort.assertCurrent(
                domainMetadataPort.validateReferences(
                        domainReferences(candidate),
                        deadline),
                deadline);
        if (!store.compareAndSet(current, candidate)) {
            throw new IllegalStateException("concurrent metadata reload conflict");
        }
        return candidate;
    }

    private static DomainMetadataReferenceSet domainReferences(AgentMetadataBundle candidate) {
        Set<CanonicalFieldRef> fields = candidate.activePolicy().domainSecurityConstraints().values().stream()
                .flatMap(constraints -> constraints.fields().keySet().stream())
                .collect(Collectors.toUnmodifiableSet());
        Set<CanonicalOperatorRef> operators = candidate.activePolicy().domainSecurityConstraints().values().stream()
                .flatMap(AgentMetadataReloader::operatorRefs)
                .collect(Collectors.toUnmodifiableSet());
        Set<CanonicalFunctionRef> functions = candidate.activePolicy().domainSecurityConstraints().values().stream()
                .flatMap(AgentMetadataReloader::functionRefs)
                .collect(Collectors.toUnmodifiableSet());
        return new DomainMetadataReferenceSet(fields, operators, functions);
    }

    private static java.util.stream.Stream<CanonicalOperatorRef> operatorRefs(
            DomainSecurityConstraints constraints) {
        return constraints.fields().entrySet().stream()
                .flatMap(entry -> entry.getValue().allowedOperators().stream()
                        .map(operator -> new CanonicalOperatorRef(entry.getKey(), operator)));
    }

    private static java.util.stream.Stream<CanonicalFunctionRef> functionRefs(
            DomainSecurityConstraints constraints) {
        return constraints.fields().entrySet().stream()
                .flatMap(entry -> entry.getValue().allowedFunctions().stream()
                        .map(function -> new CanonicalFunctionRef(entry.getKey(), function)));
    }
}
