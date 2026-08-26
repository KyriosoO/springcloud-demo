package com.dylan.agent.service.web;

import com.dylan.agent.service.application.AgentPublicException;
import com.dylan.agent.service.contract.CapabilityStatus;
import com.dylan.agent.service.contract.FailureSource;
import com.fasterxml.jackson.core.JsonProcessingException;

import org.springframework.boot.web.reactive.error.ErrorWebExceptionHandler;
import org.springframework.core.Ordered;
import org.springframework.core.codec.DecodingException;
import org.springframework.core.io.buffer.DataBufferLimitException;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.ServerWebInputException;
import org.springframework.web.server.UnsupportedMediaTypeStatusException;

import reactor.core.publisher.Mono;

@Component
public final class AgentWebExceptionHandler implements ErrorWebExceptionHandler, Ordered {
    private final AgentPublicErrorWriter writer;

    public AgentWebExceptionHandler(AgentPublicErrorWriter writer) {
        this.writer = writer;
    }

    @Override
    public Mono<Void> handle(ServerWebExchange exchange, Throwable error) {
        if (!"/api/v1/agent/queries".equals(exchange.getRequest().getPath().value())) {
            return Mono.error(error);
        }
        if (error instanceof AgentPublicException publicError) {
            return writer.write(exchange, publicError.httpStatus(), publicError.status(),
                    publicError.code(), publicError.source());
        }
        if (hasCause(error, AuthenticationException.class) || hasCause(error, JwtException.class)) {
            return writer.write(exchange, HttpStatus.UNAUTHORIZED, CapabilityStatus.UNAUTHENTICATED,
                    "core.user_identity_required", FailureSource.CORE);
        }
        if (hasCause(error, DataBufferLimitException.class)) {
            return writer.write(exchange, HttpStatus.PAYLOAD_TOO_LARGE, CapabilityStatus.INVALID_ARGUMENT,
                    "core.request_body_too_large", FailureSource.CORE);
        }
        if (error instanceof UnsupportedMediaTypeStatusException) {
            return writer.write(exchange, HttpStatus.UNSUPPORTED_MEDIA_TYPE, CapabilityStatus.INVALID_ARGUMENT,
                    "core.unsupported_media_type", FailureSource.CORE);
        }
        if (hasCause(error, ServerWebInputException.class)
                || hasCause(error, DecodingException.class)
                || hasCause(error, JsonProcessingException.class)) {
            return writer.write(exchange, HttpStatus.BAD_REQUEST, CapabilityStatus.INVALID_ARGUMENT,
                    "core.invalid_request", FailureSource.CORE);
        }
        return writer.write(exchange, HttpStatus.INTERNAL_SERVER_ERROR, CapabilityStatus.INTERNAL_FAILURE,
                "core.internal_failure", FailureSource.CORE);
    }

    private boolean hasCause(Throwable error, Class<? extends Throwable> type) {
        Throwable current = error;
        while (current != null) {
            if (type.isInstance(current)) {
                return true;
            }
            current = current.getCause();
        }
        return false;
    }

    @Override
    public int getOrder() {
        return -2;
    }
}
