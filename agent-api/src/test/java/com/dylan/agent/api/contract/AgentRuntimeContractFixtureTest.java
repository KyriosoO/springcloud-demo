package com.dylan.agent.api.contract;

import com.dylan.agent.api.contract.runtime.clarification.CapabilityChoiceArgs;
import com.dylan.agent.api.contract.runtime.clarification.ClarificationArgs;
import com.dylan.agent.api.contract.runtime.clarification.ClarificationReasonCode;
import com.dylan.agent.api.contract.runtime.clarification.ClarificationRequired;
import com.dylan.agent.api.contract.runtime.clarification.DomainChoiceArgs;
import com.dylan.agent.api.contract.runtime.clarification.FieldChoiceArgs;
import com.dylan.agent.api.contract.runtime.clarification.ValueChoiceArgs;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.AgentRuntimeContract;
import com.dylan.agent.api.contract.runtime.common.RuntimeCapabilityRoutingDescriptor;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.runtime.common.RuntimeDomainFieldSchema;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationMetadata;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.api.contract.runtime.common.RuntimeTerminationReason;
import com.dylan.agent.api.contract.runtime.error.RuntimeErrorCode;
import com.dylan.agent.api.contract.runtime.error.RuntimeErrorResponse;
import com.dylan.agent.api.contract.runtime.plan.AggregateAgentPlan;
import com.dylan.agent.api.contract.runtime.plan.ExecutablePlan;
import com.dylan.agent.api.contract.runtime.plan.PlanOutcome;
import com.dylan.agent.api.contract.runtime.plan.PlanRequest;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.contract.runtime.route.RouteDecision;
import com.dylan.agent.api.contract.runtime.route.RouteOutcome;
import com.dylan.agent.api.contract.runtime.route.RouteRequest;
import com.dylan.agent.api.plan.AgentAggregateSpec;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.api.plan.AggregateMetricSpec;
import com.dylan.agent.api.plan.AggregateOrderSpec;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.QueryContextMode;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.exc.InvalidTypeIdException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import org.hibernate.validator.messageinterpolation.ParameterMessageInterpolator;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

@DisplayName("D01 contract fixtures")
class AgentRuntimeContractFixtureTest {

    private static final Path FIXTURE_DIR = Path.of(
        "src/test/resources/contract/fixtures");
    private static final ObjectMapper MAPPER = strictMapper();
    private static final Validator VALIDATOR = Validation.byDefaultProvider().configure()
        .messageInterpolator(new ParameterMessageInterpolator())
        .buildValidatorFactory()
        .getValidator();

    @Test
    void shouldRoundTripRouteRequest() throws Exception {
        String json = readFixture("route-request.json");
        RouteRequest value = MAPPER.readValue(json, RouteRequest.class);
        validateBean(value);
        assertRouteRequestWellFormed(value);
        assertEquals(MAPPER.readTree(json), MAPPER.readTree(MAPPER.writeValueAsString(value)));
    }

    @Test
    void shouldRoundTripRouteDecision() throws Exception {
        RouteRequest request = MAPPER.readValue(readFixture("route-request.json"), RouteRequest.class);
        String json = readFixture("route-decision.json");
        RouteOutcome value = MAPPER.readValue(json, RouteOutcome.class);
        validateBean(value);
        assertRouteOutcomeBound(request, value);
        assertEquals(MAPPER.readTree(json), MAPPER.readTree(MAPPER.writeValueAsString(value)));
    }

    @Test
    void shouldRoundTripRouteClarification() throws Exception {
        RouteRequest request = MAPPER.readValue(readFixture("route-request.json"), RouteRequest.class);
        String json = readFixture("route-clarification.json");
        RouteOutcome value = MAPPER.readValue(json, RouteOutcome.class);
        validateBean(value);
        assertRouteOutcomeBound(request, value);
        assertEquals(MAPPER.readTree(json), MAPPER.readTree(MAPPER.writeValueAsString(value)));
    }

