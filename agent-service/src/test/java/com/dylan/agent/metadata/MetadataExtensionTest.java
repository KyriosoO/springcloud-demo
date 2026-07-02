package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class MetadataExtensionTest {
    @Test
    void addingNewDomainDoesNotRequireMetadataAlgorithmBranch() {
        assertThat(com.dylan.agent.metadata.domain.port.DomainMetadataPort.class).isInterface();
        assertThat(com.dylan.agent.metadata.catalog.CapabilityCatalog.class).isFinal();
    }
}
