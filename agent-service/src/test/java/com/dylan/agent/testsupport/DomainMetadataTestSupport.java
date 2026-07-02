package com.dylan.agent.testsupport;

import com.dylan.agent.adapter.api.AdapterAggregateResult;
import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.AggregatableAdapter;
import com.dylan.agent.adapter.api.QueryableAdapter;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.metadata.domain.internal.AdapterPortResolver;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView;
import com.dylan.agent.metadata.domain.internal.DomainMetadataPortImpl;
import com.dylan.agent.metadata.domain.internal.DomainMetadataProperties;
import com.dylan.agent.metadata.domain.internal.DomainMetadataPropertiesValidator;
import com.dylan.agent.metadata.domain.internal.DomainMetadataStore;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.springframework.context.support.GenericApplicationContext;

/** Shared D04 metadata fixtures for tests. */
public final class DomainMetadataTestSupport {

    public static final Clock TEST_CLOCK =
            Clock.fixed(Instant.parse("2026-07-02T00:00:00Z"), ZoneOffset.UTC);

    private DomainMetadataTestSupport() {
    }

    public static AgentProperties agentProperties() {
        AgentProperties p = new AgentProperties();
        p.setIntentRoles(Map.of(
                AgentIntent.QUERY, Set.of("agent:viewer", "agent:admin"),
                AgentIntent.CLARIFY, Set.of("agent:viewer", "agent:admin"),
                AgentIntent.AGGREGATE, Set.of("agent:viewer", "agent:admin")));

        AgentProperties.RuntimeProperties rt = new AgentProperties.RuntimeProperties();
        rt.setBaseUrl("http://localhost:9230");
        rt.setSharedKey("test-key-at-least-16-characters");
        rt.setConnectTimeout(Duration.ofSeconds(2));
        rt.setReadTimeout(Duration.ofSeconds(15));
        rt.setMaxResponseBytes(65536);
        p.setRuntime(rt);

        AgentProperties.ConversationProperties conv = new AgentProperties.ConversationProperties();
        conv.setRecentTurnLimit(6);
        conv.setRetentionDays(7);
        conv.setCleanupDelay(Duration.ofHours(1));
        p.setConversation(conv);

        AgentProperties.QueryProperties q = new AgentProperties.QueryProperties();
        q.setDefaultSize(20);
        q.setMaxSize(100);
        q.setMaxResultWindow(10000);
        q.setMaxFilters(5);
        q.setMaxInValues(20);
        q.setMaxFilterValueLength(256);
        q.setMaxDownstreamResponseBytes(2097152);
        p.setQuery(q);

        AgentProperties.AggregateProperties agg = new AgentProperties.AggregateProperties();
        agg.setMaxMetrics(5);
        agg.setMaxGroupFields(2);
        agg.setDefaultMaxRows(20);
        agg.setMaxMaxRows(100);
        p.setAggregate(agg);
        return p;
    }

    public static DomainCatalogView catalogView() {
        return new DomainCatalogView(store());
    }

    public static DomainMetadataPortImpl domainMetadataPort() {
        GenericApplicationContext context = new GenericApplicationContext();
        context.registerBean("employeeAgentAdapter", QueryableAggregatableAdapter.class,
                QueryableAggregatableAdapter::new);
        context.registerBean("transactionAgentAdapter", QueryableAggregatableAdapter.class,
                QueryableAggregatableAdapter::new);
        context.refresh();
        return new DomainMetadataPortImpl(store(), context, TEST_CLOCK);
    }

    public static AdapterPortResolver adapterPortResolver(
            QueryableAdapter queryable,
            AggregatableAdapter aggregatable) {
        GenericApplicationContext context = new GenericApplicationContext();
        context.registerBean("employeeAgentAdapter", QueryableAggregatableAdapter.class,
                () -> new QueryableAggregatableAdapter(queryable, aggregatable));
        context.registerBean("transactionAgentAdapter", QueryableAggregatableAdapter.class,
                () -> new QueryableAggregatableAdapter(queryable, aggregatable));
        context.refresh();
        return new AdapterPortResolver(store(), context);
    }

