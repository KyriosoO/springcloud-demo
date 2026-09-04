package com.dylan.springgateway.config;

import java.time.Duration;

import org.springframework.cloud.gateway.filter.GatewayFilter;
import org.springframework.cloud.gateway.filter.factory.RetryGatewayFilterFactory;
import org.springframework.cloud.gateway.route.RouteLocator;
import org.springframework.cloud.gateway.route.builder.RouteLocatorBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;

@Configuration
public class GatewayRouter {
	@Bean
	RouteLocator customRouteLocator(RouteLocatorBuilder builder, RetryGatewayFilterFactory retryFactory) {
		GatewayFilter retry = retryFactory.apply(c -> {
			c.setRetries(3);
			c.setStatuses(HttpStatus.SERVICE_UNAVAILABLE);
			c.setBackoff(Duration.ofMillis(500), Duration.ofMillis(500), 1, false);
		});
		return builder.routes()
				.route("agent_route", r -> r.path("/agent.html", "/api/v1/agent/**").uri("lb://agent-service"))
				.route("hello_route", r -> r.path("/test", "/api/**", "/orders/**").filters(f -> f.filter(retry)).uri("lb://openfeign-service"))
				.route("ws_route", r -> r.path("/ws/**").uri("lb:ws://mq-procedure-service"))
				.route("auth_route", r -> r.path("/login", "/login.html", "/home.html", "/as/**").filters(f -> f.filter(retry)).uri("lb://auth-service"))
				.route("direct_route", r -> r.path("/index").filters(f -> f.filter(retry)).uri("lb://m-service"))
				.route("mq_route", r -> r.path("/txn/**").filters(f -> f.filter(retry)).uri("lb://mq-procedure-service"))
				.route("workflow", r -> r.path("/workflows/**").filters(f -> f.filter(retry)).uri("lb://workflow-service"))
				.build();
	}
}
