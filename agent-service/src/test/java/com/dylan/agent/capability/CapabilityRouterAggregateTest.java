package com.dylan.agent.capability;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.AggregatableAdapterRegistry;
import com.dylan.agent.adapter.api.AdapterAggregateResult;
import com.dylan.agent.adapter.api.AggregatableAdapter;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.capability.aggregate.AggregateCapabilityHandler;
import com.dylan.agent.capability.aggregate.AggregatePlanValidator;
import com.dylan.agent.capability.clarify.ClarifyCapabilityHandler;
import com.dylan.agent.capability.clarify.ClarifyPlanValidator;
import com.dylan.agent.capability.query.QueryCapabilityHandler;
import com.dylan.agent.capability.query.QueryPlanValidator;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.dylan.agent.mask.NoneFieldMasker;
import com.dylan.agent.mask.IdCardFieldMasker;
import com.dylan.agent.mask.MobileFieldMasker;
import com.dylan.agent.mask.EmailFieldMasker;
import com.dylan.agent.mask.AddressFieldMasker;
import com.dylan.agent.result.AggregateResultProcessor;
import com.dylan.agent.security.AgentPermissionService;

@DisplayName("CapabilityRouter (AGGREGATE)")
class CapabilityRouterAggregateTest {

    private CapabilityRouter router;

    @BeforeEach
    void setUp() {
        var queryHandler = new QueryCapabilityHandler(
                new QueryPlanValidator(null, null, null, null),
                new AgentPermissionService(null),
                null, null);
        var clarifyHandler = new ClarifyCapabilityHandler(new ClarifyPlanValidator(null));

        var adapter = new TestAggregateAdapter();
        var registry = new AggregatableAdapterRegistry(List.of(adapter));
        var maskerRegistry = new FieldMaskerRegistry(List.of(new NoneFieldMasker(),
                new IdCardFieldMasker(), new MobileFieldMasker(),
                new EmailFieldMasker(), new AddressFieldMasker()));
        var permissionService = new AgentPermissionService(null);
        var resultProcessor = new AggregateResultProcessor(permissionService, maskerRegistry);
        var aggregateHandler = new AggregateCapabilityHandler(
                new AggregatePlanValidator(null, null, null, null),
                permissionService,
                registry,
                resultProcessor);

        var handlerRegistry = new AgentCapabilityHandlerRegistry(
                List.of(queryHandler, clarifyHandler, aggregateHandler));
        router = new CapabilityRouter(handlerRegistry);
    }

    @Test
    @DisplayName("registry 可注册 AGGREGATE handler")
    void shouldRegisterAggregateHandler() {
        var handler = router.route(AgentIntent.AGGREGATE);
        assertThat(handler.intent()).isEqualTo(AgentIntent.AGGREGATE);
    }

    @Test
    @DisplayName("router 仍可路由 QUERY")
    void shouldStillRouteQuery() {
        assertThat(router.route(AgentIntent.QUERY).intent()).isEqualTo(AgentIntent.QUERY);
    }

    @Test
    @DisplayName("router 仍可路由 CLARIFY")
    void shouldStillRouteClarify() {
        assertThat(router.route(AgentIntent.CLARIFY).intent()).isEqualTo(AgentIntent.CLARIFY);
    }

    static class TestAggregateAdapter implements AggregatableAdapter {
        @Override public String domain() { return "test"; }
        @Override public Set<String> supportedAggregateFields() { return Set.of("amount"); }
        @Override public Set<AggregateFunction> supportedFunctions(String field) { return Set.of(AggregateFunction.COUNT); }
        @Override public AdapterAggregateResult aggregate(ValidatedAggregateQuery query) {
            return new AdapterAggregateResult(List.of(Map.of("cnt", 1L)), false);
        }
    }
}