    public static DomainMetadataStore store() {
        GenericApplicationContext context = new GenericApplicationContext();
        context.registerBean("employeeAgentAdapter", QueryableAggregatableAdapter.class,
                QueryableAggregatableAdapter::new);
        context.registerBean("transactionAgentAdapter", QueryableAggregatableAdapter.class,
                QueryableAggregatableAdapter::new);
        context.refresh();
        return new DomainMetadataStore(DomainMetadataPropertiesValidator.build(
                properties(), context.getBeansOfType(com.dylan.agent.adapter.api.AgentAdapterPort.class), TEST_CLOCK));
    }

    public static DomainMetadataProperties properties() {
        DomainMetadataProperties properties = new DomainMetadataProperties();
        properties.setCatalogVersion("catalog-test");
        properties.setAdapterRegistrationVersion("adapter-reg-test");
        properties.setDomains(Map.of(
                "employee", employeeDomain(),
                "transaction", transactionDomain()));
        properties.setRegistrations(List.of(
                registration("employee-queryable", "QUERYABLE", "employee",
                        QueryableAdapter.class, "employeeAgentAdapter"),
                registration("employee-aggregatable", "AGGREGATABLE", "employee",
                        AggregatableAdapter.class, "employeeAgentAdapter"),
                registration("transaction-queryable", "QUERYABLE", "transaction",
                        QueryableAdapter.class, "transactionAgentAdapter"),
                registration("transaction-aggregatable", "AGGREGATABLE", "transaction",
                        AggregatableAdapter.class, "transactionAgentAdapter")));
        return properties;
    }

    private static DomainMetadataProperties.DomainProperties employeeDomain() {
        DomainMetadataProperties.DomainProperties domain = new DomainMetadataProperties.DomainProperties();
        domain.setAliases(List.of("员工", "employee"));
        domain.setDescription("Employee records for tests.");
        domain.setFields(new LinkedHashMap<>());
        putString(domain, "chineseName");
        putString(domain, "memberNo");
        putString(domain, "position");
        putString(domain, "contactAddress");
        putString(domain, "idCardNo");
        putString(domain, "phoneNo");
        putString(domain, "email");
        putDecimal(domain, "amount");
        putInstant(domain, "transDate");
        domain.setDefaultSelectFieldsByRole(Map.of(
                "QUERYABLE", List.of("chineseName", "memberNo", "position"),
                "AGGREGATABLE", List.of("chineseName", "memberNo", "position")));
        domain.setRoleCapabilities(Map.of(
                "QUERYABLE", roleCapability(domain.getFields().keySet(), defaultOperators(), Map.of()),
                "AGGREGATABLE", roleCapability(domain.getFields().keySet(), defaultOperators(),
                        Map.of("amount", Set.of(AggregateFunction.SUM, AggregateFunction.AVG,
                                AggregateFunction.MIN, AggregateFunction.MAX)))));
        return domain;
    }

    private static DomainMetadataProperties.DomainProperties transactionDomain() {
        DomainMetadataProperties.DomainProperties domain = new DomainMetadataProperties.DomainProperties();
        domain.setAliases(List.of("交易", "transaction"));
        domain.setDescription("Transaction records for tests.");
        domain.setFields(new LinkedHashMap<>());
        putString(domain, "transId");
        putString(domain, "transType");
        putInstant(domain, "transDate");
        putDecimal(domain, "amount");
        domain.setDefaultSelectFieldsByRole(Map.of(
                "QUERYABLE", List.of("transId", "transType", "transDate", "amount"),
                "AGGREGATABLE", List.of("transId", "transType", "transDate", "amount")));
        domain.setRoleCapabilities(Map.of(
                "QUERYABLE", roleCapability(domain.getFields().keySet(), transactionOperators(), Map.of()),
                "AGGREGATABLE", roleCapability(domain.getFields().keySet(), transactionOperators(),
                        Map.of("amount", Set.of(AggregateFunction.SUM, AggregateFunction.AVG,
                                AggregateFunction.MIN, AggregateFunction.MAX)))));
        return domain;
    }

    private static void putString(DomainMetadataProperties.DomainProperties domain, String field) {
        DomainMetadataProperties.FieldProperties fp = field(field, AgentFieldType.STRING);
        fp.setMaxLength(256);
        domain.getFields().put(field, fp);
    }

    private static void putDecimal(DomainMetadataProperties.DomainProperties domain, String field) {
        DomainMetadataProperties.FieldProperties fp = field(field, AgentFieldType.DECIMAL);
        fp.setValueFormat("plain decimal only, precision 50, scale 2, no exponent");
        fp.setPrecision(50);
        fp.setScale(2);
        domain.getFields().put(field, fp);
    }