    @Test
    void shouldRoundTripPlanRequest() throws Exception {
        String json = readFixture("plan-request.json");
        PlanRequest value = MAPPER.readValue(json, PlanRequest.class);
        validateBean(value);
        assertPlanRequestWellFormed(value);
        assertEquals(MAPPER.readTree(json), MAPPER.readTree(MAPPER.writeValueAsString(value)));
    }

    @Test
    void shouldRoundTripQueryPlan() throws Exception {
        PlanRequest request = MAPPER.readValue(readFixture("plan-request.json"), PlanRequest.class);
        String json = readFixture("query-plan.json");
        PlanOutcome value = MAPPER.readValue(json, PlanOutcome.class);
        validateBean(value);
        assertPlanOutcomeBound(request, value);
        assertEquals(MAPPER.readTree(json), MAPPER.readTree(MAPPER.writeValueAsString(value)));
    }

    @Test
    void shouldRoundTripAggregatePlan() throws Exception {
        String json = readFixture("aggregate-plan.json");
        PlanOutcome value = MAPPER.readValue(json, PlanOutcome.class);
        validateBean(value);
        assertInstanceOf(AggregateAgentPlan.class, ((ExecutablePlan) value).getPlan());
        assertMetadata(value.getMetadata(), RuntimeOperationType.PLAN);
        assertEquals(MAPPER.readTree(json), MAPPER.readTree(MAPPER.writeValueAsString(value)));
    }

    @Test
    void shouldRoundTripPlanClarification() throws Exception {
        PlanRequest request = MAPPER.readValue(readFixture("plan-request.json"), PlanRequest.class);
        String json = readFixture("plan-clarification.json");
        PlanOutcome value = MAPPER.readValue(json, PlanOutcome.class);
        validateBean(value);
        assertPlanOutcomeBound(request, value);
        assertPlanClarificationAuthorized(request, (ClarificationRequired) value);
        assertEquals(MAPPER.readTree(json), MAPPER.readTree(MAPPER.writeValueAsString(value)));
    }

    @Test
    void shouldRoundTripRuntimeError() throws Exception {
        String json = readFixture("runtime-error.json");
        RuntimeErrorResponse value = MAPPER.readValue(json, RuntimeErrorResponse.class);
        validateBean(value);
        assertRuntimeErrorBinding(value);
        assertEquals(MAPPER.readTree(json), MAPPER.readTree(MAPPER.writeValueAsString(value)));

        Map<RuntimeErrorCode, RuntimeTerminationReason> bindings = new EnumMap<>(RuntimeErrorCode.class);
        bindings.put(RuntimeErrorCode.CONTRACT_INVALID, RuntimeTerminationReason.VALIDATION_REJECTED);
        bindings.put(RuntimeErrorCode.AUTHENTICATION_FAILED, RuntimeTerminationReason.AUTHENTICATION_REJECTED);
        bindings.put(RuntimeErrorCode.PROVIDER_UNAVAILABLE, RuntimeTerminationReason.PROVIDER_UNAVAILABLE);
        bindings.put(RuntimeErrorCode.DEADLINE_EXCEEDED, RuntimeTerminationReason.DEADLINE_EXCEEDED);
        bindings.put(RuntimeErrorCode.OUTPUT_REPAIR_EXHAUSTED, RuntimeTerminationReason.REPAIR_EXHAUSTED);
        bindings.put(RuntimeErrorCode.INTERNAL_ERROR, RuntimeTerminationReason.INTERNAL_ERROR);
        bindings.forEach((code, termination) -> {
            value.setCode(code);
            value.getMetadata().setTerminationReason(termination);
            value.getMetadata().setDeadlineReached(termination == RuntimeTerminationReason.DEADLINE_EXCEEDED);
            value.getMetadata().setRepairLimitReached(termination == RuntimeTerminationReason.REPAIR_EXHAUSTED);
            assertDoesNotThrow(() -> assertRuntimeErrorBinding(value));
        });
        value.setCode(RuntimeErrorCode.CONTRACT_INVALID);
        value.getMetadata().setTerminationReason(RuntimeTerminationReason.INTERNAL_ERROR);
        assertThrows(AssertionError.class, () -> assertRuntimeErrorBinding(value));
    }

