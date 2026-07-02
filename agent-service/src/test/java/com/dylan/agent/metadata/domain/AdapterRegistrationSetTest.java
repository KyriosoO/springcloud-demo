package com.dylan.agent.metadata.domain;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.AggregatableAdapter;
import com.dylan.agent.adapter.api.QueryableAdapter;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

class AdapterRegistrationSetTest {

    @Test
    void indexesOneRegistrationPerRoleAndDomainWithDeclaredPortType() {
        var registrations = DomainMetadataTestSupport.store().current().registrations();

        var employeeQuery = registrations.require(AdapterRole.QUERYABLE, "employee");
        var transactionAggregate = registrations.require(AdapterRole.AGGREGATABLE, "transaction");

        assertThat(employeeQuery.portType()).isEqualTo(QueryableAdapter.class);
        assertThat(transactionAggregate.portType()).isEqualTo(AggregatableAdapter.class);
        assertThat(registrations.domains(AdapterRole.QUERYABLE))
                .containsExactlyInAnyOrder("employee", "transaction");
        assertThat(registrations.sortedRegistrations())
                .extracting(registration -> registration.role().value() + "/" + registration.domain())
                .containsExactly(
                        "AGGREGATABLE/employee",
                        "AGGREGATABLE/transaction",
                        "QUERYABLE/employee",
                        "QUERYABLE/transaction");
    }
}
