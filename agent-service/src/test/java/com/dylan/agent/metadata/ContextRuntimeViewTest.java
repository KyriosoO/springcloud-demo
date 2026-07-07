package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import org.junit.jupiter.api.Test;

import com.dylan.agent.api.context.AggregateCapabilityContextPayload;
import com.dylan.agent.api.context.DocumentCapabilityContextPayload;
import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.RuntimeAggregateContextView;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.runtime.common.RuntimeDocumentContextView;
import com.dylan.agent.api.contract.runtime.common.RuntimeQueryContextView;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.plan.AgentSortSpec;
import com.dylan.agent.api.plan.AggregateMetricSpec;
import com.dylan.agent.api.plan.AggregateOrderSpec;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.kernel.definition.ContextReadDeclaration;
import com.dylan.agent.kernel.port.model.ExpectedContextVersion;
import com.dylan.agent.metadata.authorization.model.DelegationConstraintRef;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.config.AgentSecuritySettings;
import com.dylan.agent.metadata.config.AgentSecuritySettingsRegistry;
import com.dylan.agent.metadata.context.internal.ContextBoundary;
import com.dylan.agent.metadata.context.model.ContextRecordKey;
import com.dylan.agent.metadata.context.model.ContextSnapshot;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;

class ContextRuntimeViewTest {
    @Test
    void toRuntimeViewProjectsMinimalQueryContext() {
        ContextBoundary boundary = new ContextBoundary(
                new NoopContextRepository(), new PayloadJsonCodec(), new PlainCodec(), settings(),
                java.time.Clock.fixed(MetadataTestSupport.NOW, java.time.ZoneOffset.UTC));

        var view = boundary.toRuntimeView(snapshot(), declaration(), evidence());

        assertThat(view).isInstanceOf(RuntimeQueryContextView.class);
        assertThat(((RuntimeQueryContextView) view).getSelectFields()).containsExactly("name");
    }

    @Test
    void toRuntimeViewOnlyProjectsReadableFields() {
        ContextBoundary boundary = new ContextBoundary(
                new NoopContextRepository(), new PayloadJsonCodec(), new PlainCodec(), settings(),
                java.time.Clock.fixed(MetadataTestSupport.NOW, java.time.ZoneOffset.UTC));

        var view = (RuntimeQueryContextView) boundary.toRuntimeView(snapshot(), declaration(), evidence());

        assertThat(view.getSelectFields()).containsExactly("name");
        assertThat(view.getFilters()).isEmpty();
        assertThat(view.getPage()).isNull();
        assertThat(view.getSize()).isNull();
    }

    @Test
    void toRuntimeViewProjectsPaginationTotalsWhenReadable() {
        ContextBoundary boundary = new ContextBoundary(
                new NoopContextRepository(), new PayloadJsonCodec(), new PlainCodec(), settings(),
                java.time.Clock.fixed(MetadataTestSupport.NOW, java.time.ZoneOffset.UTC));

        var view = (RuntimeQueryContextView) boundary.toRuntimeView(
                snapshotWithTotals(),
                new ContextReadDeclaration(
                        RuntimeContextType.QUERY,
                        AgentExecutionContracts.QUERY_CONTEXT,
                        QueryCapabilityContextPayload.class,
                        false,
                        Set.of("selectFields", "page", "size", "total", "totalExact", "totalPages")),
                evidence());

        assertThat(view.getTotal()).isEqualTo(45L);
        assertThat(view.getTotalExact()).isTrue();
        assertThat(view.getTotalPages()).isEqualTo(3);
    }

