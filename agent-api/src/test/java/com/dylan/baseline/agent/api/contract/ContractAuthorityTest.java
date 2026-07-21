package com.dylan.baseline.agent.api.contract;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;

class ContractAuthorityTest {
    @Test
    void targetHasOneRuntimeOpenApiAndNoParallelWireDto() throws Exception {
        Path module = Path.of("").toAbsolutePath().normalize();
        Path repository = module.getFileName().toString().equals("agent-api") ? module.getParent() : module;
        List<Path> sources;
        try (var paths = Files.walk(repository, 6)) {
            sources = paths.filter(Files::isRegularFile)
                    .filter(path -> {
                        String name = path.getFileName().toString().toLowerCase();
                        return (name.endsWith(".json") || name.endsWith(".yaml") || name.endsWith(".yml"))
                                && name.contains("openapi")
                                && (name.contains("runtime") || name.contains("tool"));
                    })
                    .filter(path -> path.toString().contains("src" + java.io.File.separator + "main"))
                    .filter(path -> path.toString().contains(java.io.File.separator + "openapi"
                            + java.io.File.separator))
                    .filter(path -> !path.toString().contains("_alpha" + java.io.File.separator))
                    .filter(path -> !path.toString().contains(java.io.File.separator + "target" + java.io.File.separator))
                    .toList();
        }
        assertThat(sources).containsExactly(
                repository.resolve("agent-api/src/main/resources/openapi/agent-runtime-openapi.json"));

        String servicePom = Files.readString(repository.resolve("agent-service/pom.xml"));
        assertThat(servicePom).contains("<artifactId>agent-api</artifactId>").doesNotContain("_alpha");
        try (var javaSources = Files.walk(repository.resolve("agent-service/src/main/java"))) {
            String productionCode = javaSources.filter(path -> path.toString().endsWith(".java"))
                    .map(path -> {
                        try {
                            return Files.readString(path);
                        } catch (java.io.IOException exception) {
                            throw new java.io.UncheckedIOException(exception);
                        }
                    })
                    .reduce("", (left, right) -> left + "\n" + right);
            assertThat(productionCode)
                    .doesNotContain("class ContractMetadata", "record ContractMetadata", "_alpha")
                    .contains("com.dylan.baseline.agent.api.runtime.generated.ContractMetadata");
        }
    }
}
