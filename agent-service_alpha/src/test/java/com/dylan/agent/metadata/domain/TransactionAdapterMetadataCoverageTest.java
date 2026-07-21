package com.dylan.agent.metadata.domain;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

class TransactionAdapterMetadataCoverageTest {

    @Test
    void transactionDomainHasQueryableAndAggregatableCatalogCoverage() {
        var catalog = DomainMetadataTestSupport.catalog();

        var domain = catalog.requireDomain("transaction");
        var queryable = domain.roleCapabilities().get(AdapterRole.QUERYABLE);
        var aggregatable = domain.roleCapabilities().get(AdapterRole.AGGREGATABLE);

        assertThat(domain.defaultSelectFieldsByRole().get(AdapterRole.QUERYABLE))
                .contains("transId", "transType", "transDate", "amount");
        assertThat(queryable.operatorsByField().get("amount"))
                .contains(AgentOperator.EQ, AgentOperator.GT, AgentOperator.LT);
        assertThat(aggregatable.functionsByField().get("amount"))
                .contains(AggregateFunction.SUM, AggregateFunction.AVG,
                        AggregateFunction.MIN, AggregateFunction.MAX);
    }
}
