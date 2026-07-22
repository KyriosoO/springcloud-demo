package com.dylan.baseline.agent.security.authorization.internal;

import com.dylan.baseline.agent.security.authorization.AuthPermissionAuthorityPort;
import com.dylan.baseline.agent.security.authorization.ResolvedAuthPermission;
import com.dylan.baseline.agent.security.authorization.SubjectRef;
import com.dylan.common.security.ServiceTokenProvider;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.SocketTimeoutException;
import java.net.http.HttpTimeoutException;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Objects;
import java.util.UUID;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientException;

/** 通过服务令牌调用 Auth 内部权限接口；每次调用无重试、无正向缓存。 */
public final class HttpAuthPermissionAuthorityAdapter implements AuthPermissionAuthorityPort {

    private final AuthPermissionRestClientFactory restClientFactory;
    private final AuthPermissionClientProperties properties;
    private final ServiceTokenProvider serviceTokenProvider;
    private final ObjectMapper objectMapper;
    private final AuthPermissionAuthorityAdapter responseAdapter;
    private final Clock clock;

    HttpAuthPermissionAuthorityAdapter(
            AuthPermissionRestClientFactory restClientFactory,
            AuthPermissionClientProperties properties,
            ServiceTokenProvider serviceTokenProvider,
            ObjectMapper objectMapper,
            AuthPermissionAuthorityAdapter responseAdapter,
            Clock clock) {
        this.restClientFactory = Objects.requireNonNull(restClientFactory);
        this.properties = Objects.requireNonNull(properties);
        this.serviceTokenProvider = Objects.requireNonNull(serviceTokenProvider);
        this.objectMapper = Objects.requireNonNull(objectMapper);
        this.responseAdapter = Objects.requireNonNull(responseAdapter);
        this.clock = Objects.requireNonNull(clock);
    }

    @Override
    public ResolvedAuthPermission resolveCurrent(
            SubjectRef expectedSubject,
            String expectedTenantRef,
            Instant absoluteDeadline) {
        Instant requestedAt = clock.instant();
        if (expectedSubject == null || absoluteDeadline == null || !requestedAt.isBefore(absoluteDeadline)) {
            throw new AuthPermissionValidationException("SECURITY_AUTH_FACT_STALE");
        }
        Duration remaining = Duration.between(requestedAt, absoluteDeadline);
        Duration readTimeout = remaining.compareTo(properties.getReadTimeout()) < 0
                ? remaining : properties.getReadTimeout();
        AuthPermissionWireRequest request = new AuthPermissionWireRequest(
                "agent-permission-" + UUID.randomUUID(),
                expectedSubject,
                requestedAt,
                absoluteDeadline);
        WireResponse wire = execute(request, serviceToken(), readTimeout);
        if (wire.status() < 200 || wire.status() >= 300) {
            throw mapFailure(wire);
        }
        if (wire.contentType() == null || !MediaType.APPLICATION_JSON.isCompatibleWith(wire.contentType())) {
            throw new AuthPermissionValidationException("SECURITY_AUTH_FACT_UNAVAILABLE");
        }
        try {
            AuthPermissionWireResponse response = objectMapper.readValue(wire.body(), AuthPermissionWireResponse.class);
            return responseAdapter.map(response, expectedSubject, expectedTenantRef, absoluteDeadline);
        } catch (AuthPermissionValidationException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new AuthPermissionValidationException("SECURITY_AUTH_FACT_UNAVAILABLE", ex);
        }
    }

    private WireResponse execute(
            AuthPermissionWireRequest request,
            String token,
            Duration readTimeout) {
        try {
            return restClientFactory.create(readTimeout).post()
                    .uri(properties.getResolvePath())
                    .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(request)
                    .exchange((httpRequest, response) -> {
                        byte[] body = response.getBody().readNBytes(properties.getMaxResponseBytes() + 1);
                        if (body.length > properties.getMaxResponseBytes()) {
                            throw new ResponseLimitExceededException();
                        }
                        return new WireResponse(
                                response.getStatusCode().value(),
                                response.getHeaders().getContentType(),
                                body);
                    });
        } catch (ResourceAccessException ex) {
            String code = isTimeout(ex) && !clock.instant().isBefore(request.deadline())
                    ? "SECURITY_AUTH_FACT_STALE" : "SECURITY_AUTH_FACT_UNAVAILABLE";
            throw new AuthPermissionValidationException(code, ex);
        } catch (ResponseLimitExceededException | RestClientException | IllegalArgumentException ex) {
            throw new AuthPermissionValidationException("SECURITY_AUTH_FACT_UNAVAILABLE", ex);
        }
    }

    private String serviceToken() {
        try {
            String token = serviceTokenProvider.token();
            if (token == null || token.isBlank()) {
                throw new IllegalStateException("service token is blank");
            }
            return token;
        } catch (RuntimeException ex) {
            throw new AuthPermissionValidationException("SECURITY_AUTH_FACT_UNAVAILABLE", ex);
        }
    }

    private AuthPermissionValidationException mapFailure(WireResponse wire) {
        String code = switch (wire.status()) {
            case 504 -> "SECURITY_AUTH_FACT_STALE";
            default -> "SECURITY_AUTH_FACT_UNAVAILABLE";
        };
        // 远端错误正文不可信且不向上泄漏；当前内部异常只保留稳定安全码。
        return new AuthPermissionValidationException(code);
    }

    private static boolean isTimeout(Throwable failure) {
        Throwable current = failure;
        while (current != null) {
            if (current instanceof SocketTimeoutException || current instanceof HttpTimeoutException) {
                return true;
            }
            current = current.getCause();
        }
        return false;
    }

    private record WireResponse(int status, MediaType contentType, byte[] body) {
    }

    private static final class ResponseLimitExceededException extends RuntimeException {
    }
}