    @Test
    void shouldValidateEveryClarificationBinding() {
        List<ClarificationRequired> valid = new ArrayList<>();

        CapabilityChoiceArgs capabilities = new CapabilityChoiceArgs();
        capabilities.setCapabilityIds(List.of("query", "aggregate"));
        DomainChoiceArgs domainRequired = new DomainChoiceArgs();
        domainRequired.setDomains(List.of("employee"));
        DomainChoiceArgs domainAmbiguous = new DomainChoiceArgs();
        domainAmbiguous.setDomains(List.of("employee", "transaction"));
        FieldChoiceArgs fields = new FieldChoiceArgs();
        fields.setFields(List.of("name"));
        ValueChoiceArgs valueRequired = new ValueChoiceArgs();
        valueRequired.setField("name");
        valueRequired.setValues(List.of());
        ValueChoiceArgs valueAmbiguous = new ValueChoiceArgs();
        valueAmbiguous.setField("name");
        valueAmbiguous.setValues(List.of("张", "章"));

        List<ClarificationReasonCode> reasons = List.of(
            ClarificationReasonCode.CAPABILITY_AMBIGUOUS,
            ClarificationReasonCode.DOMAIN_REQUIRED,
            ClarificationReasonCode.DOMAIN_AMBIGUOUS,
            ClarificationReasonCode.FIELD_REQUIRED,
            ClarificationReasonCode.VALUE_REQUIRED,
            ClarificationReasonCode.VALUE_AMBIGUOUS);
        List<ClarificationArgs> arguments = List.of(
            capabilities, domainRequired, domainAmbiguous, fields, valueRequired, valueAmbiguous);
        List<RuntimeOperationType> operations = List.of(
            RuntimeOperationType.ROUTE, RuntimeOperationType.ROUTE, RuntimeOperationType.ROUTE,
            RuntimeOperationType.PLAN, RuntimeOperationType.PLAN, RuntimeOperationType.PLAN);
        for (int index = 0; index < reasons.size(); index++) {
            RuntimeOperationMetadata metadata = new RuntimeOperationMetadata();
            metadata.setOperation(operations.get(index));
            metadata.setProviderAttempts(1);
            metadata.setRepairAttempts(0);
            metadata.setRepairDurationMs(0L);
            metadata.setTotalDurationMs(1L);
            metadata.setTerminationReason(RuntimeTerminationReason.CLARIFICATION);
            metadata.setDeadlineReached(false);
            metadata.setRepairLimitReached(false);
            ClarificationRequired clarification = new ClarificationRequired();
            clarification.setRequestId("binding-" + index);
            clarification.setReasonCode(reasons.get(index));
            clarification.setArgs(arguments.get(index));
            clarification.setMetadata(metadata);
            valid.add(clarification);
        }
        valid.forEach(clarification -> assertDoesNotThrow(() ->
            assertClarificationBinding(clarification, clarification.getMetadata().getOperation())));

        ClarificationRequired wrongOperation = valid.getFirst();
        wrongOperation.getMetadata().setOperation(RuntimeOperationType.PLAN);
        assertThrows(AssertionError.class, () ->
            assertClarificationBinding(wrongOperation, RuntimeOperationType.PLAN));
        wrongOperation.getMetadata().setOperation(RuntimeOperationType.ROUTE);

        ClarificationRequired wrongArgs = valid.getFirst();
        wrongArgs.setArgs(domainRequired);
        assertThrows(AssertionError.class, () ->
            assertClarificationBinding(wrongArgs, RuntimeOperationType.ROUTE));
        wrongArgs.setArgs(capabilities);

        capabilities.setCapabilityIds(List.of("query"));
        assertThrows(AssertionError.class, () ->
            assertClarificationBinding(valid.getFirst(), RuntimeOperationType.ROUTE));

        domainRequired.setDomains(List.of("employee", "employee"));
        assertThrows(AssertionError.class, () ->
            assertClarificationBinding(valid.get(1), RuntimeOperationType.ROUTE));
    }

