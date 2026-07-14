package com.dylan.agent.metadata.authorization.internal;

import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
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
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.function.Predicate;
import java.util.stream.Collectors;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

/**
 * auth-service 内部 Agent Permission API 的生产 Adapter。
 *
 * <p>该 Adapter 只消费 auth-service 返回的完整权限投影，不读取 JWT role 或
 * agent-service 本地角色配置来补权限。</p>
 */
public class AuthServiceUserPermissionAuthorityAdapter implements UserPermissionAuthorityPort {

    static final String AUTH_SUBJECT_TYPE = "USER";
    private static final int MAX_COLLECTION_ENTRIES = 1_024;
    private static final int MAX_IDENTIFIER_LENGTH = 256;
    private static final int MAX_ATTRIBUTE_VALUE_LENGTH = 1_024;

    private final AuthServicePermissionRestClientFactory restClientFactory;
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
        this(ignored -> Objects.requireNonNull(restClient, "restClient must not be null"),
                properties, objectMapper, serviceTokenProvider, clock);
    }

    AuthServiceUserPermissionAuthorityAdapter(
            AuthServicePermissionRestClientFactory restClientFactory,
            AgentProperties.AuthServiceProperties properties,
            ObjectMapper objectMapper,
            ServiceTokenProvider serviceTokenProvider,
            Clock clock) {
        this.restClientFactory = Objects.requireNonNull(restClientFactory, "restClientFactory must not be null");
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
        WireResponse wire;
        try {
            Duration remaining = Duration.between(clock.instant(), absoluteDeadline);
            if (remaining.isZero() || remaining.isNegative()) {
                throw authorityException(
                        UserPermissionAuthorityFailure.DEADLINE_EXCEEDED,
                        "auth-permission-deadline");
            }
            Duration requestTimeout = remaining.compareTo(properties.getReadTimeout()) < 0
                    ? remaining : properties.getReadTimeout();
            wire = restClientFactory.create(requestTimeout).post()
                    .uri(properties.getResolvePath())
                    .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                    .body(request)
                    .exchange((httpRequest, response) -> {
                        int maxBytes = properties.getMaxResponseBytes();
                        byte[] body = response.getBody().readNBytes(maxBytes + 1);
                        if (body.length > maxBytes) {
                            throw new ResponseLimitExceededException();
                        }
                        return new WireResponse(
                                response.getStatusCode().value(),
                                response.getHeaders().getContentType(),
                                body);
                    });
        } catch (ResourceAccessException ex) {
            throw authorityException(timeoutFailure(ex, absoluteDeadline), "auth-permission-io", ex);
        } catch (ResponseLimitExceededException ex) {
            throw authorityException(
                    UserPermissionAuthorityFailure.INVALID_RESPONSE,
                    "auth-permission-response-limit",
                    ex);
        } catch (RestClientException | IllegalArgumentException ex) {
            throw authorityException(UserPermissionAuthorityFailure.INVALID_RESPONSE, "auth-permission-response", ex);
        }
        if (!clock.instant().isBefore(absoluteDeadline)) {
            throw authorityException(UserPermissionAuthorityFailure.DEADLINE_EXCEEDED, "auth-permission-deadline");
        }
        if (wire == null) {
            throw authorityException(UserPermissionAuthorityFailure.INVALID_RESPONSE, "auth-permission-null-wire");
        }
        if (wire.status() < 200 || wire.status() >= 300) {
            throw mapHttpResponse(wire);
        }
        if (wire.contentType() == null
                || !MediaType.APPLICATION_JSON.isCompatibleWith(wire.contentType())) {
            throw authorityException(UserPermissionAuthorityFailure.INVALID_RESPONSE, "auth-permission-content-type");
        }
        try {
            return objectMapper.readValue(wire.body(), AuthPermissionResolveResponse.class);
        } catch (RuntimeException | java.io.IOException ex) {
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
        if (response.resolvedAt().isAfter(clock.instant())) {
            throw authorityException(
                    UserPermissionAuthorityFailure.INVALID_RESPONSE,
                    "auth-permission-resolved-at");
        }
        validateResponseShape(response);
        parseOperators(response.allowedOperators());
    }

    private void validateResponseShape(AuthPermissionResolveResponse response)
            throws UserPermissionAuthorityException {
        try {
            requireBoundedText(response.evidenceId(), "evidenceId", value -> true);
            requireBoundedText(response.version(), "version", value -> true);
            validateSet(response.allowedCapabilityIds(), "allowedCapabilityIds", this::isCapabilityId);
            validateSet(response.allowedDomains(), "allowedDomains", this::isDomainId);
            validateFieldMap(response.filterableFields(), response.allowedDomains(), "filterableFields");
            validateFieldMap(response.displayableFields(), response.allowedDomains(), "displayableFields");
            validateRuleMap(response.allowedOperators(), response.allowedDomains(), "allowedOperators", value -> {
                AgentOperator.valueOf(value);
                return true;
            });
            validateRuleMap(response.allowedFunctions(), response.allowedDomains(), "allowedFunctions",
                    value -> value.matches("[a-z][a-z0-9_]{0,63}"));
            validateSet(response.readableContextTypes(), "readableContextTypes", value -> {
                RuntimeContextType.valueOf(value);
                return true;
            });
            validateSet(response.writableContextTypes(), "writableContextTypes", value -> {
                RuntimeContextType.valueOf(value);
                return true;
            });
            validateAttributes(response.attributes());
        } catch (RuntimeException ex) {
            throw authorityException(
                    UserPermissionAuthorityFailure.INVALID_RESPONSE,
                    "auth-permission-invalid-shape",
                    ex);
        }
    }

    private void validateFieldMap(
            Map<String, Set<String>> values,
            Set<String> allowedDomains,
            String name) {
        requireCollectionSize(values.size(), name);
        values.forEach((domain, fields) -> {
            requireBoundedText(domain, name + " domain", this::isDomainId);
            if (!allowedDomains.contains(domain)) {
                throw new IllegalArgumentException(name + " contains a domain outside allowedDomains");
            }
            validateSet(fields, name + " fields", this::isFieldId);
        });
    }

    private void validateRuleMap(
            Map<String, Set<String>> values,
            Set<String> allowedDomains,
            String name,
            Predicate<String> valueValidator) {
        requireCollectionSize(values.size(), name);
        values.forEach((fieldKey, rules) -> {
            requireBoundedText(fieldKey, name + " field key", this::isFieldKey);
            String domain = fieldKey.substring(0, fieldKey.indexOf('.'));
            if (!allowedDomains.contains(domain)) {
                throw new IllegalArgumentException(name + " contains a domain outside allowedDomains");
            }
            validateSet(rules, name + " rules", valueValidator);
        });
    }

    private void validateAttributes(Map<String, String> attributes) {
        requireCollectionSize(attributes.size(), "attributes");
        attributes.forEach((key, value) -> {
            requireBoundedText(key, "attribute key", item -> item.matches("[A-Za-z][A-Za-z0-9_.-]{0,127}"));
            if (value == null || value.isBlank() || value.length() > MAX_ATTRIBUTE_VALUE_LENGTH) {
                throw new IllegalArgumentException("attribute value is invalid");
            }
        });
    }

    private void validateSet(Set<String> values, String name, Predicate<String> validator) {
        if (values == null) {
            throw new IllegalArgumentException(name + " must not be null");
        }
        requireCollectionSize(values.size(), name);
        values.forEach(value -> requireBoundedText(value, name + " value", validator));
    }

    private static void requireCollectionSize(int size, String name) {
        if (size > MAX_COLLECTION_ENTRIES) {
            throw new IllegalArgumentException(name + " exceeds entry limit");
        }
    }

    private void requireBoundedText(String value, String name, Predicate<String> validator) {
        if (value == null || value.isBlank() || value.length() > MAX_IDENTIFIER_LENGTH
                || !validator.test(value)) {
            throw new IllegalArgumentException(name + " is invalid");
        }
    }

    private boolean isCapabilityId(String value) {
        return value.matches("[a-z][a-z0-9]*(?:[._-][A-Za-z0-9]+)*");
    }

    private boolean isDomainId(String value) {
        return value.matches("[a-z][a-z0-9_]*");
    }

    private boolean isFieldId(String value) {
        return value.matches("[A-Za-z][A-Za-z0-9_]{0,127}");
    }

    private boolean isFieldKey(String value) {
        int separator = value.indexOf('.');
        return separator > 0
                && separator == value.lastIndexOf('.')
                && isDomainId(value.substring(0, separator))
                && isFieldId(value.substring(separator + 1));
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

    private UserPermissionAuthorityException mapHttpResponse(WireResponse response) {
        HttpStatus status = HttpStatus.resolve(response.status());
        if (status == HttpStatus.UNAUTHORIZED || status == HttpStatus.FORBIDDEN) {
            return authorityException(
                    UserPermissionAuthorityFailure.UNAVAILABLE,
                    "auth-permission-http-" + response.status());
        }
        String diagnosticId = diagnosticId(response.body(), response.status());
        if (status == HttpStatus.NOT_FOUND) {
            return authorityException(UserPermissionAuthorityFailure.SUBJECT_NOT_FOUND, diagnosticId);
        }
        if (status == HttpStatus.GATEWAY_TIMEOUT) {
            return authorityException(UserPermissionAuthorityFailure.DEADLINE_EXCEEDED, diagnosticId);
        }
        if (status == HttpStatus.BAD_REQUEST) {
            return authorityException(UserPermissionAuthorityFailure.INVALID_RESPONSE, diagnosticId);
        }
        return authorityException(UserPermissionAuthorityFailure.UNAVAILABLE, diagnosticId);
    }

    private String diagnosticId(byte[] body, int status) {
        try {
            AuthPermissionErrorResponse error = objectMapper.readValue(
                    body,
                    AuthPermissionErrorResponse.class);
            if (error.diagnosticId() != null && !error.diagnosticId().isBlank()) {
                return error.diagnosticId();
            }
        } catch (Exception ignored) {
            return "auth-permission-http-" + status;
        }
        return "auth-permission-http-" + status;
    }

    private UserPermissionAuthorityFailure timeoutFailure(Throwable ex, Instant absoluteDeadline) {
        return isTimeout(ex) && !clock.instant().isBefore(absoluteDeadline)
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

    private record WireResponse(int status, MediaType contentType, byte[] body) {
    }

    private static final class ResponseLimitExceededException extends RuntimeException {
    }
}