    @Test
    void toRuntimeViewIncludesSortsWhenReadable() {
        ContextBoundary boundary = new ContextBoundary(
                new NoopContextRepository(), new PayloadJsonCodec(), new PlainCodec(), settings(),
                java.time.Clock.fixed(MetadataTestSupport.NOW, java.time.ZoneOffset.UTC));

        var view = (RuntimeQueryContextView) boundary.toRuntimeView(
                snapshotWithSorts(),
                new ContextReadDeclaration(
                        RuntimeContextType.QUERY,
                        AgentExecutionContracts.QUERY_CONTEXT,
                        QueryCapabilityContextPayload.class,
                        false,
                        Set.of("selectFields", "sorts")),
                evidence());

        assertThat(view.getSorts()).singleElement().satisfies(sort -> {
            assertThat(sort.getField()).isEqualTo("name");
            assertThat(sort.getDirection()).isEqualTo("DESC");
        });
    }

    @Test
    void toRuntimeViewIncludesAggregateOrderByWhenReadable() {
        ContextBoundary boundary = new ContextBoundary(
                new NoopContextRepository(), new PayloadJsonCodec(), new PlainCodec(), settings(),
                java.time.Clock.fixed(MetadataTestSupport.NOW, java.time.ZoneOffset.UTC));

        var view = (RuntimeAggregateContextView) boundary.toRuntimeView(
                aggregateSnapshotWithOrderBy(),
                new ContextReadDeclaration(
                        RuntimeContextType.AGGREGATE,
                        AgentExecutionContracts.AGGREGATE_CONTEXT,
                        AggregateCapabilityContextPayload.class,
                        false,
                        Set.of("metrics", "groupByFields", "orderBy", "maxRows")),
                aggregateEvidence());

        assertThat(view.getOrderBy()).singleElement().satisfies(order -> {
            assertThat(order.getField()).isEqualTo("totalAmount");
            assertThat(order.getDirection()).isEqualTo("DESC");
        });
    }

    @Test
    void toRuntimeViewProjectsDocumentContext() {
        ContextBoundary boundary = new ContextBoundary(
                new NoopContextRepository(), new PayloadJsonCodec(), new PlainCodec(), settings(),
                java.time.Clock.fixed(MetadataTestSupport.NOW, java.time.ZoneOffset.UTC));

        var view = (RuntimeDocumentContextView) boundary.toRuntimeView(
                documentSnapshot(),
                new ContextReadDeclaration(
                        RuntimeContextType.DOCUMENT,
                        AgentExecutionContracts.DOCUMENT_CONTEXT,
                        DocumentCapabilityContextPayload.class,
                        false,
                        Set.of("operation", "domain", "queryText", "citationIds", "topK")),
                documentEvidence());

        assertThat(view.getOperation()).isEqualTo("ANSWER");
        assertThat(view.getDomain()).isEqualTo("tax_policy");
        assertThat(view.getQueryText()).isEqualTo("当前增值税率有哪些？");
        assertThat(view.getCitationIds()).containsExactly("chunk-1");
        assertThat(view.getTopK()).isEqualTo(5);
        assertThat(view.getFilters()).isEmpty();
    }

    static ContextSnapshot snapshot() {
        return new ContextSnapshot(
                "ctx-1", "corr",
                new ContextRecordKey(new ContextOwnerRef("conversation", "conv-1"),
                        new ConversationScope("conv-1"),
                        com.dylan.agent.api.contract.runtime.common.RuntimeContextType.QUERY),
                "query.search", "inv-1", "employee",
                AgentExecutionContracts.QUERY_CONTEXT,
                AgentExecutionContracts.QUERY_CONTEXT,
                1,
                MetadataTestSupport.NOW.plusSeconds(60),
                "bundle-v1", "policy-v1", "perm", null,
                ExpectedContextVersion.version(1),
                new QueryCapabilityContextPayload(List.of(), List.of("name"), 1, 10));
    }

