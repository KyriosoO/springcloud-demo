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
        var catalog = DomainMetadataTestSupport.catalogView();

        var queryable = catalog.requireDomain("transaction", AdapterRole.QUERYABLE);
        var aggregatable = catalog.requireDomain("transaction", AdapterRole.AGGREGATABLE);

        assertThat(queryable.defaultSelectFields()).contains("transId", "transType", "transDate", "amount");
        assertThat(queryable.requireField("amount").operators())
                .contains(AgentOperator.EQ, AgentOperator.GT, AgentOperator.LT);
        assertThat(aggregatable.requireField("amount").functions())
                .contains(AggregateFunction.SUM, AggregateFunction.AVG,
                        AggregateFunction.MIN, AggregateFunction.MAX);
    }
}