    private static void putInstant(DomainMetadataProperties.DomainProperties domain, String field) {
        DomainMetadataProperties.FieldProperties fp = field(field, AgentFieldType.INSTANT);
        fp.setValueFormat("ISO-8601 datetime with timezone");
        domain.getFields().put(field, fp);
    }

    private static DomainMetadataProperties.FieldProperties field(String field, AgentFieldType type) {
        DomainMetadataProperties.FieldProperties fp = new DomainMetadataProperties.FieldProperties();
        fp.setAliases(List.of(field));
        fp.setDescription(field + " field");
        fp.setType(type);
        return fp;
    }

    private static DomainMetadataProperties.RoleCapabilityProperties roleCapability(
            Set<String> fields,
            Map<String, Set<AgentOperator>> operators,
            Map<String, Set<AggregateFunction>> functions) {
        DomainMetadataProperties.RoleCapabilityProperties cp =
                new DomainMetadataProperties.RoleCapabilityProperties();
        cp.setFields(fields);
        cp.setOperatorsByField(operators);
        cp.setFunctionsByField(functions);
        cp.setMaxPageSize(100);
        cp.setMaxResultRows(100);
        return cp;
    }

    private static Map<String, Set<AgentOperator>> defaultOperators() {
        Map<String, Set<AgentOperator>> operators = new LinkedHashMap<>();
        Set<AgentOperator> stringOps = Set.of(AgentOperator.EQ, AgentOperator.CONTAINS,
                AgentOperator.CONTAINS_ANY, AgentOperator.STARTS_WITH,
                AgentOperator.STARTS_WITH_ANY, AgentOperator.IN);
        for (String field : List.of("chineseName", "memberNo", "position",
                "contactAddress", "idCardNo", "phoneNo", "email")) {
            operators.put(field, stringOps);
        }
        operators.put("amount", Set.of(AgentOperator.EQ, AgentOperator.IN, AgentOperator.GT, AgentOperator.LT));
        operators.put("transDate", Set.of(AgentOperator.EQ, AgentOperator.IN, AgentOperator.GT, AgentOperator.LT));
        return operators;
    }

    private static Map<String, Set<AgentOperator>> transactionOperators() {
        Map<String, Set<AgentOperator>> operators = new LinkedHashMap<>();
        operators.put("transId", Set.of(AgentOperator.EQ));
        operators.put("transType", Set.of(AgentOperator.EQ, AgentOperator.CONTAINS));
        operators.put("transDate", Set.of(AgentOperator.GT, AgentOperator.LT));
        operators.put("amount", Set.of(AgentOperator.EQ, AgentOperator.GT, AgentOperator.LT));
        return operators;
    }

    private static DomainMetadataProperties.RegistrationProperties registration(
            String id,
            String role,
            String domain,
            Class<?> portType,
            String beanName) {
        DomainMetadataProperties.RegistrationProperties registration =
                new DomainMetadataProperties.RegistrationProperties();
        registration.setRegistrationId(id);
        registration.setRole(role);
        registration.setDomain(domain);
        registration.setPortType(portType);
        registration.setPortBeanName(beanName);
        registration.setCatalogVersion("catalog-test");
        registration.setRegistrationVersion("adapter-reg-test");
        return registration;
    }

    public static class QueryableAggregatableAdapter implements QueryableAdapter, AggregatableAdapter {
        private final QueryableAdapter queryable;
        private final AggregatableAdapter aggregatable;

        public QueryableAggregatableAdapter() {
            this(null, null);
        }

        public QueryableAggregatableAdapter(QueryableAdapter queryable, AggregatableAdapter aggregatable) {
            this.queryable = queryable;
            this.aggregatable = aggregatable;
        }

        @Override
        public AdapterQueryResult query(ValidatedQuery query) {
            if (queryable != null) {
                return queryable.query(query);
            }
            return new AdapterQueryResult(List.of(), 0, 1, 20);
        }

        @Override
        public AdapterAggregateResult aggregate(ValidatedAggregateQuery query) {
            if (aggregatable != null) {
                return aggregatable.aggregate(query);
            }
            return new AdapterAggregateResult(List.of(), false);
        }
    }
}
