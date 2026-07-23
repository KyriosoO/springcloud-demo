package com.dylan.springgateway.config;

import java.time.Duration;

import org.springframework.cloud.gateway.filter.GatewayFilter;
import org.springframework.cloud.gateway.filter.factory.RetryGatewayFilterFactory;
import org.springframework.cloud.gateway.route.RouteLocator;
import org.springframework.cloud.gateway.route.builder.RouteLocatorBuilder;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;

@Configuration
@EnableConfigurationProperties(AgentGatewayProperties.class)
public class GatewayRouter {
	RouteLocator customRouteLocator(RouteLocatorBuilder builder, RetryGatewayFilterFactory retryFactory) {
		return customRouteLocator(builder, retryFactory, new AgentGatewayProperties(false, null));
	}

	@Bean
	RouteLocator customRouteLocator(RouteLocatorBuilder builder, RetryGatewayFilterFactory retryFactory,
			AgentGatewayProperties agentGatewayProperties) {
		GatewayFilter retry = retryFactory.apply(c -> {
			c.setRetries(3);
			c.setStatuses(HttpStatus.SERVICE_UNAVAILABLE);
			c.setBackoff(Duration.ofMillis(500), Duration.ofMillis(500), 1, false);
		});
		RouteLocatorBuilder.Builder routes = builder.routes();
		if (agentGatewayProperties.enabled()) {
			routes.route("agent_route", r -> r.path("/api/agent/**").uri(agentGatewayProperties.uri()));
		}
		return routes
				.route("hello_route", r -> r.path("/test", "/api/**", "/orders/**").filters(f -> f.filter(retry)).uri("lb://openfeign-service"))
				.route("ws_route", r -> r.path("/ws/**").uri("lb:ws://mq-procedure-service"))
				.route("auth_route", r -> r.path("/login", "/login.html", "/home.html", "/as/**").filters(f -> f.filter(retry)).uri("lb://auth-service"))
				.route("direct_route", r -> r.path("/index").filters(f -> f.filter(retry)).uri("lb://m-service"))
				.route("mq_route", r -> r.path("/txn/**").filters(f -> f.filter(retry)).uri("lb://mq-procedure-service"))
				.route("workflow", r -> r.path("/workflows/**").filters(f -> f.filter(retry)).uri("lb://workflow-service"))
				.build();
	}
}
