package com.dylan.agent.lifecycle;

import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.kernel.port.model.ApprovedContextWrite;
import com.dylan.agent.lifecycle.port.ContextFinalizationParticipant;
import com.dylan.agent.lifecycle.port.ContextScopeRetirementParticipant;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.List;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static org.assertj.core.api.Assertions.assertThat;

class LifecycleSeamArchitectureTest {

    @Test
    void invocationModelDoesNotDependOnPlanningLifecycleKernelOrMetadata() {
        var imported = new ClassFileImporter().importPackages("com.dylan.agent.invocation.model");

        noClasses().that().resideInAPackage("com.dylan.agent.invocation.model..")
                .should().dependOnClassesThat().resideInAnyPackage(
                        "com.dylan.agent.planning..",
                        "com.dylan.agent.lifecycle..",
                        "com.dylan.agent.kernel..",
                        "com.dylan.agent.metadata..")
                .check(imported);
    }

    @Test
    void contextFinalizationParticipantUsesApprovedContextWritesOnly() throws Exception {
        var method = ContextFinalizationParticipant.class.getMethod("persist", List.class);

        Type genericParameter = method.getGenericParameterTypes()[0];
        assertThat(genericParameter).isInstanceOf(ParameterizedType.class);
        Type[] arguments = ((ParameterizedType) genericParameter).getActualTypeArguments();
        assertThat(arguments).containsExactly(ApprovedContextWrite.class);
        assertThat(method.getReturnType()).isEqualTo(Void.TYPE);
    }

    @Test
    void contextScopeRetirementParticipantIsConversationScoped() throws Exception {
        var method = ContextScopeRetirementParticipant.class.getMethod(
                "retire", ConversationScope.class, Instant.class);

        assertThat(method.getReturnType()).isEqualTo(Void.TYPE);
    }

    @Test
    void lifecycleSourceDoesNotContainPartialPersistencePlaceholders() throws IOException {
        Path root = Path.of("..", "agent-service", "src", "main", "java",
                "com", "dylan", "agent", "lifecycle").normalize().toAbsolutePath();

        List<Path> offenders;
        try (var stream = Files.walk(root)) {
            offenders = stream
                    .filter(path -> path.toString().endsWith(".java"))
                    .filter(path -> {
                        String text = read(path);
                        return text.contains("not wired")
                                || text.contains("fabricate")
                                || text.contains("sha256-placeholder")
                                || text.contains("List<Object>");
                    })
                    .toList();
        }

        assertThat(offenders).isEmpty();
    }

    private static String read(Path path) {
        try {
            return Files.readString(path);
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }
}
