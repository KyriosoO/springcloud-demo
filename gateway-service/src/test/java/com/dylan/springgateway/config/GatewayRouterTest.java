package com.dylan.springgateway.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.URI;
import java.time.Duration;
import java.util.List;
import java.util.Objects;

import org.junit.jupiter.api.Test;
import org.springframework.cloud.gateway.filter.factory.RetryGatewayFilterFactory;
import org.springframework.cloud.gateway.handler.predicate.PathRoutePredicateFactory;
import org.springframework.cloud.gateway.route.Route;
import org.springframework.cloud.gateway.route.builder.RouteLocatorBuilder;
import org.springframework.context.support.GenericApplicationContext;

class GatewayRouterTest {

	@Test
	void enabledAgentRouteUsesFixedUriAndHasNoRetryFilter() {
		try (GenericApplicationContext context = new GenericApplicationContext()) {
			context.registerBean(PathRoutePredicateFactory.class);
			context.refresh();
			var locator = new GatewayRouter().customRouteLocator(
					new RouteLocatorBuilder(context),
					new RetryGatewayFilterFactory(),
					new AgentGatewayProperties(true, URI.create("http://127.0.0.1:8085")));
			List<Route> routes = Objects.requireNonNull(
					locator.getRoutes().collectList().block(Duration.ofSeconds(5)));
			Route agent = routes.stream().filter(route -> "agent_route".equals(route.getId())).findFirst().orElseThrow();
			assertThat(agent.getUri()).isEqualTo(URI.create("http://127.0.0.1:8085"));
			assertThat(agent.getFilters()).isEmpty();
			assertThat(routes.getFirst().getId()).isEqualTo("agent_route");
		}
	}
}
