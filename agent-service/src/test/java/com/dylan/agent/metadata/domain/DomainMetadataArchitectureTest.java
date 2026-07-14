package com.dylan.agent.metadata.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.reflect.Modifier;
import java.nio.file.Files;
import java.nio.file.Path;
import java.io.IOException;
import java.util.stream.Stream;

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

    @Test
    void kernelAndCapabilitiesDependOnlyOnDomainPortModels() throws IOException {
        Path sourceRoot = repoRoot().resolve("agent-service/src/main/java/com/dylan/agent");
        for (String packageName : java.util.List.of("kernel", "capability")) {
            try (Stream<Path> files = Files.walk(sourceRoot.resolve(packageName))) {
                assertThat(files.filter(path -> path.toString().endsWith(".java"))
                        .filter(path -> read(path).contains("com.dylan.agent.metadata.domain.internal"))
                        .toList()).isEmpty();
            }
        }
    }

    private static String read(Path path) {
        try {
            return Files.readString(path);
        } catch (IOException ex) {
            throw new IllegalStateException(ex);
        }
    }

    private static Path repoRoot() {
        Path cwd = Path.of(System.getProperty("user.dir")).toAbsolutePath().normalize();
        String leaf = cwd.getFileName().toString();
        return leaf.equals("serviceCenter") || leaf.equals("agent-service") ? cwd.getParent() : cwd;
    }
}
