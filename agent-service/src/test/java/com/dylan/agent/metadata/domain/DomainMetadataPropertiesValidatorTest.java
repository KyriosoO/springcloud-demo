package com.dylan.agent.metadata.domain;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.springframework.context.support.GenericApplicationContext;

import com.dylan.agent.metadata.domain.internal.DomainMetadataPropertiesValidator;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

class DomainMetadataPropertiesValidatorTest {

    @Test
    void rejectsNegativeRoleLimits() {
        var properties = DomainMetadataTestSupport.properties();
        properties.getDomains().get("employee")
                .getRoleCapabilities().get("QUERYABLE")
                .setMaxPageSize(-1);

        assertThatThrownBy(() -> DomainMetadataPropertiesValidator.build(
                properties,
                context().getBeansOfType(com.dylan.agent.adapter.api.AgentAdapterPort.class),
                DomainMetadataTestSupport.TEST_CLOCK))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("negative");
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
