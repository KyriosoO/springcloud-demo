package com.dylan.agent.service.runtime;

import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeoutException;
import java.util.regex.Pattern;

import com.dylan.agent.service.config.AgentRuntimeProperties;
import com.dylan.agent.service.contract.CapabilityStatus;
import com.dylan.agent.service.contract.RuntimeInvokeRequest;
import com.dylan.agent.service.contract.RuntimeInvokeResponse;
import com.dylan.agent.service.contract.RuntimeInspectResponse;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;

import io.netty.channel.ChannelOption;
import org.springframework.core.codec.DecodingException;
import org.springframework.core.io.buffer.DataBufferLimitException;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.http.codec.json.Jackson2JsonDecoder;
import org.springframework.http.codec.json.Jackson2JsonEncoder;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientRequestException;

import reactor.core.publisher.Mono;
import reactor.netty.http.client.HttpClient;

@Component
public final class WebClientAgentRuntimeClient implements AgentRuntimeClient, AgentRuntimeInspectionClient {
    private static final String INVOKE_PATH = "/internal/v1/agent-runs:invoke";
    private static final String INSPECT_PATH = "/internal/v1/agent-runs:inspect";
    private static final Pattern CAPABILITY_ID = Pattern.compile("[a-z][a-z0-9_-]*(\\.[a-z][a-z0-9_-]*)+");

    private final int contractVersion;
    private final ObjectMapper strictMapper;
    private final WebClient webClient;

