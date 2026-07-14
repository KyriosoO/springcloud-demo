package com.dylan.agent.metadata.domain;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

class EmployeeAdapterMetadataCoverageTest {

    @Test
    void employeeDomainHasQueryableAndAggregatableCatalogCoverage() {
        var catalog = DomainMetadataTestSupport.catalog();

        var domain = catalog.requireDomain("employee");
        var queryable = domain.roleCapabilities().get(AdapterRole.QUERYABLE);
        var aggregatable = domain.roleCapabilities().get(AdapterRole.AGGREGATABLE);

        assertThat(domain.defaultSelectFieldsByRole().get(AdapterRole.QUERYABLE))
                .contains("chineseName", "memberNo", "position");
        assertThat(queryable.operatorsByField().get("chineseName"))
                .contains(AgentOperator.EQ, AgentOperator.CONTAINS);
        assertThat(aggregatable).isNotNull();
    }
}
