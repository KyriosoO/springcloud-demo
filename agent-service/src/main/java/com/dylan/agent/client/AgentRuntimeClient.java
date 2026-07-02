package com.dylan.agent.client;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.time.Duration;
import java.time.Instant;
import java.util.Objects;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.beans.factory.annotation.Qualifier;

import com.dylan.agent.api.contract.runtime.common.RuntimeOperationMetadata;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.api.contract.runtime.error.RuntimeErrorCode;
import com.dylan.agent.api.contract.runtime.plan.PlanOutcome;
import com.dylan.agent.api.contract.runtime.plan.PlanRequest;
import com.dylan.agent.api.contract.runtime.route.RouteOutcome;
import com.dylan.agent.api.contract.runtime.route.RouteRequest;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.exception.AgentRuntimeException;
import com.dylan.agent.planning.model.PlanningOperationAudit;
import com.dylan.agent.planning.model.PlanningOperationTermination;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * Runtime HTTP 客户端，使用独立 RestClient。
 * 不转发用户 JWT，使用 X-Agent-Runtime-Key 内部共享密钥。
 */
@Component
public class AgentRuntimeClient {

    private final RestClient restClient;
    private final ObjectMapper objectMapper;
    private final AgentProperties properties;

    public AgentRuntimeClient(
            @Qualifier("agentRuntimeRestClient") RestClient agentRuntimeRestClient,
            ObjectMapper objectMapper,
            AgentProperties properties) {
        this.restClient = agentRuntimeRestClient;
        this.objectMapper = objectMapper;
        this.properties = properties;
    }

    public RouteOutcome route(RouteRequest request) {
        return exchangeOperation(
                RuntimeOperationType.ROUTE,
                properties.getRuntime().getRoutePath(),
                request,
                request.getRequestId(),
                RouteOutcome.class);
    }

    public PlanOutcome plan(PlanRequest request) {
        return exchangeOperation(
                RuntimeOperationType.PLAN,
                properties.getRuntime().getPlanPath(),
                request,
                request.getRequestId(),
                PlanOutcome.class);
    }

    private <T> T exchangeOperation(
            RuntimeOperationType operation,
            String uri,
            Object request,
            String requestId,
            Class<T> responseType) {
        Instant started = Instant.now();
        try {
            return restClient.post()
                    .uri(uri)
                    .header("X-Agent-Runtime-Key", properties.getRuntime().getSharedKey())
                    .body(request)
                    .exchange((httpRequest, response) -> {
                        byte[] responseBytes = readLimited(
                                response.getBody(),
                                properties.getRuntime().getMaxResponseBytes());
                        HttpStatusCode status = response.getStatusCode();
                        if (status.is2xxSuccessful()) {
                            return parseOperationSuccess(operation, responseBytes, requestId, responseType, started);
                        }
                        throw mapOperationError(operation, status, responseBytes, requestId, started);
                    });
        } catch (RuntimeOperationException ex) {
            throw ex;
        } catch (Exception ex) {
            throw operationException(
                    operation,
                    RuntimeOperationFailure.TRANSPORT,
                    notReportedAudit(operation, started, PlanningOperationTermination.TRANSPORT_FAILURE),
                    "runtime-" + operation.name().toLowerCase() + "-transport",
                    ex);
        }
    }

    private <T> T parseOperationSuccess(
            RuntimeOperationType operation,
            byte[] responseBytes,
            String expectedRequestId,
            Class<T> responseType,
            Instant started) {
        if (responseBytes == null || responseBytes.length == 0) {
            throw operationException(
                    operation,
                    RuntimeOperationFailure.PROTOCOL,
                    notReportedAudit(operation, started, PlanningOperationTermination.PROTOCOL_REJECTED),
                    "runtime-" + operation.name().toLowerCase() + "-empty",
                    null);
        }
        try {
            T outcome = objectMapper.readValue(responseBytes, responseType);
            validateOutcome(operation, expectedRequestId, outcome);
            RuntimeOperationMetadata metadata = metadata(outcome);
            if (metadata == null) {
                throw new IllegalArgumentException("metadata missing");
            }
            return outcome;
        } catch (RuntimeOperationException ex) {
            throw ex;
        } catch (Exception ex) {
            throw operationException(
                    operation,
                    RuntimeOperationFailure.PROTOCOL,
                    notReportedAudit(operation, started, PlanningOperationTermination.PROTOCOL_REJECTED),
                    "runtime-" + operation.name().toLowerCase() + "-protocol",
                    ex);
        }
    }

    private RuntimeOperationException mapOperationError(
            RuntimeOperationType operation,
            HttpStatusCode status,
            byte[] responseBytes,
            String expectedRequestId,
            Instant started) {
        ParsedRuntimeError parsed = parseOperationError(operation, responseBytes, started);
        com.dylan.agent.api.contract.runtime.error.RuntimeErrorResponse error = parsed.error();
        if (error == null) {
            return operationException(
                    operation,
                    RuntimeOperationFailure.PROTOCOL,
                    parsed.audit(),
                    "runtime-" + operation.name().toLowerCase() + "-empty-error",
                    null);
        }
        if (error.getRequestId() != null && !error.getRequestId().isBlank()
                && !Objects.equals(error.getRequestId(), expectedRequestId)) {
            return operationException(
                    operation,
                    RuntimeOperationFailure.PROTOCOL,
                    notReportedAudit(operation, started, PlanningOperationTermination.PROTOCOL_REJECTED),
                    "runtime-" + operation.name().toLowerCase() + "-request-id",
                    null);
        }
        RuntimeOperationFailure failure = mapFailure(status, error.getCode());
        PlanningOperationAudit audit = error.getMetadata() == null
                ? parsed.audit()
                : PlanningOperationAudit.reported(
                        error.getMetadata(),
                        elapsedMillis(started),
                        PlanningOperationTermination.RUNTIME_ERROR_RECEIVED);
        return operationException(operation, failure, audit, safeDiagnosticId(error.getDiagnosticId()), null);
    }

