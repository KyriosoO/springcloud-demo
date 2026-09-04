package com.dylan.springgateway.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.util.List;
import java.util.Objects;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.cloud.gateway.filter.factory.RetryGatewayFilterFactory;
import org.springframework.cloud.gateway.handler.predicate.PathRoutePredicateFactory;
import org.springframework.cloud.gateway.route.Route;
import org.springframework.cloud.gateway.route.RouteLocator;
import org.springframework.cloud.gateway.route.builder.RouteLocatorBuilder;
import org.springframework.context.support.GenericApplicationContext;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;

import reactor.core.publisher.Mono;

@DisplayName("Gateway employee route exit")
class GatewayEmployeeRouteExitTest {

    @Test
    @DisplayName("employee API and pages are absent from the default Gateway")
    void shouldNotExposeEmployeeRoutes() {
        List<Route> routes = routes();

        assertThat(routes).extracting(Route::getId).doesNotContain("emp");
        assertThat(matchingRouteIds(routes, "/employees/42")).isEmpty();
        assertThat(matchingRouteIds(routes, "/employee-workflow.html")).isEmpty();
        assertThat(matchingRouteIds(routes, "/employee-es.html")).isEmpty();
    }

    @Test
    @DisplayName("retained infrastructure routes remain available")
    void shouldPreserveRetainedInfrastructureRoutes() {
        List<Route> routes = routes();

        assertThat(routes).extracting(Route::getId).contains(
                "agent_route", "hello_route", "ws_route", "auth_route", "direct_route",
                "mq_route", "workflow");
        assertThat(matchingRouteIds(routes, "/agent.html")).containsExactly("agent_route");
        assertThat(matchingRouteIds(routes, "/api/v1/agent/query-runs"))
                .containsExactly("agent_route", "hello_route");
        assertThat(routes.stream().map(Route::getId).toList().indexOf("agent_route"))
                .isLessThan(routes.stream().map(Route::getId).toList().indexOf("hello_route"));
        assertThat(routes.stream().filter(route -> "agent_route".equals(route.getId())).findFirst().orElseThrow()
                .getFilters()).isEmpty();
        assertThat(matchingRouteIds(routes, "/workflows/42")).containsExactly("workflow");
    }

    private static List<Route> routes() {
        try (GenericApplicationContext context = new GenericApplicationContext()) {
            context.registerBean(PathRoutePredicateFactory.class);
            context.refresh();
            RouteLocatorBuilder builder = new RouteLocatorBuilder(context);
            RouteLocator locator = new GatewayRouter().customRouteLocator(
                    builder, new RetryGatewayFilterFactory());
            return Objects.requireNonNull(locator.getRoutes().collectList().block(Duration.ofSeconds(5)));
        }
    }

    private static List<String> matchingRouteIds(List<Route> routes, String path) {
        MockServerWebExchange exchange = MockServerWebExchange.from(MockServerHttpRequest.get(path).build());
        return routes.stream()
                .filter(route -> Boolean.TRUE.equals(Mono.from(route.getPredicate().apply(exchange)).block()))
                .map(Route::getId)
                .toList();
    }
}
