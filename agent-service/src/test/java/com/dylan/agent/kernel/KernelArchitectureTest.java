package com.dylan.agent.kernel;

import com.tngtech.archunit.core.importer.ClassFileImporter;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static org.assertj.core.api.Assertions.assertThat;

class KernelArchitectureTest {

    @Test
    void coreDoesNotDependOnPersistenceRuntimeClientOrMetadataImplementation() {
        var imported = new ClassFileImporter().importPackages("com.dylan.agent.kernel.core");

        noClasses().that().resideInAPackage("com.dylan.agent.kernel.core..")
                .should().dependOnClassesThat().resideInAnyPackage(
                        "com.dylan.agent.persistence..",
                        "com.dylan.agent.client..",
                        "com.dylan.agent.metadata..internal..",
                        "com.dylan.agent.conversation..")
                .check(imported);
    }

    @Test
    void kernelUncheckedCastIsOnlyInTypedRegistrationInvoker() throws IOException {
        Path root = Path.of("..", "agent-service", "src", "main", "java")
                .normalize().toAbsolutePath();
        List<Path> offenders;
        try (var stream = Files.walk(root.resolve("com/dylan/agent/kernel"))) {
            offenders = stream
                    .filter(path -> path.toString().endsWith(".java"))
                    .filter(path -> contains(path, "@SuppressWarnings(\"unchecked\")")
                            || contains(path, "@SuppressWarnings({\"unchecked\""))
                    .filter(path -> !path.endsWith("TypedRegistrationInvoker.java"))
                    .toList();
        }

        assertThat(offenders).isEmpty();
    }

    @Test
    void coreDoesNotContainCapabilityOrDomainLiteralBranches() throws IOException {
        Path root = Path.of("..", "agent-service", "src", "main", "java",
                "com", "dylan", "agent", "kernel", "core")
                .normalize().toAbsolutePath();
        List<Path> offenders;
        try (var stream = Files.walk(root)) {
            offenders = stream
                    .filter(path -> path.toString().endsWith(".java"))
                    .filter(path -> {
                        String text = read(path);
                        return text.contains("\"query.search\"")
                                || text.contains("\"aggregate.compute\"")
                                || text.contains("\"employee\"")
                                || text.contains("\"transaction\"");
                    })
                    .toList();
        }

        assertThat(offenders).isEmpty();
    }

    private static boolean contains(Path path, String needle) {
        return read(path).contains(needle);
    }

    private static String read(Path path) {
        try {
            return Files.readString(path);
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }
}
