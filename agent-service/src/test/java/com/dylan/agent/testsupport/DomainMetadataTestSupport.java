package com.dylan.agent.testsupport;

import com.dylan.agent.adapter.api.AdapterAggregateResult;
import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.AggregatableAdapter;
import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.QueryableAdapter;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.kernel.port.model.ExecutionFieldRule;
import com.dylan.agent.metadata.domain.internal.CanonicalDomainCatalog;
import com.dylan.agent.metadata.domain.internal.DomainMetadataPortImpl;
import com.dylan.agent.metadata.domain.internal.DomainMetadataProperties;
import com.dylan.agent.metadata.domain.internal.DomainMetadataPropertiesValidator;
import com.dylan.agent.metadata.domain.internal.DomainMetadataStore;
import com.dylan.agent.metadata.domain.internal.SpringBeanAdapterAvailabilityResolver;
import com.dylan.agent.metadata.domain.port.CanonicalRoleCapabilityRef;
import com.dylan.agent.metadata.domain.port.DomainAdapterKey;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.metadata.domain.port.DomainMetadataStaticEvidence;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import com.dylan.agent.adapter.api.AgentAdapterPort;
import com.dylan.agent.kernel.port.model.AdapterExecutionBinding;

import org.springframework.context.support.GenericApplicationContext;

/** 测试共享的 D04 元数据夹具。 */
public final class DomainMetadataTestSupport {

    public static final Clock TEST_CLOCK =
            Clock.fixed(Instant.parse("2026-07-02T00:00:00Z"), ZoneOffset.UTC);

    private DomainMetadataTestSupport() {
    }

