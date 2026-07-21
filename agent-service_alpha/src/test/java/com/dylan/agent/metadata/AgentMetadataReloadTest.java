package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Clock;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import org.junit.jupiter.api.Test;
import org.springframework.context.support.GenericApplicationContext;

import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.metadata.config.AgentMetadataReloader;
import com.dylan.agent.metadata.config.AgentMetadataStore;
import com.dylan.agent.metadata.domain.internal.DomainMetadataPortImpl;
import com.dylan.agent.metadata.domain.internal.DomainMetadataPropertiesValidator;
import com.dylan.agent.metadata.domain.internal.DomainMetadataStore;
import com.dylan.agent.metadata.domain.internal.SpringBeanAdapterAvailabilityResolver;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.policy.model.DomainSecurityConstraints;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;


class AgentMetadataReloadTest {
    @Test
    void rejectsSameBundleVersionWithDifferentDigest() {
        var current = MetadataTestSupport.bundle("bundle-v1", "digest-v1");
        AgentMetadataReloader reloader = new AgentMetadataReloader(
                new AgentMetadataStore(current),
                domainPort(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        assertThatThrownBy(() -> reloader.publishValidated(
                MetadataTestSupport.bundle("bundle-v1", "digest-v2")))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("same metadata bundleVersion");
    }

    @Test
    void validatesPolicyRequiredMaskFieldReferences() {
        var current = MetadataTestSupport.bundle("bundle-v1", "digest-v1");
        AgentMetadataReloader reloader = new AgentMetadataReloader(
                new AgentMetadataStore(current),
                domainPort(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        var unknownField = new CanonicalFieldRef("employee", "unknownField");
        var candidate = MetadataTestSupport.bundleWithEmployeeFieldSecurity(
                "bundle-v2",
                "digest-v2",
                Map.of(unknownField, new DomainSecurityConstraints.FieldSecurityConstraint(
                        true,
                        true,
                        Set.of(AgentOperator.EQ),
                        Set.of(),
                        Optional.of(MaskType.ID_CARD),
                        new com.dylan.agent.metadata.policy.model.SecurityClassificationRef(
                                "test", "internal", "v1"),
                        Set.of())));

        assertThatThrownBy(() -> reloader.publishValidated(candidate))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("unknown field reference");
    }

    private DomainMetadataPortImpl domainPort() {
        GenericApplicationContext context = new GenericApplicationContext();
        context.registerBean("employeeAgentAdapter", DomainMetadataTestSupport.QueryableAggregatableAdapter.class,
                DomainMetadataTestSupport.QueryableAggregatableAdapter::new);
        context.registerBean("transactionAgentAdapter", DomainMetadataTestSupport.QueryableAggregatableAdapter.class,
                DomainMetadataTestSupport.QueryableAggregatableAdapter::new);
        context.refresh();
        var store = new DomainMetadataStore(DomainMetadataPropertiesValidator.build(
                DomainMetadataTestSupport.properties(),
                context.getBeansOfType(com.dylan.agent.adapter.api.AgentAdapterPort.class),
                DomainMetadataTestSupport.TEST_CLOCK));
        return new DomainMetadataPortImpl(
                store,
                context,
                new SpringBeanAdapterAvailabilityResolver(store, context, DomainMetadataTestSupport.TEST_CLOCK),
                DomainMetadataTestSupport.TEST_CLOCK);
    }
}
