package com.dylan.agent.service.web;

import com.dylan.agent.service.application.AgentPublicException;
import com.dylan.agent.service.application.AgentQueryCommand;
import com.dylan.agent.service.application.AgentRunApplicationService;
import com.dylan.agent.service.contract.AgentQueryRequest;
import com.dylan.agent.service.contract.AgentRunResponse;
import com.dylan.agent.service.config.AgentInspectionProperties;

import jakarta.validation.Valid;
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
public final class AgentRunController {
    private final AgentInspectionProperties properties;
    private final AgentRunApplicationService service;

    public AgentRunController(AgentRunApplicationService service, AgentInspectionProperties properties) {
        this.service = service;
        this.properties = properties;
    }

    @PostMapping(path = "/query-runs", consumes = "application/json", produces = "application/json")
    public Mono<ResponseEntity<AgentRunResponse>> inspect(
            @Valid @RequestBody AgentQueryRequest request,
            JwtAuthenticationToken authentication,
            ServerWebExchange exchange) {
        if (!properties.enabled()) {
            return Mono.error(AgentPublicException.inspectionDisabled());
        }
        AgentRequestMetadata metadata = exchange.getAttribute(AgentRequestMetadataWebFilter.ATTRIBUTE);
        if (metadata == null) {
            return Mono.error(AgentPublicException.internalFailure());
        }
        return service.inspect(new AgentQueryCommand(request.question()), authentication.getToken(), metadata)
                .map(response -> ResponseEntity.status(AgentQueryController.httpStatus(response.status(), response.error()))
                        .body(response));
    }
}
