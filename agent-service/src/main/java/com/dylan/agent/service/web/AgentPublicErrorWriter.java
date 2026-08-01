package com.dylan.agent.service.web;

import com.dylan.agent.service.contract.AgentQueryResponse;
import com.dylan.agent.service.contract.CapabilityStatus;
import com.dylan.agent.service.contract.FailureResponse;
import com.dylan.agent.service.contract.FailureSource;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;

import reactor.core.publisher.Mono;

@Component
public final class AgentPublicErrorWriter {
    private final ObjectMapper objectMapper;

    public AgentPublicErrorWriter(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public Mono<Void> write(
            ServerWebExchange exchange,
            HttpStatusCode httpStatus,
            CapabilityStatus status,
            String code,
            FailureSource source) {
        if (exchange.getResponse().isCommitted()) {
            return Mono.empty();
        }
        AgentRequestMetadata metadata = exchange.getAttribute(AgentRequestMetadataWebFilter.ATTRIBUTE);
        if (metadata == null) {
            return Mono.error(new IllegalStateException("agent.request-metadata-missing"));
        }
        AgentQueryResponse response;
        try {
            response = new AgentQueryResponse(
                    metadata.requestId(), metadata.correlationId(), status, null, fixedAnswer(status), null,
                    new FailureResponse(code, source));
        } catch (IllegalArgumentException invalidMapping) {
            response = new AgentQueryResponse(
                    metadata.requestId(), metadata.correlationId(), CapabilityStatus.INTERNAL_FAILURE,
                    null, "查询处理失败。", null,
                    new FailureResponse("core.public_error_mapping_invalid", FailureSource.CORE));
            httpStatus = org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR;
        }
        byte[] body;
        try {
            body = objectMapper.writeValueAsBytes(response);
        } catch (JsonProcessingException failure) {
            return Mono.error(new IllegalStateException("agent.public-error-serialization", failure));
        }
        exchange.getResponse().setStatusCode(httpStatus);
        exchange.getResponse().getHeaders().setContentType(MediaType.APPLICATION_JSON);
        exchange.getResponse().getHeaders().setContentLength(body.length);
        DataBuffer buffer = exchange.getResponse().bufferFactory().wrap(body);
        return exchange.getResponse().writeWith(Mono.just(buffer));
    }

    private String fixedAnswer(CapabilityStatus status) {
        return switch (status) {
            case UNAUTHENTICATED -> "用户身份无效。";
            case FORBIDDEN, MODEL_EGRESS_DENIED -> "没有权限执行该查询。";
            case INVALID_ARGUMENT -> "查询参数无效。";
            case TIMEOUT -> "查询超时。";
            case DOWNSTREAM_FAILURE -> "下游查询暂时不可用。";
            default -> "查询处理失败。";
        };
    }
}
