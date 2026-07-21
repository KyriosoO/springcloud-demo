package com.dylan.agent.kernel;

import com.tngtech.archunit.core.importer.ClassFileImporter;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

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
        Path root = Path.of("..", "agent-service", "src", "main", "java")
                .normalize().toAbsolutePath();
        List<String> offenders = new ArrayList<>();
        try (var stream = Files.walk(root.resolve("com/dylan/agent/kernel"))) {
            stream.filter(path -> path.toString().endsWith(".java"))
                    .forEach(path -> offenders.addAll(literalBranchOffenders(path)));
        }
        try (var stream = Files.walk(root.resolve("com/dylan/agent/metadata"))) {
            stream.filter(path -> path.toString().endsWith(".java"))
                    .forEach(path -> offenders.addAll(literalBranchOffenders(path)));
        }

        assertThat(offenders).isEmpty();
    }

    @Test
    void coreDoesNotContainCapabilityOrDomainLiterals() throws IOException {
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

    @Test
    void productionSourcesDoNotKeepLegacyCapabilityHandlerChain() throws IOException {
        Path root = Path.of("..", "agent-service", "src", "main", "java")
                .normalize().toAbsolutePath();
        List<String> forbidden = List.of(
                "AgentCapabilityHandlerRegistry",
                "CapabilityRouter",
                "CapabilityRouteResolver",
                "ClarifyCapabilityHandler",
                "CapabilityDescriptorFactory");
        List<Path> offenders;
        try (var stream = Files.walk(root.resolve("com/dylan/agent"))) {
            offenders = stream
                    .filter(path -> path.toString().endsWith(".java"))
                    .filter(path -> {
                        String text = read(path);
                        return forbidden.stream().anyMatch(text::contains);
                    })
                    .toList();
        }

        assertThat(offenders).isEmpty();
    }

    @Test
    void d03ProductionConfigurationDoesNotUseConditionalBeans() {
        Path root = Path.of("..", "agent-service", "src", "main", "java")
                .normalize().toAbsolutePath();
        List<Path> configs = List.of(
                root.resolve("com/dylan/agent/planning/PlanningConfiguration.java"),
                root.resolve("com/dylan/agent/metadata/config/AgentMetadataSecurityConfiguration.java"));

        assertThat(configs)
                .allSatisfy(path -> assertThat(read(path))
                        .doesNotContain("@ConditionalOnBean")
                        .doesNotContain("@ConditionalOnMissingBean"));
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

    private static List<String> literalBranchOffenders(Path path) {
        Pattern ifByIdentifier = Pattern.compile(
                "if\\s*\\([^)]*(capabilityId|domain)[^)]*(equals|==)\\s*\\(\\s*\"");
        Pattern ifByLiteral = Pattern.compile(
                "if\\s*\\([^)]*\"(query\\.search|aggregate\\.compute|employee|transaction)\"");
        Pattern switchByIdentifier = Pattern.compile(
                "switch\\s*\\([^)]*(capabilityId|domain)");
        List<String> offenders = new ArrayList<>();
        List<String> lines;
        try {
            lines = Files.readAllLines(path);
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
        for (int index = 0; index < lines.size(); index++) {
            String line = lines.get(index);
            if (ifByIdentifier.matcher(line).find()
                    || ifByLiteral.matcher(line).find()
                    || switchByIdentifier.matcher(line).find()) {
                offenders.add(path + ":" + (index + 1) + ":" + line.trim());
            }
        }
        return offenders;
    }
}