    @Test
    void shouldRejectUnknownPlanKind() throws Exception {
        InvalidTypeIdException error = assertThrows(InvalidTypeIdException.class, () ->
            MAPPER.readValue(readFixture("negative/unknown-plan-kind.json"), PlanOutcome.class));
        assertEquals("UPDATE", error.getTypeId());
    }

    @Test
    void shouldRejectUnknownOperator() throws Exception {
        JsonProcessingException error = assertThrows(JsonProcessingException.class, () ->
            MAPPER.readValue(readFixture("negative/unknown-operator.json"), PlanOutcome.class));
        assertTrue(error.getMessage().contains("operator"), error.getMessage());
    }

    @Test
    void shouldRejectExtraField() throws Exception {
        JsonProcessingException error = assertThrows(JsonProcessingException.class, () ->
            MAPPER.readValue(readFixture("negative/extra-field.json"), PlanOutcome.class));
        assertTrue(error.getMessage().contains("extraField"), error.getMessage());
    }

    @Test
    void shouldRejectMissingQuery() throws Exception {
        PlanOutcome value = MAPPER.readValue(
            readFixture("negative/missing-query.json"), PlanOutcome.class);
        AssertionError error = assertThrows(AssertionError.class, () -> validateBean(value));
        assertTrue(error.getMessage().contains("plan.query"), error.getMessage());
    }

    @Test
    void shouldRejectDiscriminatorMismatch() throws Exception {
        JsonProcessingException error = assertThrows(JsonProcessingException.class, () ->
            MAPPER.readValue(readFixture("negative/discriminator-mismatch.json"), PlanOutcome.class));
        assertTrue(error.getMessage().contains("aggregate") || error.getMessage().contains("query"),
            error.getMessage());
    }

    @Test
    void shouldValidateRouteToPlanFixtureChain() throws Exception {
        RouteRequest route = MAPPER.readValue(readFixture("route-request.json"), RouteRequest.class);
        RouteDecision decision = (RouteDecision) MAPPER.readValue(
            readFixture("route-decision.json"), RouteOutcome.class);
        PlanRequest plan = MAPPER.readValue(readFixture("plan-request.json"), PlanRequest.class);
        ExecutablePlan outcome = (ExecutablePlan) MAPPER.readValue(
            readFixture("query-plan.json"), PlanOutcome.class);

        assertEquals(Set.of("flow-001"), new HashSet<>(List.of(
            route.getRequestId(), decision.getRequestId(), plan.getRequestId(), outcome.getRequestId())));
        assertEquals(route.getContractVersion(), plan.getContractVersion());
        assertEquals(route.getAbsoluteDeadline(), plan.getAbsoluteDeadline());
        assertEquals(decision.getCapabilityId(), plan.getCapabilityId());
        assertEquals(plan.getCapabilityId(), plan.getCapability().getCapabilityId());
        assertEquals(decision.getDomain(), plan.getDomain());
        assertEquals(plan.getDomain(), plan.getDomainSchema().getDomain());
        assertEquals(plan.getPlanKind(), outcome.getPlan().getPlanKind());
        assertInstanceOf(QueryAgentPlan.class, outcome.getPlan());
    }

    private static String readFixture(String name) throws IOException {
        return Files.readString(FIXTURE_DIR.resolve(name), StandardCharsets.UTF_8);
    }

    private static ObjectMapper strictMapper() {
        return new ObjectMapper()
            .registerModule(new JavaTimeModule())
            .enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
            .enable(DeserializationFeature.FAIL_ON_INVALID_SUBTYPE)
            .enable(DeserializationFeature.FAIL_ON_NULL_FOR_PRIMITIVES)
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    }

    private static void validateBean(Object value) {
        Set<ConstraintViolation<Object>> violations = VALIDATOR.validate(value);
        if (!violations.isEmpty()) {
            String details = violations.stream()
                .map(violation -> violation.getPropertyPath() + " " + violation.getMessage())
                .sorted()
                .collect(Collectors.joining("; "));
            throw new AssertionError(details);
        }
    }

