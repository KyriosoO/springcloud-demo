package com.dylan.springGateway.config;

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
				.route("hello_route", r -> r.path("/test", "/api", "/orders/**").filters(f -> f.filter(retry)).uri("lb://feignserver"))
				.route("auth_route", r -> r.path("/login", "/my", "/login.html", "/home.html").filters(f -> f.filter(retry)).uri("lb://authcenter"))
				.route("direct_route", r -> r.path("/index").filters(f -> f.filter(retry)).uri("lb://mserver"))
				.route("mq_route", r -> r.path("/txn/**").filters(f -> f.filter(retry)).uri("lb://mqprocedureserver"))
				.build();
	}
}
