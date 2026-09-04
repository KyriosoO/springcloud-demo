package com.dylan.agent.service.runtime;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;

import com.dylan.agent.service.config.AgentRuntimeProperties;
import com.dylan.agent.service.contract.CapabilityStatus;
import com.dylan.agent.service.contract.RuntimeInvokeResponse;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.ClientResponse;

import reactor.test.StepVerifier;

class RuntimeContractTest {
    private final ObjectMapper mapper = new ObjectMapper()
            .findAndRegisterModules()
            .enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);
    private final WebClientAgentRuntimeClient client = new WebClientAgentRuntimeClient(properties(), mapper);

    @Test
    void consumesSharedSuccessFixtureAndRejectsContractDrift() throws Exception {
        String success = Files.readString(fixture("internal-response-success.json"));
        String invalidEnum = Files.readString(fixture("internal-response-invalid-enum.json"));
        String successWithFailure = Files.readString(fixture("internal-response-success-with-failure.json"));

        RuntimeInvokeResponse response = mapper.readValue(success, RuntimeInvokeResponse.class);
        assertThat(response.status()).isEqualTo(CapabilityStatus.SUCCESS);
        org.assertj.core.api.Assertions.assertThatThrownBy(
                () -> mapper.readValue(invalidEnum, RuntimeInvokeResponse.class)).isInstanceOf(Exception.class);
        RuntimeInvokeResponse invalidSemantics = mapper.readValue(successWithFailure, RuntimeInvokeResponse.class);
        StepVerifier.create(client.decodeResponse(json(HttpStatus.OK, successWithFailure), invalidSemantics.requestId()))
                .expectErrorSatisfies(error -> assertThat(((RuntimeClientException) error).code())
                        .isEqualTo("core.runtime_invalid_response"))
                .verify();
    }

    @Test
    void mapsEveryTransportStatusWithoutReadingItsBody() {
        assertStatus(401, "core.runtime_auth_context_invalid");
        assertStatus(429, "core.runtime_capacity_exceeded");
        assertStatus(503, "downstream.runtime_unavailable");
        assertStatus(501, "downstream.runtime_failure");
        assertStatus(302, "core.runtime_protocol_error");
        assertStatus(422, "core.runtime_protocol_error");
    }

    @Test
    void rejectsRequestIdMismatchUnknownFieldsAndWrongMediaType() throws Exception {
        String success = Files.readString(fixture("internal-response-success.json"));
        String unknown = success.replace("\"failure\": null", "\"failure\": null, \"extra\": true");

        StepVerifier.create(client.decodeResponse(json(HttpStatus.OK, success), "different"))
                .expectError(RuntimeClientException.class).verify();
        StepVerifier.create(client.decodeResponse(json(HttpStatus.OK, unknown), requestId()))
                .expectError(RuntimeClientException.class).verify();
        StepVerifier.create(client.decodeResponse(
                        ClientResponse.create(HttpStatus.OK).header("Content-Type", "text/plain").body(success).build(),
                        requestId()))
                .expectError(RuntimeClientException.class).verify();
    }

    @Test
    void rejectsInvalidCapabilityIdAndExcessiveResultDepth() throws Exception {
        String success = Files.readString(fixture("internal-response-success.json"));
        String invalidCapability = success.replace("employee.get", "invalid capability");
        String nested = "{\"value\":1}";
        for (int index = 0; index < 17; index++) {
            nested = "{\"nested\":" + nested + "}";
        }
        String excessiveDepth = success.replace("{\n    \"employeeId\": \"E-100\"\n  }", nested);

        StepVerifier.create(client.decodeResponse(json(HttpStatus.OK, invalidCapability), requestId()))
                .expectError(RuntimeClientException.class).verify();
        StepVerifier.create(client.decodeResponse(json(HttpStatus.OK, excessiveDepth), requestId()))
                .expectError(RuntimeClientException.class).verify();
    }

    @Test
    void inspectionContractAcceptsSafeProjectionAndRejectsCredentialKeys() {
        String valid = """
                {"contractVersion":1,"requestId":"%s","status":"unsupported",
                 "capabilityId":null,"answerText":"unsupported","userResult":null,
                 "failure":{"code":"core.no_enabled_capability","source":"core"},
                 "modelCalls":[{"sequence":1,"taskId":"business_query_plan","taskVersion":"v1",
                   "request":{"input":{"question":"上海员工"}},
                   "status":"failed","failureKind":"invalid_output"}],
                 "plans":[],"downstreamCalls":[]}
                """.formatted(requestId());
        String credential = valid.replace(
                "{\"input\":{\"question\":\"上海员工\"}}",
                "{\"authorization\":\"Bearer secret\"}");

        StepVerifier.create(client.decodeInspectResponse(json(HttpStatus.OK, valid), requestId()))
                .assertNext(response -> assertThat(response.modelCalls()).hasSize(1))
                .verifyComplete();
        StepVerifier.create(client.decodeInspectResponse(json(HttpStatus.OK, credential), requestId()))
                .expectError(RuntimeClientException.class)
                .verify();
    }

    private void assertStatus(int status, String code) {
        ClientResponse response = ClientResponse.create(HttpStatus.valueOf(status))
                .header("Content-Type", "application/json")
                .body("sensitive body must not be decoded")
                .build();
        StepVerifier.create(client.decodeResponse(response, "req"))
                .expectErrorSatisfies(error -> assertThat(((RuntimeClientException) error).code()).isEqualTo(code))
                .verify();
    }

    private ClientResponse json(HttpStatus status, String body) {
        return ClientResponse.create(status)
                .header("Content-Type", MediaType.APPLICATION_JSON_VALUE)
                .body(body)
                .build();
    }

    private Path fixture(String name) {
        return Path.of("..", "agent-contracts", "fixtures", name);
    }

    private String requestId() {
        return "7251cedd-6762-4fd3-874d-b1607570f0ac";
    }

    private AgentRuntimeProperties properties() {
        return new AgentRuntimeProperties(URI.create("http://127.0.0.1:8091"), 1,
                Duration.ofSeconds(1), 393216);
    }
}