    private static void assertRouteRequestWellFormed(RouteRequest request) {
        assertEquals(AgentRuntimeContract.VERSION, request.getContractVersion());
        Map<String, RuntimeCapabilityRoutingDescriptor> capabilities = request.getCapabilities().stream()
            .collect(Collectors.toMap(RuntimeCapabilityRoutingDescriptor::getCapabilityId, value -> value));
        assertEquals(request.getCapabilities().size(), capabilities.size());
        Set<String> domains = request.getDomains().stream()
            .map(value -> value.getDomain()).collect(Collectors.toSet());
        assertEquals(request.getDomains().size(), domains.size());
        Set<String> referenced = new HashSet<>();
        request.getCapabilities().forEach(capability -> {
            assertEquals(capability.getAllowedDomains().size(),
                new HashSet<>(capability.getAllowedDomains()).size());
            if (capability.getDomainMode() == AgentDomainMode.NONE) {
                assertTrue(capability.getAllowedDomains().isEmpty());
            }
            if (capability.getDomainMode() == AgentDomainMode.REQUIRED) {
                assertFalse(capability.getAllowedDomains().isEmpty());
            }
            assertTrue(domains.containsAll(capability.getAllowedDomains()));
            referenced.addAll(capability.getAllowedDomains());
        });
        assertEquals(domains, referenced);
        assertNotNull(request.getAbsoluteDeadline());
    }

    private static void assertRouteOutcomeBound(RouteRequest request, RouteOutcome outcome) {
        assertEquals(request.getRequestId(), outcome.getRequestId());
        assertMetadata(outcome.getMetadata(), RuntimeOperationType.ROUTE);
        if (outcome instanceof ClarificationRequired clarification) {
            assertClarificationBinding(clarification, RuntimeOperationType.ROUTE);
            return;
        }
        RouteDecision decision = assertInstanceOf(RouteDecision.class, outcome);
        RuntimeCapabilityRoutingDescriptor capability = request.getCapabilities().stream()
            .filter(value -> value.getCapabilityId().equals(decision.getCapabilityId()))
            .findFirst().orElseThrow(() -> new AssertionError("unknown capabilityId"));
        if (capability.getDomainMode() == AgentDomainMode.NONE) {
            assertNull(decision.getDomain());
        } else if (capability.getDomainMode() == AgentDomainMode.REQUIRED) {
            assertNotNull(decision.getDomain());
        }
        if (decision.getDomain() != null) {
            assertTrue(capability.getAllowedDomains().contains(decision.getDomain()));
        }
    }

    private static void assertPlanRequestWellFormed(PlanRequest request) {
        assertEquals(AgentRuntimeContract.VERSION, request.getContractVersion());
        assertEquals(request.getCapabilityId(), request.getCapability().getCapabilityId());
        assertEquals(request.getPlanKind(), request.getCapability().getPlanKind());
        assertEquals(request.getPlanKind() == AgentPlanKind.QUERY
                ? "#/components/schemas/QueryAgentPlan"
                : "#/components/schemas/AggregateAgentPlan",
            request.getInputSchemaRef());
        AgentDomainMode mode = request.getCapability().getDomainMode();
        if (mode == AgentDomainMode.NONE) {
            assertNull(request.getDomain());
            assertNull(request.getDomainSchema());
        } else if (mode == AgentDomainMode.REQUIRED) {
            assertNotNull(request.getDomain());
            assertNotNull(request.getDomainSchema());
        }
        if (request.getDomain() != null) {
            assertTrue(request.getCapability().getAllowedDomains().contains(request.getDomain()));
        }
        if (request.getDomainSchema() != null) {
            assertEquals(request.getDomain(), request.getDomainSchema().getDomain());
            Set<String> fields = request.getDomainSchema().getFields().stream()
                .map(RuntimeDomainFieldSchema::getField).collect(Collectors.toSet());
            assertEquals(request.getDomainSchema().getFields().size(), fields.size());
        }
        Set<RuntimeContextType> contextTypes = request.getContextViews().stream()
            .map(value -> value.getContextType()).collect(Collectors.toSet());
        assertEquals(request.getContextViews().size(), contextTypes.size());
        assertNotNull(request.getAbsoluteDeadline());
    }

