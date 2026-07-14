package com.dylan.agent.metadata.domain;

import com.dylan.agent.metadata.domain.internal.DomainMetadataProperties;
import com.dylan.agent.metadata.domain.internal.DomainMetadataPropertiesValidator;
import com.dylan.agent.metadata.domain.internal.DomainMetadataStore;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

import org.junit.jupiter.api.Test;
import org.springframework.context.support.GenericApplicationContext;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DomainMetadataStoreTest {

    @Test
    void publishesWholeBundleWithCasAndRejectsVersionReuseWithDifferentDigest() {
        GenericApplicationContext context = context();
        var initial = build(DomainMetadataTestSupport.properties(), context);
        DomainMetadataStore store = new DomainMetadataStore(initial);

        DomainMetadataProperties reusedVersion = DomainMetadataTestSupport.properties();
        reusedVersion.getDomains().get("employee").setAliases(List.of("employee", "员工"));
        var conflicting = build(reusedVersion, context);
        assertThatThrownBy(() -> store.publish(initial.staticEvidence(), conflicting))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("METADATA_VERSION_REUSED");

        DomainMetadataProperties nextVersion = DomainMetadataTestSupport.properties();
        nextVersion.setCatalogVersion("catalog-test-v2");
        nextVersion.setAdapterRegistrationVersion("adapter-reg-test-v2");
        nextVersion.getRegistrations().forEach(registration ->
                registration.setRegistrationVersion("adapter-reg-test-v2"));
        var candidate = build(nextVersion, context);

        assertThat(store.publish(initial.staticEvidence(), candidate)).isTrue();
        assertThat(store.current()).isSameAs(candidate);
        assertThat(store.publish(initial.staticEvidence(), initial)).isFalse();
    }

    private com.dylan.agent.metadata.domain.internal.DomainMetadataStaticBundle build(
            DomainMetadataProperties properties,
            GenericApplicationContext context) {
        return DomainMetadataPropertiesValidator.build(
                properties,
                context.getBeansOfType(com.dylan.agent.adapter.api.AgentAdapterPort.class),
                DomainMetadataTestSupport.TEST_CLOCK);
    }

    private GenericApplicationContext context() {
        GenericApplicationContext context = new GenericApplicationContext();
        context.registerBean("employeeAgentAdapter",
                DomainMetadataTestSupport.QueryableAggregatableAdapter.class,
                DomainMetadataTestSupport.QueryableAggregatableAdapter::new);
        context.registerBean("transactionAgentAdapter",
                DomainMetadataTestSupport.QueryableAggregatableAdapter.class,
                DomainMetadataTestSupport.QueryableAggregatableAdapter::new);
        context.refresh();
        return context;
    }
}
