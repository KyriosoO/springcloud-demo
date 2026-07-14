package com.dylan.agent.metadata.authorization.internal;

import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.metadata.authorization.model.UserPermission;
import com.dylan.agent.metadata.authorization.port.UserPermissionAuthorityException;
import com.dylan.agent.metadata.authorization.port.UserPermissionAuthorityFailure;
import com.dylan.agent.metadata.authorization.port.UserPermissionAuthorityPort;
import com.dylan.common.security.ServiceTokenProvider;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.net.SocketTimeoutException;
import java.net.http.HttpTimeoutException;
import java.time.Clock;
import java.time.Instant;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

/**
 * auth-service 内部 Agent Permission API 的生产 Adapter。
 *
 * <p>该 Adapter 只消费 auth-service 返回的完整权限投影，不读取 JWT role 或
 * agent-service 本地角色配置来补权限。</p>
 */
public class AuthServiceUserPermissionAuthorityAdapter implements UserPermissionAuthorityPort {

    static final String AUTH_SUBJECT_TYPE = "USER";

    private final RestClient restClient;
    private final AgentProperties.AuthServiceProperties properties;
    private final ObjectMapper objectMapper;
    private final ServiceTokenProvider serviceTokenProvider;
    private final Clock clock;

    AuthServiceUserPermissionAuthorityAdapter(
            RestClient restClient,
            AgentProperties.AuthServiceProperties properties,
            ObjectMapper objectMapper,
            ServiceTokenProvider serviceTokenProvider,
            Clock clock) {
        this.restClient = Objects.requireNonNull(restClient, "restClient must not be null");
        this.properties = Objects.requireNonNull(properties, "properties must not be null");
        this.objectMapper = Objects.requireNonNull(objectMapper, "objectMapper must not be null");
        this.serviceTokenProvider = Objects.requireNonNull(serviceTokenProvider, "serviceTokenProvider must not be null");
        this.clock = Objects.requireNonNull(clock, "clock must not be null");
    }

    @Override
    public UserPermission resolveCurrent(
            ExecutionSubjectRef subject,
            Instant absoluteDeadline) throws UserPermissionAuthorityException {
        Objects.requireNonNull(subject, "subject must not be null");
        Objects.requireNonNull(absoluteDeadline, "absoluteDeadline must not be null");
        if (!clock.instant().isBefore(absoluteDeadline)) {
            throw authorityException(UserPermissionAuthorityFailure.DEADLINE_EXCEEDED, "auth-permission-deadline");
        }
        if (!"user".equalsIgnoreCase(subject.type())) {
            throw authorityException(UserPermissionAuthorityFailure.INVALID_RESPONSE, "auth-permission-subject-type");
        }
        String token = serviceToken();
        AuthPermissionResolveRequest request = request(subject, absoluteDeadline);
        AuthPermissionResolveResponse response = execute(request, token, absoluteDeadline);
        validateResponse(subject, response);
        try {
            return toUserPermission(subject, response);
        } catch (UserPermissionAuthorityException ex) {
            throw ex;
        } catch (RuntimeException ex) {
            throw authorityException(UserPermissionAuthorityFailure.INVALID_RESPONSE,
                    "auth-permission-invalid-projection", ex);
        }
    }

    private AuthPermissionResolveResponse execute(
            AuthPermissionResolveRequest request,
            String token,
            Instant absoluteDeadline) throws UserPermissionAuthorityException {
        try {
            ResponseEntity<AuthPermissionResolveResponse> entity = restClient.post()
                    .uri(properties.getResolvePath())
                    .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                    .body(request)
                    .retrieve()
                    .toEntity(AuthPermissionResolveResponse.class);
            if (!clock.instant().isBefore(absoluteDeadline)) {
                throw authorityException(UserPermissionAuthorityFailure.DEADLINE_EXCEEDED, "auth-permission-deadline");
            }
            return entity.getBody();
        } catch (RestClientResponseException ex) {
            throw mapHttpException(ex);
        } catch (ResourceAccessException ex) {
            throw authorityException(timeoutFailure(ex), "auth-permission-io", ex);
        } catch (RestClientException | IllegalArgumentException ex) {
            throw authorityException(UserPermissionAuthorityFailure.INVALID_RESPONSE, "auth-permission-response", ex);
        }
    }

    private UserPermission toUserPermission(
            ExecutionSubjectRef originalSubject,
            AuthPermissionResolveResponse response) throws UserPermissionAuthorityException {
        return new UserPermission(
                originalSubject,
                response.evidenceId(),
                response.version(),
                response.allowedCapabilityIds(),
                response.allowedDomains(),
                response.filterableFields(),
                response.displayableFields(),
                parseOperators(response.allowedOperators()),
                response.allowedFunctions(),
                response.readableContextTypes(),
                response.writableContextTypes(),
                response.attributes(),
                response.resolvedAt());
    }

    private void validateResponse(
            ExecutionSubjectRef originalSubject,
            AuthPermissionResolveResponse response) throws UserPermissionAuthorityException {
        if (response == null
                || response.subject() == null
                || response.subject().type() == null
                || response.subject().id() == null
                || response.evidenceId() == null
                || response.evidenceId().isBlank()
                || response.version() == null
                || response.version().isBlank()
                || response.allowedCapabilityIds() == null
                || response.allowedDomains() == null
                || response.filterableFields() == null
                || response.displayableFields() == null
                || response.allowedOperators() == null
                || response.allowedFunctions() == null
                || response.readableContextTypes() == null
                || response.writableContextTypes() == null
                || response.attributes() == null
                || response.resolvedAt() == null) {
            throw authorityException(UserPermissionAuthorityFailure.INVALID_RESPONSE, "auth-permission-invalid-body");
        }
        if (!AUTH_SUBJECT_TYPE.equals(response.subject().type())
                || !originalSubject.id().equals(response.subject().id())) {
            throw authorityException(UserPermissionAuthorityFailure.INVALID_RESPONSE, "auth-permission-subject-mismatch");
        }
        parseOperators(response.allowedOperators());
    }