    public WebClientAgentRuntimeClient(AgentRuntimeProperties properties, ObjectMapper objectMapper) {
        this.contractVersion = properties.contractVersion();
        this.strictMapper = objectMapper.copy().enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);
        this.webClient = createWebClient(properties, strictMapper);
    }

    static WebClient createWebClient(AgentRuntimeProperties properties, ObjectMapper strictMapper) {
        ExchangeStrategies strategies = ExchangeStrategies.builder().codecs(codecs -> {
            codecs.defaultCodecs().maxInMemorySize(properties.maxResponseBytes());
            codecs.defaultCodecs().jackson2JsonDecoder(new Jackson2JsonDecoder(strictMapper, MediaType.APPLICATION_JSON));
            codecs.defaultCodecs().jackson2JsonEncoder(new Jackson2JsonEncoder(strictMapper, MediaType.APPLICATION_JSON));
        }).build();
        HttpClient httpClient = HttpClient.create()
                .followRedirect(false)
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, Math.toIntExact(properties.connectTimeout().toMillis()));
        return WebClient.builder()
                .baseUrl(properties.baseUrl().toString())
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .exchangeStrategies(strategies)
                .build();
    }

    @Override
    public Mono<RuntimeInvokeResponse> invoke(RuntimeInvokeRequest request, String rawUserToken) {
        return webClient.post()
                .uri(INVOKE_PATH)
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.APPLICATION_JSON)
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + rawUserToken)
                .header("X-Agent-Contract-Version", Integer.toString(contractVersion))
                .bodyValue(request)
                .exchangeToMono(response -> decodeResponse(response, request.requestId()))
                .onErrorMap(error -> !(error instanceof RuntimeClientException), this::mapTransportFailure);
    }

    @Override
    public Mono<RuntimeInspectResponse> inspect(RuntimeInvokeRequest request, String rawUserToken) {
        return webClient.post()
                .uri(INSPECT_PATH)
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.APPLICATION_JSON)
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + rawUserToken)
                .header("X-Agent-Contract-Version", Integer.toString(contractVersion))
                .bodyValue(request)
                .exchangeToMono(response -> decodeInspectResponse(response, request.requestId()))
                .onErrorMap(error -> !(error instanceof RuntimeClientException), this::mapTransportFailure);
    }

    Mono<RuntimeInvokeResponse> decodeResponse(ClientResponse response, String expectedRequestId) {
        int status = response.statusCode().value();
        if (status != 200) {
            RuntimeClientException failure = mapStatus(response.statusCode());
            return response.releaseBody().then(Mono.error(failure));
        }
        MediaType contentType = response.headers().contentType().orElse(null);
        if (contentType == null || !MediaType.APPLICATION_JSON.isCompatibleWith(contentType)) {
            return response.releaseBody().then(Mono.error(RuntimeClientException.invalidResponse()));
        }
        return response.bodyToMono(byte[].class)
                .switchIfEmpty(Mono.error(RuntimeClientException.invalidResponse()))
                .map(body -> decodeBody(body, expectedRequestId));
    }

    Mono<RuntimeInspectResponse> decodeInspectResponse(ClientResponse response, String expectedRequestId) {
        int status = response.statusCode().value();
        if (status != 200) {
            RuntimeClientException failure = mapStatus(response.statusCode());
            return response.releaseBody().then(Mono.error(failure));
        }
        MediaType contentType = response.headers().contentType().orElse(null);
        if (contentType == null || !MediaType.APPLICATION_JSON.isCompatibleWith(contentType)) {
            return response.releaseBody().then(Mono.error(RuntimeClientException.invalidResponse()));
        }
        return response.bodyToMono(byte[].class)
                .switchIfEmpty(Mono.error(RuntimeClientException.invalidResponse()))
                .map(body -> decodeInspectBody(body, expectedRequestId));
    }

    private RuntimeInvokeResponse decodeBody(byte[] body, String expectedRequestId) {
        try {
            return validateResponse(strictMapper.readValue(body, RuntimeInvokeResponse.class), expectedRequestId);
        } catch (RuntimeClientException failure) {
            throw failure;
        } catch (Exception failure) {
            throw RuntimeClientException.invalidResponse();
        }
    }

    private RuntimeInspectResponse decodeInspectBody(byte[] body, String expectedRequestId) {
        try {
            return validateInspectResponse(strictMapper.readValue(body, RuntimeInspectResponse.class), expectedRequestId);
        } catch (RuntimeClientException failure) {
            throw failure;
        } catch (Exception failure) {
            throw RuntimeClientException.invalidResponse();
        }
    }

    private RuntimeInvokeResponse validateResponse(RuntimeInvokeResponse response, String expectedRequestId) {
        if (response.contractVersion() != contractVersion || !expectedRequestId.equals(response.requestId())
                || response.status() == null) {
            throw RuntimeClientException.invalidResponse();
        }
        if (response.capabilityId() != null && (response.capabilityId().length() > 80
                || !CAPABILITY_ID.matcher(response.capabilityId()).matches())) {
            throw RuntimeClientException.invalidResponse();
        }
        boolean successLike = response.status() == CapabilityStatus.SUCCESS
                || response.status() == CapabilityStatus.NO_RESULT;
        if ((successLike && response.failure() != null)
                || (!successLike && (response.failure() == null || response.userResult() != null))) {
            throw RuntimeClientException.invalidResponse();
        }
        if (response.userResult() != null) {
            validateJsonValue(response.userResult(), 1);
        }
        return response;
    }

    private RuntimeInspectResponse validateInspectResponse(
            RuntimeInspectResponse response,
            String expectedRequestId) {
        if (response.contractVersion() != contractVersion || !expectedRequestId.equals(response.requestId())
                || response.status() == null) {
            throw RuntimeClientException.invalidResponse();
        }
        if (response.capabilityId() != null && (response.capabilityId().length() > 80
                || !CAPABILITY_ID.matcher(response.capabilityId()).matches())) {
            throw RuntimeClientException.invalidResponse();
        }
        boolean successLike = response.status() == CapabilityStatus.SUCCESS
                || response.status() == CapabilityStatus.NO_RESULT;
        if ((successLike && response.failure() != null)
                || (!successLike && (response.failure() == null || response.userResult() != null))) {
            throw RuntimeClientException.invalidResponse();
        }
        if (response.userResult() != null) {
            validateJsonValue(response.userResult(), 1);
        }
        response.modelCalls().forEach(call -> {
            validateObservationJson(call.request(), 1);
        });
        response.plans().forEach(plan -> validateObservationJson(plan.plan(), 1));
        response.downstreamCalls().forEach(call -> validateObservationJson(call.request(), 1));
        return response;
    }

    private void validateObservationJson(Object value, int depth) {
        if (depth > 16) {
            throw RuntimeClientException.invalidResponse();
        }
        if (value == null || value instanceof Boolean || value instanceof Integer || value instanceof Long
                || value instanceof java.math.BigInteger || value instanceof java.math.BigDecimal) {
            return;
        }
        if (value instanceof String text) {
            if (text.length() > 16_384) {
                throw RuntimeClientException.invalidResponse();
            }
            return;
        }
        if (value instanceof Double number) {
            if (!Double.isFinite(number)) {
                throw RuntimeClientException.invalidResponse();
            }
            return;
        }
        if (value instanceof Float number) {
            if (!Float.isFinite(number)) {
                throw RuntimeClientException.invalidResponse();
            }
            return;
        }
        if (value instanceof Map<?, ?> map) {
            if (map.size() > 1024 || map.keySet().stream().anyMatch(key -> !(key instanceof String))) {
                throw RuntimeClientException.invalidResponse();
            }
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                String key = ((String) entry.getKey()).toLowerCase(java.util.Locale.ROOT);
                if (List.of("authorization", "jwt", "token", "api_key", "apikey", "headers",
                        "rawresponse", "content", "documents").contains(key)) {
                    throw RuntimeClientException.invalidResponse();
                }
                validateObservationJson(entry.getValue(), depth + 1);
            }
            return;
        }
        if (value instanceof List<?> list) {
            if (list.size() > 1024) {
                throw RuntimeClientException.invalidResponse();
            }
            list.forEach(item -> validateObservationJson(item, depth + 1));
            return;
        }
        throw RuntimeClientException.invalidResponse();
    }

    private void validateJsonValue(Object value, int depth) {
        if (depth > 16) {
            throw RuntimeClientException.invalidResponse();
        }
        if (value == null || value instanceof String || value instanceof Boolean
                || value instanceof Integer || value instanceof Long
                || value instanceof java.math.BigInteger || value instanceof java.math.BigDecimal) {
            return;
        }
        if (value instanceof Double number) {
            if (!Double.isFinite(number)) {
                throw RuntimeClientException.invalidResponse();
            }
            return;
        }
        if (value instanceof Float number) {
            if (!Float.isFinite(number)) {
                throw RuntimeClientException.invalidResponse();
            }
            return;
        }
        if (value instanceof Map<?, ?> map) {
            if (map.size() > 2048 || map.keySet().stream().anyMatch(key -> !(key instanceof String))) {
                throw RuntimeClientException.invalidResponse();
            }
            map.values().forEach(item -> validateJsonValue(item, depth + 1));
            return;
        }
        if (value instanceof List<?> list) {
            if (list.size() > 2048) {
                throw RuntimeClientException.invalidResponse();
            }
            list.forEach(item -> validateJsonValue(item, depth + 1));
            return;
        }
        throw RuntimeClientException.invalidResponse();
    }

    private RuntimeClientException mapStatus(HttpStatusCode status) {
        if (status.is5xxServerError() && status.value() != 503) {
            return RuntimeClientException.failure();
        }
        return switch (status.value()) {
            case 401 -> RuntimeClientException.unauthenticated();
            case 429 -> RuntimeClientException.capacity();
            case 503 -> RuntimeClientException.unavailable();
            default -> RuntimeClientException.protocolError();
        };
    }

    private Throwable mapTransportFailure(Throwable error) {
        if (error instanceof TimeoutException) {
            return RuntimeClientException.timeout();
        }
        if (error instanceof DataBufferLimitException || error instanceof DecodingException) {
            return RuntimeClientException.invalidResponse();
        }
        if (error instanceof WebClientRequestException requestException) {
            return requestException.getCause() instanceof java.net.ConnectException
                    ? RuntimeClientException.unavailable()
                    : RuntimeClientException.connectionLost();
        }
        return RuntimeClientException.failure();
    }
}
