package com.dylan.agent.capability.aggregate;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.AdapterAggregateResult;
import com.dylan.agent.adapter.api.AggregatableAdapter;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateMetric;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.capability.CapabilityExecutionContext;
import com.dylan.agent.capability.CapabilityExecutionResult;
import com.dylan.agent.capability.model.ValidatedAggregatePlan;
import com.dylan.agent.mask.AddressFieldMasker;
import com.dylan.agent.mask.EmailFieldMasker;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.dylan.agent.mask.IdCardFieldMasker;
import com.dylan.agent.mask.MobileFieldMasker;
import com.dylan.agent.mask.NoneFieldMasker;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.result.AggregateResultProcessor;
import com.dylan.agent.security.AgentPermissionService;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

@DisplayName("AggregateCapabilityHandler")
class AggregateCapabilityHandlerTest {

    private AggregateCapabilityHandler handler;
    private AgentUserContext user;

    @BeforeEach
    void setUp() {
        user = new AgentUserContext("admin", Set.of("agent:admin"));
        var catalogView = DomainMetadataTestSupport.catalogView();
        var validator = new StubValidator();
        var permissionService = new StubPermissionService();
        var adapter = new TestAggregateAdapter();
        var adapterPortResolver = DomainMetadataTestSupport.adapterPortResolver(null, adapter);
        var maskerRegistry = new FieldMaskerRegistry(List.of(new NoneFieldMasker(),
                new IdCardFieldMasker(), new MobileFieldMasker(),
                new EmailFieldMasker(), new AddressFieldMasker()));
        var resultProcessor = new AggregateResultProcessor(permissionService, maskerRegistry);
        handler = new AggregateCapabilityHandler(validator, permissionService, adapterPortResolver, resultProcessor);
    }

    @Test
    @DisplayName("execute 返回 aggregateResult")
    void shouldReturnAggregateResult() {
        var plan = new ValidatedAggregatePlan("transaction",
                new ValidatedAggregateQuery(List.of(),
                        List.of(new ValidatedAggregateMetric("total", AggregateFunction.COUNT, null)),
                        List.of(), null, 20));
        var ctx = new CapabilityExecutionContext("conv-1", "turn-001", "test", user, null);

        CapabilityExecutionResult result = handler.execute(ctx, plan);

        assertThat(result.intent()).isEqualTo(AgentIntent.AGGREGATE);
        assertThat(result.queryParameters()).isNull();
        assertThat(result.queryResult()).isNull();
        assertThat(result.aggregateResult()).isNotNull();
        assertThat(result.aggregateResult().getDomain()).isEqualTo("transaction");
        assertThat(result.contextToPersist()).isNotNull();
    }

    static class StubValidator extends AggregatePlanValidator {
        public StubValidator() {
            super(null, null, null, DomainMetadataTestSupport.catalogView());
        }

        @Override
        public ValidatedAggregatePlan validate(
                com.dylan.agent.capability.CapabilityValidationContext context) {
            return new ValidatedAggregatePlan("transaction",
                    new ValidatedAggregateQuery(List.of(), List.of(), List.of(), null, 20));
        }
    }

    static class StubPermissionService extends AgentPermissionService {
        public StubPermissionService() {
            super(DomainMetadataTestSupport.agentProperties(), DomainMetadataTestSupport.catalogView());
        }

        @Override
        public void checkIntent(AgentUserContext ctx, AgentIntent intent) {
        }

        @Override
        public void checkAggregate(AgentUserContext ctx, String domain, ValidatedAggregateQuery q) {
        }

        @Override
        public com.dylan.agent.model.FieldPolicy getDisplayPolicy(
                AgentUserContext ctx, String domain, String field) {
            return new com.dylan.agent.model.FieldPolicy(field, Set.of(),
                    Set.of("agent:admin"), Set.of("agent:admin"), com.dylan.agent.model.MaskType.NONE);
        }
    }

    static class TestAggregateAdapter implements AggregatableAdapter {
        @Override
        public AdapterAggregateResult aggregate(ValidatedAggregateQuery query) {
            return new AdapterAggregateResult(List.of(Map.of("total", 42L)), false);
        }
    }
}
