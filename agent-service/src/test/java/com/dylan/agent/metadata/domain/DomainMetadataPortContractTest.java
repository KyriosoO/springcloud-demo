package com.dylan.agent.metadata.domain;

import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.domain.port.CanonicalFunctionRef;
import com.dylan.agent.metadata.domain.port.CanonicalOperatorRef;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.metadata.domain.port.DomainMetadataReferenceSet;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DomainMetadataPortContractTest {

    @Test
    void referenceSetRequiresOperatorAndFunctionFieldsToBeDeclared() {
        CanonicalFieldRef field = new CanonicalFieldRef("employee", "name");

        DomainMetadataReferenceSet refs = new DomainMetadataReferenceSet(
                Set.of(field),
                Set.of(new CanonicalOperatorRef(field, AgentOperator.EQ)),
                Set.of(new CanonicalFunctionRef(field, "COUNT")));

        assertThat(refs.isEmpty()).isFalse();

        CanonicalFieldRef undeclared = new CanonicalFieldRef("employee", "salary");
        assertThatThrownBy(() -> new DomainMetadataReferenceSet(
                Set.of(field),
                Set.of(new CanonicalOperatorRef(undeclared, AgentOperator.GT)),
                Set.of()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("operator field");
    }

    @Test
    void evidenceSafeRefIsStableAndDoesNotExposeCatalogBody() {
        DomainMetadataEvidence left = new DomainMetadataEvidence(
                "catalog-v1", "adapter-v1", "availability-digest", Instant.parse("2026-07-01T00:00:00Z"));
        DomainMetadataEvidence same = new DomainMetadataEvidence(
                "catalog-v1", "adapter-v1", "availability-digest", Instant.parse("2026-07-01T00:00:00Z"));
        DomainMetadataEvidence different = new DomainMetadataEvidence(
                "catalog-v2", "adapter-v1", "availability-digest", Instant.parse("2026-07-01T00:00:00Z"));

        assertThat(left.safeRef()).isEqualTo(same.safeRef());
        assertThat(left.safeRef()).isNotEqualTo(different.safeRef());
        assertThat(left.safeRef()).doesNotContain("catalog-v1");
    }
}
