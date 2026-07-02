package com.dylan.agent.metadata.domain;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

class EmployeeAdapterMetadataCoverageTest {

    @Test
    void employeeDomainHasQueryableAndAggregatableCatalogCoverage() {
        var catalog = DomainMetadataTestSupport.catalogView();

        var queryable = catalog.requireDomain("employee", AdapterRole.QUERYABLE);
        var aggregatable = catalog.requireDomain("employee", AdapterRole.AGGREGATABLE);

        assertThat(queryable.defaultSelectFields()).contains("chineseName", "memberNo", "position");
        assertThat(queryable.requireField("chineseName").operators())
                .contains(AgentOperator.EQ, AgentOperator.CONTAINS);
        assertThat(aggregatable.requireField("amount").functions()).isNotEmpty();
    }
}
