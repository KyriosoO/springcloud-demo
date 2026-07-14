package com.dylan.agent.metadata.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.reflect.Modifier;
import java.nio.file.Files;
import java.nio.file.Path;
import java.io.IOException;
import java.util.List;
import java.util.stream.Stream;

import org.junit.jupiter.api.Test;

import com.dylan.agent.metadata.domain.internal.DomainMetadataPortImpl;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;
import com.dylan.agent.adapter.api.AggregatableAdapter;
import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.adapter.api.QueryableAdapter;
import com.dylan.agent.kernel.port.model.ExecutionValidationProjection;
import com.dylan.agent.metadata.domain.internal.CanonicalRoleCapability;
import com.dylan.agent.metadata.domain.internal.DomainMetadataProperties;

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

    @Test
    void adapterPortsDoNotSelfReportDomainFacts() {
        List<String> methodNames = Stream.of(
                        QueryableAdapter.class,
                        AggregatableAdapter.class,
                        DocumentRetrievableAdapter.class)
                .flatMap(type -> Stream.of(type.getDeclaredMethods()))
                .map(method -> method.getName().toLowerCase(java.util.Locale.ROOT))
                .toList();

        assertThat(methodNames).noneMatch(name -> name.contains("supportedfield")
                || name.contains("operator")
                || name.contains("function")
                || name.contains("capabilit"));
    }

    @Test
    void domainMetadataModelsDoNotReintroduceResourceBudgets() {
        List<Class<?>> types = List.of(
                DomainMetadataProperties.RoleCapabilityProperties.class,
                CanonicalRoleCapability.class,
                ExecutionValidationProjection.class);
        List<String> memberNames = types.stream()
                .flatMap(type -> Stream.concat(
                        Stream.of(type.getDeclaredFields()).map(java.lang.reflect.Field::getName),
                        Stream.of(type.getDeclaredMethods()).map(java.lang.reflect.Method::getName)))
                .map(name -> name.toLowerCase(java.util.Locale.ROOT))
                .toList();

        assertThat(memberNames).noneMatch(name -> name.contains("maxpagesize")
                || name.contains("maxresultrows")
                || name.contains("maxresultbytes"));
    }

    @Test
    void planningKernelAndGenericValidatorsDoNotBranchOnProductionDomains() throws IOException {
        Path sourceRoot = repoRoot().resolve("agent-service/src/main/java/com/dylan/agent");
        for (String packageName : List.of("planning", "kernel", "capability")) {
            try (Stream<Path> files = Files.walk(sourceRoot.resolve(packageName))) {
                List<Path> violations = files
                        .filter(path -> path.toString().endsWith(".java"))
                        .filter(path -> {
                            String source = read(path);
                            return source.contains("\"employee\"")
                                    || source.contains("\"transaction\"")
                                    || source.contains("\"sample_domain\"");
                        })
                        .toList();
                assertThat(violations).as(packageName).isEmpty();
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
