package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import org.junit.jupiter.api.Test;

import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.RuntimeQueryContextView;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.kernel.definition.ContextReadDeclaration;
import com.dylan.agent.kernel.port.model.ExpectedContextVersion;
import com.dylan.agent.metadata.authorization.model.DelegationConstraintRef;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.context.internal.ContextBoundary;
import com.dylan.agent.metadata.context.model.ContextRecordKey;
import com.dylan.agent.metadata.context.model.ContextSnapshot;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;

class ContextRuntimeViewTest {
    @Test
    void toRuntimeViewProjectsMinimalQueryContext() {
        ContextBoundary boundary = new ContextBoundary(
                new NoopContextRepository(), new PayloadJsonCodec(), new PlainCodec(),
                java.time.Clock.fixed(MetadataTestSupport.NOW, java.time.ZoneOffset.UTC));

        var view = boundary.toRuntimeView(snapshot(), declaration(), evidence());

        assertThat(view).isInstanceOf(RuntimeQueryContextView.class);
        assertThat(((RuntimeQueryContextView) view).getSelectFields()).containsExactly("name");
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

    static ContextReadDeclaration declaration() {
        return new ContextReadDeclaration(
                com.dylan.agent.api.contract.runtime.common.RuntimeContextType.QUERY,
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
                        Set.of(), Set.of(), com.dylan.agent.api.capability.AgentCapabilityRiskLevel.READ_ONLY,
                        com.dylan.agent.api.capability.AgentCapabilityExecutionMode.IMMEDIATE,
                        Duration.ofSeconds(30), 1, 100, 100, 10_000),
                new DomainMetadataEvidence("catalog", "adapter", "availability", MetadataTestSupport.NOW),
                MetadataTestSupport.NOW,
                MetadataTestSupport.NOW.plusSeconds(60));
    }
}