    private static void assertPlanOutcomeBound(PlanRequest request, PlanOutcome outcome) {
        assertEquals(request.getRequestId(), outcome.getRequestId());
        assertMetadata(outcome.getMetadata(), RuntimeOperationType.PLAN);
        if (outcome instanceof ClarificationRequired clarification) {
            assertClarificationBinding(clarification, RuntimeOperationType.PLAN);
            return;
        }
        ExecutablePlan executable = assertInstanceOf(ExecutablePlan.class, outcome);
        assertEquals(request.getPlanKind(), executable.getPlan().getPlanKind());
        Set<String> fields = new HashSet<>();
        if (request.getDomainSchema() != null) {
            fields.addAll(request.getDomainSchema().getFields().stream()
                .map(RuntimeDomainFieldSchema::getField).toList());
            fields.addAll(request.getDomainSchema().getDefaultSelectFields());
        }
        Map<String, RuntimeDomainFieldSchema> fieldSchemas = request.getDomainSchema() == null
            ? Map.of() : request.getDomainSchema().getFields().stream()
                .collect(Collectors.toMap(RuntimeDomainFieldSchema::getField, value -> value));
        if (executable.getPlan() instanceof QueryAgentPlan queryPlan) {
            AgentQuerySpec query = queryPlan.getQuery();
            if (query.getContextMode() != QueryContextMode.MERGE) {
                assertTrue(query.getRemoveFields() == null || query.getRemoveFields().isEmpty());
            }
            if (!fields.isEmpty()) {
                assertTrue(fields.containsAll(query.getSelectFields()));
                for (AgentFilter filter : query.getFilters()) {
                    assertTrue(fields.contains(filter.getField()));
                    assertTrue(fieldSchemas.get(filter.getField()).getOperators().contains(filter.getOperator()));
                }
            }
        } else {
            AgentAggregateSpec aggregate = ((AggregateAgentPlan) executable.getPlan()).getAggregate();
            Set<String> metricAliases = aggregate.getMetrics().stream()
                .map(AggregateMetricSpec::getAlias).collect(Collectors.toSet());
            if (!fields.isEmpty()) {
                assertTrue(fields.containsAll(aggregate.getGroupByFields()));
                for (AggregateMetricSpec metric : aggregate.getMetrics()) {
                    if (metric.getFunction() != AggregateFunction.COUNT || metric.getField() != null) {
                        assertTrue(fields.contains(metric.getField()));
                        assertTrue(fieldSchemas.get(metric.getField()).getAggregateFunctions()
                            .contains(metric.getFunction()));
                    }
                }
                for (AggregateOrderSpec order : aggregate.getOrderBy()) {
                    assertTrue(aggregate.getGroupByFields().contains(order.getField())
                        || metricAliases.contains(order.getField()));
                }
            }
        }
    }