    static ContextSnapshot snapshotWithTotals() {
        return new ContextSnapshot(
                "ctx-1", "corr",
                new ContextRecordKey(new ContextOwnerRef("conversation", "conv-1"),
                        new ConversationScope("conv-1"),
                        com.dylan.agent.api.contract.runtime.common.RuntimeContextType.QUERY),
                "query.search", "inv-1", "employee",
                AgentExecutionContracts.QUERY_CONTEXT,
                AgentExecutionContracts.QUERY_CONTEXT,
                1,
                MetadataTestSupport.NOW.plusSeconds(60),
                "bundle-v1", "policy-v1", "perm", null,
                ExpectedContextVersion.version(1),
                new QueryCapabilityContextPayload(List.of(), List.of("name"), 1, 10, 45L, true, 3));
    }

    static ContextSnapshot snapshotWithSorts() {
        AgentSortSpec sort = new AgentSortSpec();
        sort.setField("name");
        sort.setDirection("DESC");
        return new ContextSnapshot(
                "ctx-1", "corr",
                new ContextRecordKey(new ContextOwnerRef("conversation", "conv-1"),
                        new ConversationScope("conv-1"),
                        com.dylan.agent.api.contract.runtime.common.RuntimeContextType.QUERY),
                "query.search", "inv-1", "employee",
                AgentExecutionContracts.QUERY_CONTEXT,
                AgentExecutionContracts.QUERY_CONTEXT,
                1,
                MetadataTestSupport.NOW.plusSeconds(60),
                "bundle-v1", "policy-v1", "perm", null,
                ExpectedContextVersion.version(1),
                new QueryCapabilityContextPayload(List.of(), List.of("name"), List.of(sort), 1, 10, null, null, null));
    }

    static ContextSnapshot aggregateSnapshotWithOrderBy() {
        AggregateMetricSpec metric = new AggregateMetricSpec();
        metric.setAlias("totalAmount");
        metric.setFunction(AggregateFunction.SUM);
        metric.setField("amount");
        AggregateOrderSpec order = new AggregateOrderSpec();
        order.setField("totalAmount");
        order.setDirection("DESC");
        return new ContextSnapshot(
                "ctx-aggregate", "corr",
                new ContextRecordKey(new ContextOwnerRef("conversation", "conv-1"),
                        new ConversationScope("conv-1"),
                        RuntimeContextType.AGGREGATE),
                "aggregate.compute", "inv-aggregate", "transaction",
                AgentExecutionContracts.AGGREGATE_CONTEXT,
                AgentExecutionContracts.AGGREGATE_CONTEXT,
                1,
                MetadataTestSupport.NOW.plusSeconds(60),
                "bundle-v1", "policy-v1", "perm", null,
                ExpectedContextVersion.version(1),
                new AggregateCapabilityContextPayload(
                        List.of(), List.of(metric), List.of("transType"), List.of(order), 20));
    }

    static ContextSnapshot documentSnapshot() {
        return new ContextSnapshot(
                "ctx-document", "corr",
                new ContextRecordKey(new ContextOwnerRef("conversation", "conv-1"),
                        new ConversationScope("conv-1"),
                        RuntimeContextType.DOCUMENT),
                "document.answer", "inv-document", "tax_policy",
                AgentExecutionContracts.DOCUMENT_CONTEXT,
                AgentExecutionContracts.DOCUMENT_CONTEXT,
                1,
                MetadataTestSupport.NOW.plusSeconds(60),
                "bundle-v1", "policy-v1", "perm", null,
                ExpectedContextVersion.version(1),
                new DocumentCapabilityContextPayload(
                        "ANSWER", "tax_policy", "当前增值税率有哪些？",
                        List.of(), List.of("chunk-1"), 5));
    }

    static ContextReadDeclaration declaration() {
        return new ContextReadDeclaration(
                RuntimeContextType.QUERY,
                AgentExecutionContracts.QUERY_CONTEXT,
                QueryCapabilityContextPayload.class,
                false,
                Set.of("selectFields"));
    }

