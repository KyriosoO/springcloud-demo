package com.dylan.agent.api.contract;

import com.dylan.agent.api.contract.runtime.clarification.ClarificationRequired;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.plan.AgentPlan;
import com.dylan.agent.api.contract.runtime.plan.ExecutablePlan;
import com.dylan.agent.api.contract.runtime.plan.PlanOutcome;
import com.dylan.agent.api.contract.runtime.route.RouteOutcome;
import com.dylan.agent.api.contract.runtime.route.RouteRequest;
import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

@DisplayName("Active Runtime contract architecture invariants")
class AgentRuntimeContractArchitectureTest {

    @Test
    void targetContractMustNotDependOnSpringOrServicePackages() throws Exception {
        Path source = locateRepoRoot().resolve(
            "agent-api/src/main/java/com/dylan/agent/api/contract/runtime");
        List<String> violations = scanText(source, Pattern.compile(
            "(?m)^import\\s+(org\\.springframework|com\\.dylan\\.(?!agent\\.api\\.(contract\\.runtime|plan|enums)))"));
        assertTrue(violations.isEmpty(), String.join(System.lineSeparator(), violations));
    }

    @Test
    void planKindMustContainOnlyQueryAndAggregate() {
        assertEquals(Set.of("QUERY", "AGGREGATE"), Arrays.stream(AgentPlanKind.values())
            .map(Enum::name).collect(Collectors.toSet()));
    }

    @Test
    void clarificationMustNotImplementAgentPlan() {
        assertFalse(AgentPlan.class.isAssignableFrom(ClarificationRequired.class));
    }

    @Test
    void routeRequestMustNotExposeContextOrDomainFieldSchema() {
        assertNoFieldNamed(RouteRequest.class, Set.of(
            "context", "contextView", "contextViews", "domainSchema", "domainFields"));
    }

    @Test
    void executablePlanMustNotExposeCapabilityIdPlanKindOrDomain() {
        assertNoFieldNamed(ExecutablePlan.class, Set.of("capabilityId", "planKind", "domain"));
    }

    @Test
    void targetDtosMustNotDeclarePlanVersionOrStrategyVersion() throws Exception {
        List<String> violations = scanText(locateRepoRoot().resolve(
            "agent-api/src/main/java/com/dylan/agent/api/contract/runtime"),
            Pattern.compile("(?m)^\\s*private\\s+[^;]*(planVersion|strategyVersion)\\b"));
        assertTrue(violations.isEmpty(), String.join(System.lineSeparator(), violations));
    }

    @Test
    void runtimeContractMustNotBeReferencedByUnexpectedProductionCode() throws Exception {
        Pattern runtimeContract = Pattern.compile("com\\.dylan\\.agent\\.api\\.contract\\.runtime");
        Path repo = locateRepoRoot();
        List<String> violations = new ArrayList<>();
        // D02 kernel/planning/invocation/lifecycle/metadata/shared packages
        // reference active Runtime contract types as part of the D03 target chain;
        // this is the expected design contract. Exclusion paths ensure
        // the gate only catches unintended legacy references.
        for (String result : scanText(repo.resolve("agent-service/src/main"), runtimeContract,
            "java/com/dylan/agent/kernel/",
            "java/com/dylan/agent/capability/query/QueryCapabilityConfiguration.java",
            "java/com/dylan/agent/capability/query/QueryPlanValidator.java",
            "java/com/dylan/agent/capability/query/QueryCapabilityHandler.java",
            "java/com/dylan/agent/capability/query/ValidatedQueryPlan.java",
            "java/com/dylan/agent/capability/querypreview/QueryPreviewCapabilityConfiguration.java",
            "java/com/dylan/agent/capability/querypreview/QueryPreviewPlanValidator.java",
            "java/com/dylan/agent/capability/querypreview/ValidatedQueryPreviewPlan.java",
            "java/com/dylan/agent/capability/aggregate/AggregateCapabilityConfiguration.java",
            "java/com/dylan/agent/capability/aggregate/AggregatePlanValidator.java",
            "java/com/dylan/agent/capability/aggregate/AggregateCapabilityHandler.java",
            "java/com/dylan/agent/capability/aggregate/ValidatedAggregatePlan.java",
            "java/com/dylan/agent/application/PlanningCommandFactory.java",
            "java/com/dylan/agent/client/AgentRuntimeClient.java",
            "java/com/dylan/agent/client/AgentRuntimeErrorMapper.java",
            "java/com/dylan/agent/client/RuntimeOperationException.java",
            "java/com/dylan/agent/planning/",
            "java/com/dylan/agent/conversation/ConversationService.java",
            "java/com/dylan/agent/invocation/", "java/com/dylan/agent/lifecycle/",
            "java/com/dylan/agent/metadata/", "java/com/dylan/agent/shared/")) {
            violations.add(result);
        }
        violations.addAll(scanText(repo.resolve("agent-runtime/app"), runtimeContract));
        assertTrue(violations.isEmpty(), String.join(System.lineSeparator(), violations));
    }

