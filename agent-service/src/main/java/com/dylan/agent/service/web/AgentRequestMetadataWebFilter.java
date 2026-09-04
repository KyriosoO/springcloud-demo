package com.dylan.agent.service.web;

import java.util.UUID;
import java.util.regex.Pattern;

import org.springframework.core.Ordered;
import org.springframework.http.HttpMethod;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;

import reactor.core.publisher.Mono;

@Component
public final class AgentRequestMetadataWebFilter implements WebFilter, Ordered {
    public static final String ATTRIBUTE = AgentRequestMetadata.class.getName();
    private static final String QUERY_PATH = "/api/v1/agent/queries";
    private static final String QUERY_RUN_PATH = "/api/v1/agent/query-runs";
    private static final Pattern SAFE_CORRELATION = Pattern.compile("[\\x20-\\x7e]{1,128}");

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        if (exchange.getRequest().getMethod() != HttpMethod.POST
                || (!QUERY_PATH.equals(exchange.getRequest().getPath().value())
                        && !QUERY_RUN_PATH.equals(exchange.getRequest().getPath().value()))) {
            return chain.filter(exchange);
        }
        if (exchange.getAttribute(ATTRIBUTE) != null) {
            return Mono.error(new IllegalStateException("agent.request-metadata-duplicate"));
        }
        String requested = exchange.getRequest().getHeaders().getFirst("X-Correlation-Id");
        String correlationId = requested != null && SAFE_CORRELATION.matcher(requested).matches()
                ? requested
                : UUID.randomUUID().toString();
        exchange.getAttributes().put(ATTRIBUTE,
                new AgentRequestMetadata(UUID.randomUUID().toString(), correlationId, System.nanoTime()));
        return chain.filter(exchange);
    }

    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE;
    }
}
