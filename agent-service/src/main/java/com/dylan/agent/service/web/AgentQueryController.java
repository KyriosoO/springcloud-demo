package com.dylan.agent.service.web;

import com.dylan.agent.service.application.AgentPublicException;
import com.dylan.agent.service.application.AgentQueryApplicationService;
import com.dylan.agent.service.application.AgentQueryCommand;
import com.dylan.agent.service.contract.AgentQueryRequest;
import com.dylan.agent.service.contract.AgentQueryResponse;
import com.dylan.agent.service.contract.CapabilityStatus;

import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ServerWebExchange;

import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api/v1/agent")
public final class AgentQueryController {
    private final AgentQueryApplicationService service;

    public AgentQueryController(AgentQueryApplicationService service) {
        this.service = service;
    }

    @PostMapping(path = "/queries", consumes = "application/json", produces = "application/json")
    public Mono<ResponseEntity<AgentQueryResponse>> query(
            @Valid @RequestBody AgentQueryRequest request,
            JwtAuthenticationToken authentication,
            ServerWebExchange exchange) {
        AgentRequestMetadata metadata = exchange.getAttribute(AgentRequestMetadataWebFilter.ATTRIBUTE);
        if (metadata == null) {
            return Mono.error(AgentPublicException.internalFailure());
        }
        return service.query(new AgentQueryCommand(request.question()), authentication.getToken(), metadata)
                .map(response -> ResponseEntity.status(httpStatus(response)).body(response));
    }

    static HttpStatus httpStatus(AgentQueryResponse response) {
        return switch (response.status()) {
            case SUCCESS, NO_RESULT -> HttpStatus.OK;
            case UNSUPPORTED -> HttpStatus.UNPROCESSABLE_ENTITY;
            case INVALID_ARGUMENT -> HttpStatus.BAD_REQUEST;
            case UNAUTHENTICATED -> HttpStatus.UNAUTHORIZED;
            case FORBIDDEN, MODEL_EGRESS_DENIED -> HttpStatus.FORBIDDEN;
            case TIMEOUT -> HttpStatus.GATEWAY_TIMEOUT;
            case DOWNSTREAM_FAILURE -> "core.ingress_capacity_exceeded".equals(
                    response.error() == null ? null : response.error().code())
                            ? HttpStatus.TOO_MANY_REQUESTS
                            : HttpStatus.BAD_GATEWAY;
            case INTERNAL_FAILURE -> HttpStatus.INTERNAL_SERVER_ERROR;
        };
    }
}