    @Test
    void routeAndPlanOutcomesMustRemainClosedByAnnotations() throws Exception {
        assertFalse(RouteOutcome.class.isSealed());
        assertFalse(PlanOutcome.class.isSealed());
        assertEquals(JsonTypeInfo.Id.NAME,
            RouteOutcome.class.getAnnotation(JsonTypeInfo.class).use());
        assertEquals(JsonTypeInfo.Id.NAME,
            PlanOutcome.class.getAnnotation(JsonTypeInfo.class).use());
        Set<Class<?>> routeTypes = Arrays.stream(
            RouteOutcome.class.getAnnotation(JsonSubTypes.class).value())
            .map(JsonSubTypes.Type::value).collect(Collectors.toSet());
        Set<Class<?>> planTypes = Arrays.stream(
            PlanOutcome.class.getAnnotation(JsonSubTypes.class).value())
            .map(JsonSubTypes.Type::value).collect(Collectors.toSet());
        assertEquals(Set.of(
            com.dylan.agent.api.contract.runtime.route.RouteDecision.class,
            ClarificationRequired.class), routeTypes);
        assertEquals(Set.of(ExecutablePlan.class, ClarificationRequired.class), planTypes);

        Path targetSource = locateRepoRoot().resolve(
            "agent-api/src/main/java/com/dylan/agent/api/contract/runtime");
        List<String> implementors = scanText(targetSource,
            Pattern.compile("implements\\s+[^\\n{]*(RouteOutcome|PlanOutcome)"));
        assertEquals(3, implementors.size(), String.join(System.lineSeparator(), implementors));
        assertTrue(implementors.stream().anyMatch(value -> value.contains("RouteDecision.java")));
        assertTrue(implementors.stream().anyMatch(value -> value.contains("ExecutablePlan.java")));
        assertTrue(implementors.stream().anyMatch(value -> value.contains("ClarificationRequired.java")));
    }

    private static Path locateRepoRoot() {
        for (Path current = Path.of("").toAbsolutePath(); current != null;
             current = current.getParent()) {
            if (Files.isDirectory(current.resolve("agent-api"))
                && Files.isDirectory(current.resolve("agent-runtime"))
                && Files.isDirectory(current.resolve("agent-service"))) {
                return current;
            }
        }
        throw new IllegalStateException("repository root not found");
    }

    private static Set<String> javaFields(Class<?> type) {
        return Arrays.stream(type.getDeclaredFields())
            .map(Field::getName).collect(Collectors.toSet());
    }

    private static void assertNoFieldNamed(Class<?> type, Set<String> forbidden) {
        Set<String> actual = javaFields(type);
        forbidden.forEach(name -> assertFalse(actual.contains(name), type.getName() + "." + name));
    }

    private static List<String> scanText(Path root, Pattern pattern) throws IOException {
        return scanText(root, pattern, new String[0]);
    }

    private static List<String> scanText(Path root, Pattern pattern,
            String... exclusionPaths) throws IOException {
        assertTrue(Files.isDirectory(root), "scan root not found: " + root);
        List<String> matches = new ArrayList<>();
        try (var paths = Files.walk(root)) {
            for (Path path : paths.filter(Files::isRegularFile).toList()) {
                String name = path.getFileName().toString();
                if (!(name.endsWith(".java") || name.endsWith(".py") || name.endsWith(".json"))) {
                    continue;
                }
                String relative = root.relativize(path).toString().replace("\\", "/");
                boolean excluded = false;
                for (String exclusion : exclusionPaths) {
                    if (relative.startsWith(exclusion)) {
                        excluded = true;
                        break;
                    }
                }
                if (excluded) continue;
                String text = Files.readString(path, StandardCharsets.UTF_8);
                if (pattern.matcher(text).find()) {
                    matches.add(path + ": " + pattern.pattern());
                }
            }
        }
        return matches;
    }
}
