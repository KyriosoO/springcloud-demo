package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Clock;
import java.time.ZoneOffset;

import org.junit.jupiter.api.Test;
import org.springframework.context.support.GenericApplicationContext;

import com.dylan.agent.metadata.config.AgentMetadataReloader;
import com.dylan.agent.metadata.config.AgentMetadataStore;
import com.dylan.agent.metadata.domain.internal.DomainMetadataPortImpl;
import com.dylan.agent.metadata.domain.internal.DomainMetadataPropertiesValidator;
import com.dylan.agent.metadata.domain.internal.DomainMetadataStore;
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
        return new DomainMetadataPortImpl(store, context, DomainMetadataTestSupport.TEST_CLOCK);
    }
}
