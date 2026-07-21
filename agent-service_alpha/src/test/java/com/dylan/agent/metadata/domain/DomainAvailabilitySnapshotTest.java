package com.dylan.agent.metadata.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.metadata.domain.port.DomainAvailabilitySnapshot;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

class DomainAvailabilitySnapshotTest {

    @Test
    void defensivelyCopiesAvailableDomainsWithoutCarryingFieldCatalogFacts() {
        var evidence = DomainMetadataTestSupport.currentEvidence();
        Set<String> domains = new LinkedHashSet<>(Set.of("employee"));
        Map<AdapterRole, Set<String>> available = new LinkedHashMap<>();
        available.put(AdapterRole.QUERYABLE, domains);

        DomainAvailabilitySnapshot snapshot = new DomainAvailabilitySnapshot(evidence, available);
        domains.add("transaction");

        assertThat(snapshot.evidence()).isEqualTo(evidence);
        assertThat(snapshot.availableDomains()).containsOnlyKeys(AdapterRole.QUERYABLE);
        assertThat(snapshot.availableDomains().get(AdapterRole.QUERYABLE)).containsExactly("employee");
    }
}
