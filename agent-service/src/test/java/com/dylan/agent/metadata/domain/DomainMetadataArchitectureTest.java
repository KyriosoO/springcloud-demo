package com.dylan.agent.metadata.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.reflect.Modifier;
import java.nio.file.Files;
import java.nio.file.Path;

import org.junit.jupiter.api.Test;

import com.dylan.agent.metadata.domain.internal.DomainMetadataPortImpl;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;

class DomainMetadataArchitectureTest {

    @Test
    void domainMetadataPortHasSingleProductionImplementationAndOldSourcesAreDeleted() {
        assertThat(DomainMetadataPort.class).isAssignableFrom(DomainMetadataPortImpl.class);
        assertThat(Modifier.isFinal(DomainMetadataPortImpl.class.getModifiers())).isTrue();

        Path repoRoot = repoRoot();
        assertThat(Files.exists(repoRoot.resolve(
                "agent-service/src/main/java/com/dylan/agent/adapter/QueryableAdapterRegistry.java"))).isFalse();
        assertThat(Files.exists(repoRoot.resolve(
                "agent-service/src/main/java/com/dylan/agent/adapter/AggregatableAdapterRegistry.java"))).isFalse();
        assertThat(Files.exists(repoRoot.resolve(
                "agent-service/src/main/java/com/dylan/agent/planning/RuntimeDomainSchemaFactory.java"))).isFalse();
        assertThat(Files.exists(repoRoot.resolve(
                "agent-service/src/main/java/com/dylan/agent/metadata/domain/internal/AdapterPortResolver.java")))
                .isFalse();
    }

    private static Path repoRoot() {
        Path cwd = Path.of(System.getProperty("user.dir")).toAbsolutePath().normalize();
        return cwd.getFileName().toString().equals("serviceCenter") ? cwd.getParent() : cwd;
    }
}