    private Map<String, Set<AgentOperator>> parseOperators(
            Map<String, Set<String>> operators) throws UserPermissionAuthorityException {
        try {
            return operators.entrySet().stream()
                    .collect(Collectors.toUnmodifiableMap(
                            Map.Entry::getKey,
                            entry -> entry.getValue().stream()
                                    .map(AgentOperator::valueOf)
                                    .collect(Collectors.toUnmodifiableSet())));
        } catch (RuntimeException ex) {
            throw authorityException(UserPermissionAuthorityFailure.INVALID_RESPONSE, "auth-permission-operator", ex);
        }
    }

    private AuthPermissionResolveRequest request(ExecutionSubjectRef subject, Instant absoluteDeadline) {
        Instant now = clock.instant();
        return new AuthPermissionResolveRequest(
                "agent-permission-" + UUID.randomUUID(),
                new SubjectRefDto(AUTH_SUBJECT_TYPE, subject.id()),
                now,
                absoluteDeadline);
    }

    private String serviceToken() throws UserPermissionAuthorityException {
        try {
            String token = serviceTokenProvider.token();
            if (token == null || token.isBlank()) {
                throw authorityException(UserPermissionAuthorityFailure.UNAVAILABLE, "auth-permission-token");
            }
            return token;
        } catch (UserPermissionAuthorityException ex) {
            throw ex;
        } catch (RuntimeException ex) {
            throw authorityException(UserPermissionAuthorityFailure.UNAVAILABLE, "auth-permission-token", ex);
        }
    }

    private UserPermissionAuthorityException mapHttpException(RestClientResponseException ex) {
        HttpStatus status = HttpStatus.resolve(ex.getStatusCode().value());
        String diagnosticId = diagnosticId(ex);
        if (status == HttpStatus.NOT_FOUND) {
            return authorityException(UserPermissionAuthorityFailure.SUBJECT_NOT_FOUND, diagnosticId, ex);
        }
        if (status == HttpStatus.GATEWAY_TIMEOUT) {
            return authorityException(UserPermissionAuthorityFailure.DEADLINE_EXCEEDED, diagnosticId, ex);
        }
        if (status == HttpStatus.BAD_REQUEST) {
            return authorityException(UserPermissionAuthorityFailure.INVALID_RESPONSE, diagnosticId, ex);
        }
        return authorityException(UserPermissionAuthorityFailure.UNAVAILABLE, diagnosticId, ex);
    }

    private String diagnosticId(RestClientResponseException ex) {
        try {
            AuthPermissionErrorResponse error = objectMapper.readValue(
                    ex.getResponseBodyAsByteArray(),
                    AuthPermissionErrorResponse.class);
            if (error.diagnosticId() != null && !error.diagnosticId().isBlank()) {
                return error.diagnosticId();
            }
        } catch (Exception ignored) {
            return "auth-permission-http-" + ex.getStatusCode().value();
        }
        return "auth-permission-http-" + ex.getStatusCode().value();
    }

    private static UserPermissionAuthorityFailure timeoutFailure(Throwable ex) {
        return isTimeout(ex)
                ? UserPermissionAuthorityFailure.DEADLINE_EXCEEDED
                : UserPermissionAuthorityFailure.UNAVAILABLE;
    }

    private static boolean isTimeout(Throwable ex) {
        Throwable current = ex;
        while (current != null) {
            if (current instanceof SocketTimeoutException || current instanceof HttpTimeoutException) {
                return true;
            }
            current = current.getCause();
        }
        return false;
    }

    private static UserPermissionAuthorityException authorityException(
            UserPermissionAuthorityFailure failure,
            String diagnosticId) {
        return authorityException(failure, diagnosticId, null);
    }

    private static UserPermissionAuthorityException authorityException(
            UserPermissionAuthorityFailure failure,
            String diagnosticId,
            Throwable cause) {
        return new UserPermissionAuthorityException(failure, safeDiagnosticId(diagnosticId), cause);
    }

    private static String safeDiagnosticId(String diagnosticId) {
        return diagnosticId == null || diagnosticId.isBlank()
                ? "auth-permission-" + UUID.randomUUID()
                : diagnosticId.trim();
    }

    public record SubjectRefDto(String type, String id) {
    }

    public record AuthPermissionResolveRequest(
            String requestId,
            SubjectRefDto subject,
            Instant requestedAt,
            Instant deadline) {
    }

    public record AuthPermissionResolveResponse(
            SubjectRefDto subject,
            String evidenceId,
            String version,
            Set<String> allowedCapabilityIds,
            Set<String> allowedDomains,
            Map<String, Set<String>> filterableFields,
            Map<String, Set<String>> displayableFields,
            Map<String, Set<String>> allowedOperators,
            Map<String, Set<String>> allowedFunctions,
            Set<String> readableContextTypes,
            Set<String> writableContextTypes,
            Map<String, String> attributes,
            Instant resolvedAt) {
    }

    public record AuthPermissionErrorResponse(
            String requestId,
            String code,
            String message,
            String diagnosticId) {
    }
}