    private static void assertClarificationBinding(
        ClarificationRequired clarification, RuntimeOperationType expected
    ) {
        assertMetadata(clarification.getMetadata(), expected);
        Map<ClarificationReasonCode, Class<? extends ClarificationArgs>> argsTypes =
            new EnumMap<>(ClarificationReasonCode.class);
        argsTypes.put(ClarificationReasonCode.CAPABILITY_AMBIGUOUS, CapabilityChoiceArgs.class);
        argsTypes.put(ClarificationReasonCode.DOMAIN_REQUIRED, DomainChoiceArgs.class);
        argsTypes.put(ClarificationReasonCode.DOMAIN_AMBIGUOUS, DomainChoiceArgs.class);
        argsTypes.put(ClarificationReasonCode.FIELD_REQUIRED, FieldChoiceArgs.class);
        argsTypes.put(ClarificationReasonCode.VALUE_REQUIRED, ValueChoiceArgs.class);
        argsTypes.put(ClarificationReasonCode.VALUE_AMBIGUOUS, ValueChoiceArgs.class);
        assertInstanceOf(argsTypes.get(clarification.getReasonCode()), clarification.getArgs());
        RuntimeOperationType requiredOperation = switch (clarification.getReasonCode()) {
            case CAPABILITY_AMBIGUOUS, DOMAIN_REQUIRED, DOMAIN_AMBIGUOUS -> RuntimeOperationType.ROUTE;
            case FIELD_REQUIRED, VALUE_REQUIRED, VALUE_AMBIGUOUS -> RuntimeOperationType.PLAN;
        };
        assertEquals(requiredOperation, expected);
        List<String> choices = switch (clarification.getArgs()) {
            case CapabilityChoiceArgs value -> value.getCapabilityIds();
            case DomainChoiceArgs value -> value.getDomains();
            case FieldChoiceArgs value -> value.getFields();
            case ValueChoiceArgs value -> value.getValues();
        };
        int count = new HashSet<>(choices).size();
        assertEquals(choices.size(), count);
        int minimum = switch (clarification.getReasonCode()) {
            case CAPABILITY_AMBIGUOUS, DOMAIN_AMBIGUOUS, VALUE_AMBIGUOUS -> 2;
            case DOMAIN_REQUIRED, FIELD_REQUIRED -> 1;
            case VALUE_REQUIRED -> 0;
        };
        assertTrue(count >= minimum);
    }

    private static void assertPlanClarificationAuthorized(
        PlanRequest request, ClarificationRequired clarification
    ) {
        assertClarificationBinding(clarification, RuntimeOperationType.PLAN);
        Set<String> fields = request.getDomainSchema() == null ? Set.of()
            : request.getDomainSchema().getFields().stream()
                .map(RuntimeDomainFieldSchema::getField).collect(Collectors.toSet());
        if (clarification.getArgs() instanceof FieldChoiceArgs choices) {
            assertTrue(fields.containsAll(choices.getFields()));
        }
        if (clarification.getArgs() instanceof ValueChoiceArgs choices) {
            assertTrue(fields.contains(choices.getField()));
        }
    }

    private static void assertMetadata(
        RuntimeOperationMetadata metadata, RuntimeOperationType expected
    ) {
        validateBean(metadata);
        assertEquals(expected, metadata.getOperation());
        assertTrue(metadata.getRepairAttempts() <= Math.max(metadata.getProviderAttempts() - 1, 0));
        assertTrue(metadata.getTotalDurationMs() >= metadata.getRepairDurationMs());
        assertEquals(metadata.getTerminationReason() == RuntimeTerminationReason.DEADLINE_EXCEEDED,
            metadata.getDeadlineReached());
        assertEquals(metadata.getTerminationReason() == RuntimeTerminationReason.REPAIR_EXHAUSTED,
            metadata.getRepairLimitReached());
    }

    private static void assertRuntimeErrorBinding(RuntimeErrorResponse error) {
        Map<RuntimeErrorCode, RuntimeTerminationReason> bindings = new EnumMap<>(RuntimeErrorCode.class);
        bindings.put(RuntimeErrorCode.CONTRACT_INVALID, RuntimeTerminationReason.VALIDATION_REJECTED);
        bindings.put(RuntimeErrorCode.AUTHENTICATION_FAILED, RuntimeTerminationReason.AUTHENTICATION_REJECTED);
        bindings.put(RuntimeErrorCode.PROVIDER_UNAVAILABLE, RuntimeTerminationReason.PROVIDER_UNAVAILABLE);
        bindings.put(RuntimeErrorCode.DEADLINE_EXCEEDED, RuntimeTerminationReason.DEADLINE_EXCEEDED);
        bindings.put(RuntimeErrorCode.OUTPUT_REPAIR_EXHAUSTED, RuntimeTerminationReason.REPAIR_EXHAUSTED);
        bindings.put(RuntimeErrorCode.INTERNAL_ERROR, RuntimeTerminationReason.INTERNAL_ERROR);
        assertEquals(bindings.get(error.getCode()), error.getMetadata().getTerminationReason());
        assertMetadata(error.getMetadata(), error.getMetadata().getOperation());
    }
}
