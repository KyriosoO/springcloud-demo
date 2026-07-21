package com.dylan.agent.client;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.AgentRuntimeContract;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.api.contract.runtime.plan.ExecutablePlan;
import com.dylan.agent.api.contract.runtime.plan.PlanOutcome;
import com.dylan.agent.api.contract.runtime.plan.PlanRequest;
import com.dylan.agent.api.contract.runtime.route.RouteDecision;
import com.dylan.agent.api.contract.runtime.route.RouteOutcome;
import com.dylan.agent.api.contract.runtime.route.RouteRequest;
import com.dylan.agent.config.AgentProperties;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;

import java.time.Duration;
import java.time.Instant;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

@DisplayName("AgentRuntimeClient Route/Plan contract")
class AgentRuntimeClientContractTest {

    private static final Instant DEADLINE = Instant.parse("2026-07-02T10:00:30Z");

    private MockRestServiceServer server;
    private AgentRuntimeClient client;

    @BeforeEach
    void setUp() {
        ObjectMapper mapper = JsonMapper.builder()
                .findAndAddModules()
                .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, true)
                .build();
        RestClient.Builder builder = RestClient.builder()
                .baseUrl("http://runtime")
                .messageConverters(converters ->
                        converters.add(0, new MappingJackson2HttpMessageConverter(mapper)));
        server = MockRestServiceServer.bindTo(builder).build();
        client = new AgentRuntimeClient(builder.build(), mapper, properties());
    }

    @Test
    void routeCallsRouteEndpointWithInternalCredentialOnly() {
        server.expect(requestTo("http://runtime/runtime/v1/route"))
                .andExpect(header("X-Agent-Runtime-Key", "runtime-key"))
                .andExpect(request -> {
                    HttpHeaders headers = request.getHeaders();
                    assertThat(headers.getFirst(HttpHeaders.AUTHORIZATION)).isNull();
                    assertThat(headers.getFirst(HttpHeaders.COOKIE)).isNull();
                })
                .andRespond(withSuccess(routeDecision("req-1", RuntimeOperationType.ROUTE), MediaType.APPLICATION_JSON));

        RouteOutcome outcome = client.route(routeRequest("req-1"));

        assertThat(outcome).isInstanceOf(RouteDecision.class);
        assertThat(outcome.getRequestId()).isEqualTo("req-1");
        assertThat(outcome.getMetadata().getOperation()).isEqualTo(RuntimeOperationType.ROUTE);
        server.verify();
    }

    @Test
    void planCallsPlanEndpointAndParsesExecutableOutcome() {
        server.expect(requestTo("http://runtime/runtime/v1/plan"))
                .andExpect(header("X-Agent-Runtime-Key", "runtime-key"))
                .andRespond(withSuccess(executablePlan("req-1"), MediaType.APPLICATION_JSON));

        PlanOutcome outcome = client.plan(planRequest("req-1"));

        assertThat(outcome).isInstanceOf(ExecutablePlan.class);
        assertThat(outcome.getRequestId()).isEqualTo("req-1");
        assertThat(outcome.getMetadata().getOperation()).isEqualTo(RuntimeOperationType.PLAN);
        server.verify();
    }

    @Test
    void rejectsMismatchedOutcomeRequestId() {
        server.expect(requestTo("http://runtime/runtime/v1/route"))
                .andRespond(withSuccess(routeDecision("other", RuntimeOperationType.ROUTE), MediaType.APPLICATION_JSON));

        assertThatThrownBy(() -> client.route(routeRequest("req-1")))
                .isInstanceOfSatisfying(RuntimeOperationException.class, ex -> {
                    assertThat(ex.operation()).isEqualTo(RuntimeOperationType.ROUTE);
                    assertThat(ex.failure()).isEqualTo(RuntimeOperationFailure.PROTOCOL);
                });
    }

    @Test
    void rejectsMismatchedMetadataOperation() {
        server.expect(requestTo("http://runtime/runtime/v1/route"))
                .andRespond(withSuccess(routeDecision("req-1", RuntimeOperationType.PLAN), MediaType.APPLICATION_JSON));

        assertThatThrownBy(() -> client.route(routeRequest("req-1")))
                .isInstanceOfSatisfying(RuntimeOperationException.class, ex ->
                        assertThat(ex.failure()).isEqualTo(RuntimeOperationFailure.PROTOCOL));
    }

    @Test
    void rejectsImpossibleMetadataAttemptCounts() {
        server.expect(requestTo("http://runtime/runtime/v1/route"))
                .andRespond(withSuccess(
                        routeDecision("req-1", RuntimeOperationType.ROUTE)
                                .replace("\"repairAttempts\": 0", "\"repairAttempts\": 1"),
                        MediaType.APPLICATION_JSON));

        assertThatThrownBy(() -> client.route(routeRequest("req-1")))
                .isInstanceOfSatisfying(RuntimeOperationException.class, ex ->
                        assertThat(ex.failure()).isEqualTo(RuntimeOperationFailure.PROTOCOL));
    }

    @Test
    void mapsRuntimeErrorResponseToTypedException() {
        server.expect(requestTo("http://runtime/runtime/v1/plan"))
                .andRespond(withStatus(HttpStatus.GATEWAY_TIMEOUT)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body(runtimeError("req-1")));

        assertThatThrownBy(() -> client.plan(planRequest("req-1")))
                .isInstanceOfSatisfying(RuntimeOperationException.class, ex -> {
                    assertThat(ex.operation()).isEqualTo(RuntimeOperationType.PLAN);
                    assertThat(ex.failure()).isEqualTo(RuntimeOperationFailure.DEADLINE);
                    assertThat(ex.diagnosticId()).isEqualTo("diag-runtime");
                    assertThat(ex.audit().runtimeMetadata()).isPresent();
                });
    }

    @Test
    void rejectsRuntimeErrorWithoutRequiredMetadata() {
        server.expect(requestTo("http://runtime/runtime/v1/plan"))
                .andRespond(withStatus(HttpStatus.GATEWAY_TIMEOUT)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body(runtimeErrorWithoutMetadata("req-1")));

        assertThatThrownBy(() -> client.plan(planRequest("req-1")))
                .isInstanceOfSatisfying(RuntimeOperationException.class, ex ->
                        assertThat(ex.failure()).isEqualTo(RuntimeOperationFailure.PROTOCOL));
    }

    private static AgentProperties properties() {
        AgentProperties properties = new AgentProperties();
        AgentProperties.RuntimeProperties runtime = new AgentProperties.RuntimeProperties();
        runtime.setBaseUrl("http://runtime");
        runtime.setSharedKey("runtime-key");
        runtime.setConnectTimeout(Duration.ofSeconds(1));
        runtime.setReadTimeout(Duration.ofSeconds(1));
        runtime.setMaxResponseBytes(4096);
        properties.setRuntime(runtime);
        return properties;
    }

    private static RouteRequest routeRequest(String requestId) {
        RouteRequest request = new RouteRequest();
        request.setRequestId(requestId);
        request.setContractVersion(AgentRuntimeContract.VERSION);
        request.setMessage("岗位是 HRM");
        request.setAbsoluteDeadline(DEADLINE);
        request.setRepairLimit(1);
        return request;
    }

    private static PlanRequest planRequest(String requestId) {
        PlanRequest request = new PlanRequest();
        request.setRequestId(requestId);
        request.setContractVersion(AgentRuntimeContract.VERSION);
        request.setMessage("岗位是 HRM");
        request.setCapabilityId("query.search");
        request.setPlanKind(AgentPlanKind.QUERY);
        request.setInputSchemaRef("#/components/schemas/QueryAgentPlan");
        request.setDomain("employee");
        request.setAbsoluteDeadline(DEADLINE);
        request.setRepairLimit(1);
        return request;
    }

    private static String routeDecision(String requestId, RuntimeOperationType operation) {
        return """
                {
                  "outcomeType": "DECISION",
                  "requestId": "%s",
                  "capabilityId": "query.search",
                  "domain": "employee",
                  "metadata": %s
                }
                """.formatted(requestId, metadata(operation));
    }

    private static String executablePlan(String requestId) {
        return """
                {
                  "outcomeType": "EXECUTABLE",
                  "requestId": "%s",
                  "plan": {
                    "planKind": "QUERY",
                    "query": {
                      "filters": [],
                      "selectFields": ["chineseName"],
                      "page": 1,
                      "size": 20
                    }
                  },
                  "metadata": %s
                }
                """.formatted(requestId, metadata(RuntimeOperationType.PLAN));
    }

    private static String runtimeError(String requestId) {
        return """
                {
                  "requestId": "%s",
                  "code": "DEADLINE_EXCEEDED",
                  "message": "deadline exceeded",
                  "metadata": %s,
                  "diagnosticId": "diag-runtime"
                }
                """.formatted(requestId, metadata(RuntimeOperationType.PLAN));
    }

    private static String runtimeErrorWithoutMetadata(String requestId) {
        return """
                {
                  "requestId": "%s",
                  "code": "DEADLINE_EXCEEDED",
                  "message": "deadline exceeded",
                  "diagnosticId": "diag-runtime"
                }
                """.formatted(requestId);
    }

    private static String metadata(RuntimeOperationType operation) {
        return """
                {
                  "operation": "%s",
                  "providerAttempts": 1,
                  "repairAttempts": 0,
                  "repairDurationMs": 0,
                  "totalDurationMs": 12,
                  "terminationReason": "COMPLETED",
                  "deadlineReached": false,
                  "repairLimitReached": false
                }
                """.formatted(operation.name());
    }
}