    public static AgentProperties agentProperties() {
        AgentProperties p = new AgentProperties();
        AgentProperties.RuntimeProperties rt = new AgentProperties.RuntimeProperties();
        rt.setBaseUrl("http://localhost:9230");
        rt.setSharedKey("test-key-at-least-16-characters");
        rt.setConnectTimeout(Duration.ofSeconds(2));
        rt.setReadTimeout(Duration.ofSeconds(15));
        rt.setMaxResponseBytes(65536);
        p.setRuntime(rt);
        p.getProfile().setAllowedDomains(Set.of("employee", "transaction"));

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

    public static CanonicalDomainCatalog catalog() {
        return store().current().catalog();
    }

    public static Map<String, ExecutionFieldRule> executionFieldRules(String domain, AdapterRole role) {
        var definition = catalog().requireDomain(domain);
        var capability = definition.roleCapabilities().get(role);
        if (capability == null) {
            throw new IllegalArgumentException("domain 不支持指定 adapter role: " + domain + "/" + role);
        }
        Map<String, ExecutionFieldRule> rules = new LinkedHashMap<>();
        for (String field : capability.fields()) {
            var canonical = definition.fields().get(field);
            rules.put(field, new ExecutionFieldRule(
                    field,
                    canonical.type(),
                    capability.operatorsByField().getOrDefault(field, Set.of()),
                    capability.functionsByField().getOrDefault(field, Set.of()),
                    canonical.maxLength().orElse(null),
                    canonical.precision().orElse(null),
                    canonical.scale().orElse(null),
                    canonical.valueFormat().orElse(null)));
        }
        return Map.copyOf(rules);
    }

    public static DomainMetadataPortImpl domainMetadataPort() {
        GenericApplicationContext context = new GenericApplicationContext();
        context.registerBean("employeeAgentAdapter", QueryableAggregatableAdapter.class,
                QueryableAggregatableAdapter::new);
        context.registerBean("transactionAgentAdapter", QueryableAggregatableAdapter.class,
                QueryableAggregatableAdapter::new);
        context.refresh();
        DomainMetadataStore store = new DomainMetadataStore(DomainMetadataPropertiesValidator.build(
                properties(), context.getBeansOfType(com.dylan.agent.adapter.api.AgentAdapterPort.class), TEST_CLOCK));
        return new DomainMetadataPortImpl(
                store,
                context,
                new SpringBeanAdapterAvailabilityResolver(store, context, TEST_CLOCK),
                TEST_CLOCK);
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

    public static DomainMetadataEvidence currentEvidence() {
        DomainMetadataPortImpl port = domainMetadataPort();
        var scope = PlanningEffectiveScopeTestFactory.create(
                Set.of("query.search", "aggregate.compute"),
                Set.of("employee", "transaction"),
                Map.of(),
                Set.of(),
                Set.of(),
                com.dylan.agent.api.capability.AgentCapabilityRiskLevel.READ_ONLY,
                com.dylan.agent.api.capability.AgentCapabilityExecutionMode.IMMEDIATE,
                Duration.ofSeconds(30),
                1,
                100,
                100,
                10_000);
        return port.availability(
                Set.of(AdapterRole.QUERYABLE, AdapterRole.AGGREGATABLE),
                scope,
                TEST_CLOCK.instant().plusSeconds(60)).evidence();
    }

    public static DomainMetadataProperties properties() {
        DomainMetadataProperties properties = new DomainMetadataProperties();
        properties.setCatalogVersion("catalog-test");
        properties.setAdapterRegistrationVersion("adapter-reg-test");
        properties.setDomains(Map.of(
                "employee", employeeDomain(),
                "transaction", transactionDomain()));
        properties.setRegistrations(List.of(
                registration("employee-queryable", "QUERYABLE", "employee", "employeeAgentAdapter"),
                registration("employee-aggregatable", "AGGREGATABLE", "employee", "employeeAgentAdapter"),
                registration("transaction-queryable", "QUERYABLE", "transaction", "transactionAgentAdapter"),
                registration("transaction-aggregatable", "AGGREGATABLE", "transaction", "transactionAgentAdapter")));
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
        DomainMetadataProperties.RoleCapabilityProperties queryable =
                roleCapability(domain.getFields().keySet(), defaultOperators(), Map.of());
        queryable.setSortFields(Set.of("chineseName", "memberNo", "position", "contactAddress", "idCardNo", "phoneNo", "email"));
        domain.setRoleCapabilities(Map.of(
                "QUERYABLE", queryable,
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
        DomainMetadataProperties.RoleCapabilityProperties queryable =
                roleCapability(domain.getFields().keySet(), transactionOperators(), Map.of());
        queryable.setSortFields(Set.of("transId", "transType", "transDate", "amount"));
        domain.setRoleCapabilities(Map.of(
                "QUERYABLE", queryable,
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
            String beanName) {
        DomainMetadataProperties.RegistrationProperties registration =
                new DomainMetadataProperties.RegistrationProperties();
        registration.setRegistrationId(id);
        registration.setRole(role);
        registration.setDomain(domain);
        registration.setPortBeanName(beanName);
        registration.setRegistrationVersion("adapter-reg-test");
        return registration;
    }

    /** 构造不参与 DomainMetadataPort currentness 的最小测试证据。 */
    public static DomainMetadataEvidence evidence(
            String catalogVersion,
            String registrationVersion,
            String availabilitySeed,
            Instant capturedAt) {
        DomainMetadataStaticEvidence staticEvidence = new DomainMetadataStaticEvidence(
                catalogVersion,
                digest("catalog:" + catalogVersion),
                registrationVersion,
                digest("registration:" + registrationVersion),
                capturedAt);
        Set<DomainAdapterKey> keys = Set.of();
        return new DomainMetadataEvidence(
                staticEvidence,
                keys,
                DomainMetadataEvidence.keysDigest(keys),
                digest("availability:" + availabilitySeed),
                capturedAt);
    }

    public static <P extends AgentAdapterPort> AdapterExecutionBinding binding(
            AdapterRole role,
            String domain,
            Class<P> portType,
            P port,
            String registrationVersion,
            DomainMetadataEvidence evidence,
            Instant resolvedAt) {
        CanonicalRoleCapabilityRef capabilityRef = new CanonicalRoleCapabilityRef(
                evidence.catalogVersion(),
                evidence.staticEvidence().catalogDigest(),
                domain,
                role);
        return new AdapterExecutionBinding(
                role,
                domain,
                portType,
                port,
                "test-" + role.value().toLowerCase(java.util.Locale.ROOT) + "-" + domain,
                registrationVersion,
                capabilityRef,
                evidence,
                resolvedAt);
    }

    private static String digest(String value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
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
        public AdapterQueryResult query(
                ValidatedQuery query,
                com.dylan.agent.adapter.api.operation.CapabilityOperationContext operationContext) {
            if (queryable != null) {
                return queryable.query(query, operationContext);
            }
            return new AdapterQueryResult(List.of(), 0, 1, 20);
        }

        @Override
        public AdapterAggregateResult aggregate(
                ValidatedAggregateQuery query,
                com.dylan.agent.adapter.api.operation.CapabilityOperationContext operationContext) {
            if (aggregatable != null) {
                return aggregatable.aggregate(query, operationContext);
            }
            return new AdapterAggregateResult(List.of(), false);
        }
    }
}