    static PlanningAuthorizationEvidence evidence() {
        var bundle = MetadataTestSupport.bundle("bundle-v1", "digest-v1");
        var profile = bundle.profileVersionIndex().values().iterator().next();
        return new PlanningAuthorizationEvidence(
                "corr", "user:u-1", profile.key(), bundle.bundleVersion(), bundle.bundleDigest(),
                "policy-v1", "perm", "perm-v1", DelegationConstraintRef.CHAT_ALL,
                new com.dylan.agent.metadata.profile.internal.EffectiveProfileCalculator().compute(profile, bundle.activePolicy()),
                new PlanningEffectiveScope(Set.of("query.search"), Set.of("employee"), Map.of(),
                        Set.of(RuntimeContextType.QUERY), Set.of(RuntimeContextType.QUERY),
                        com.dylan.agent.api.capability.AgentCapabilityRiskLevel.READ_ONLY,
                        com.dylan.agent.api.capability.AgentCapabilityExecutionMode.IMMEDIATE,
                        Duration.ofSeconds(30), 1, 100, 100, 10_000),
                new DomainMetadataEvidence("catalog", "adapter", "availability", MetadataTestSupport.NOW),
                MetadataTestSupport.NOW,
                MetadataTestSupport.NOW.plusSeconds(60));
    }

    static PlanningAuthorizationEvidence aggregateEvidence() {
        var bundle = MetadataTestSupport.bundle("bundle-v1", "digest-v1");
        var profile = bundle.profileVersionIndex().values().iterator().next();
        return new PlanningAuthorizationEvidence(
                "corr", "user:u-1", profile.key(), bundle.bundleVersion(), bundle.bundleDigest(),
                "policy-v1", "perm", "perm-v1", DelegationConstraintRef.CHAT_ALL,
                new com.dylan.agent.metadata.profile.internal.EffectiveProfileCalculator().compute(profile, bundle.activePolicy()),
                new PlanningEffectiveScope(Set.of("aggregate.compute"), Set.of("transaction"), Map.of(),
                        Set.of(RuntimeContextType.AGGREGATE), Set.of(RuntimeContextType.AGGREGATE),
                        com.dylan.agent.api.capability.AgentCapabilityRiskLevel.READ_ONLY,
                        com.dylan.agent.api.capability.AgentCapabilityExecutionMode.IMMEDIATE,
                        Duration.ofSeconds(30), 1, 100, 100, 10_000),
                new DomainMetadataEvidence("catalog", "adapter", "availability", MetadataTestSupport.NOW),
                MetadataTestSupport.NOW,
                MetadataTestSupport.NOW.plusSeconds(60));
    }

    static PlanningAuthorizationEvidence documentEvidence() {
        var bundle = MetadataTestSupport.bundle("bundle-v1", "digest-v1");
        var profile = bundle.profileVersionIndex().values().iterator().next();
        return new PlanningAuthorizationEvidence(
                "corr", "user:u-1", profile.key(), bundle.bundleVersion(), bundle.bundleDigest(),
                "policy-v1", "perm", "perm-v1", DelegationConstraintRef.CHAT_ALL,
                new com.dylan.agent.metadata.profile.internal.EffectiveProfileCalculator().compute(profile, bundle.activePolicy()),
                new PlanningEffectiveScope(Set.of("document.answer"), Set.of("tax_policy"), Map.of(),
                        Set.of(RuntimeContextType.DOCUMENT), Set.of(RuntimeContextType.DOCUMENT),
                        com.dylan.agent.api.capability.AgentCapabilityRiskLevel.READ_ONLY,
                        com.dylan.agent.api.capability.AgentCapabilityExecutionMode.IMMEDIATE,
                        Duration.ofSeconds(30), 1, 100, 100, 10_000),
                new DomainMetadataEvidence("catalog", "adapter", "availability", MetadataTestSupport.NOW),
                MetadataTestSupport.NOW,
                MetadataTestSupport.NOW.plusSeconds(60));
    }

    private static AgentSecuritySettingsRegistry settings() {
        return new AgentSecuritySettingsRegistry(
                new AgentSecuritySettings(Duration.ofHours(1), Duration.ZERO, 10, "ACTIVE"));
    }
}