    private ParsedRuntimeError parseOperationError(
            RuntimeOperationType operation,
            byte[] responseBytes,
            Instant started) {
        if (responseBytes == null || responseBytes.length == 0) {
            return new ParsedRuntimeError(null,
                    notReportedAudit(operation, started, PlanningOperationTermination.PROTOCOL_REJECTED));
        }
        try {
            com.dylan.agent.api.contract.runtime.error.RuntimeErrorResponse error = objectMapper.readValue(
                    responseBytes,
                    com.dylan.agent.api.contract.runtime.error.RuntimeErrorResponse.class);
            if (error.getCode() == null || error.getMessage() == null || error.getMessage().isBlank()
                    || error.getDiagnosticId() == null || error.getDiagnosticId().isBlank()) {
                throw new IllegalArgumentException("invalid runtime error body");
            }
            return new ParsedRuntimeError(error,
                    notReportedAudit(operation, started, PlanningOperationTermination.PROTOCOL_REJECTED));
        } catch (Exception ex) {
            throw operationException(
                    operation,
                    RuntimeOperationFailure.PROTOCOL,
                    notReportedAudit(operation, started, PlanningOperationTermination.PROTOCOL_REJECTED),
                    "runtime-" + operation.name().toLowerCase() + "-error-body",
                    ex);
        }
    }

    private static RuntimeOperationFailure mapFailure(HttpStatusCode status, RuntimeErrorCode code) {
        if (status == HttpStatus.UNAUTHORIZED || status == HttpStatus.FORBIDDEN
                || code == RuntimeErrorCode.AUTHENTICATION_FAILED) {
            return RuntimeOperationFailure.AUTHENTICATION;
        }
        if (status == HttpStatus.GATEWAY_TIMEOUT || code == RuntimeErrorCode.DEADLINE_EXCEEDED) {
            return RuntimeOperationFailure.DEADLINE;
        }
        if (code == RuntimeErrorCode.PROVIDER_UNAVAILABLE) {
            return RuntimeOperationFailure.PROVIDER;
        }
        if (code == RuntimeErrorCode.OUTPUT_REPAIR_EXHAUSTED) {
            return RuntimeOperationFailure.REPAIR_EXHAUSTED;
        }
        if (code == RuntimeErrorCode.CONTRACT_INVALID || status == HttpStatus.BAD_REQUEST) {
            return RuntimeOperationFailure.PROTOCOL;
        }
        return RuntimeOperationFailure.INTERNAL;
    }

    private void validateOutcome(RuntimeOperationType operation, String expectedRequestId, Object outcome) {
        String actualRequestId;
        RuntimeOperationMetadata metadata;
        if (outcome instanceof RouteOutcome routeOutcome) {
            actualRequestId = routeOutcome.getRequestId();
            metadata = routeOutcome.getMetadata();
        } else if (outcome instanceof PlanOutcome planOutcome) {
            actualRequestId = planOutcome.getRequestId();
            metadata = planOutcome.getMetadata();
        } else {
            throw new IllegalArgumentException("unsupported outcome type");
        }
        if (!Objects.equals(expectedRequestId, actualRequestId)) {
            throw new IllegalArgumentException("requestId mismatch");
        }
        if (metadata == null || metadata.getOperation() != operation) {
            throw new IllegalArgumentException("runtime metadata operation mismatch");
        }
    }

    private static RuntimeOperationMetadata metadata(Object outcome) {
        if (outcome instanceof RouteOutcome routeOutcome) {
            return routeOutcome.getMetadata();
        }
        if (outcome instanceof PlanOutcome planOutcome) {
            return planOutcome.getMetadata();
        }
        return null;
    }

    private PlanningOperationAudit notReportedAudit(
            RuntimeOperationType operation,
            Instant started,
            PlanningOperationTermination termination) {
        return PlanningOperationAudit.notReported(operation, elapsedMillis(started), termination);
    }

    private long elapsedMillis(Instant started) {
        return Math.max(0L, Duration.between(started, Instant.now()).toMillis());
    }

    private static RuntimeOperationException operationException(
            RuntimeOperationType operation,
            RuntimeOperationFailure failure,
            PlanningOperationAudit audit,
            String diagnosticId,
            Throwable cause) {
        return new RuntimeOperationException(operation, failure, audit, safeDiagnosticId(diagnosticId), cause);
    }

    private static String safeDiagnosticId(String diagnosticId) {
        return diagnosticId == null || diagnosticId.isBlank()
                ? "runtime-" + UUID.randomUUID()
                : diagnosticId.trim();
    }

    private byte[] readLimited(InputStream input, int maxBytes) throws IOException {
        if (input == null) {
            return new byte[0];
        }
        try (input; ByteArrayOutputStream output = new ByteArrayOutputStream(Math.min(maxBytes, 8192))) {
            byte[] buffer = new byte[4096];
            int total = 0;
            int read;
            while ((read = input.read(buffer)) != -1) {
                total += read;
                if (total > maxBytes) {
                    throw new AgentRuntimeException("Runtime 响应超过大小上限。");
                }
                output.write(buffer, 0, read);
            }
            return output.toByteArray();
        }
    }

    private record ParsedRuntimeError(
            com.dylan.agent.api.contract.runtime.error.RuntimeErrorResponse error,
            PlanningOperationAudit audit) {
    }
}
