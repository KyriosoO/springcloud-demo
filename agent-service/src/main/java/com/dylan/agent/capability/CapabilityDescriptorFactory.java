package com.dylan.agent.capability;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Set;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.AggregatableAdapterRegistry;
import com.dylan.agent.adapter.QueryableAdapterRegistry;
import com.dylan.agent.api.capability.AgentCapabilityDescriptor;
import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.capability.CapabilityContextSpec;
import com.dylan.agent.api.capability.CapabilityContractRef;
import com.dylan.agent.api.capability.CapabilityDomainScope;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.model.AgentUserContext;

/**
 * 从 handler registry、adapter registry 和配置组装 capability descriptor 列表。
 * 维护 capabilityId -> intent 的多对一映射。
 *
 * <p>descriptor 固定输出顺序：query.search, clarify.ask, aggregate.compute；
 * domainScopes 按 domain 名称升序输出，保证契约产物和测试断言稳定。
 *
 * <p>所有依赖均由 Spring 构造器注入，非 null。
 * risk/execution 由本类直接声明，不从 handler 读取，保持 handler 接口不承载 metadata。
 */
@Component
public class CapabilityDescriptorFactory {

    private final AgentCapabilityHandlerRegistry handlerRegistry;
    private final QueryableAdapterRegistry queryableAdapterRegistry;
    private final AggregatableAdapterRegistry aggregatableAdapterRegistry;
    private final AgentProperties properties;

    public CapabilityDescriptorFactory(
            AgentCapabilityHandlerRegistry handlerRegistry,
            QueryableAdapterRegistry queryableAdapterRegistry,
            AggregatableAdapterRegistry aggregatableAdapterRegistry,
            AgentProperties properties) {
        this.handlerRegistry = handlerRegistry;
        this.queryableAdapterRegistry = queryableAdapterRegistry;
        this.aggregatableAdapterRegistry = aggregatableAdapterRegistry;
        this.properties = properties;
    }

    /** 生成系统级 capability catalog，不依赖用户上下文，用于启动校验和审计。 */
    public List<AgentCapabilityDescriptor> createAll() {
        List<AgentCapabilityDescriptor> list = new ArrayList<>();

        list.add(buildQuerySearch());
        list.add(buildClarifyAsk());

        // 仅当 registry 非空 且 registry×config 交集非空时才输出 aggregate.compute，
        // 避免向 Runtime 发送一个 enabled scopes 为空的 capability，导致 Python 侧校验拒绝整个请求。
        if (aggregatableAdapterRegistry != null
                && !aggregatableAdapterRegistry.domains().isEmpty()
                && !aggregateDomainIntersection().isEmpty()) {
            list.add(buildAggregateCompute());
        }

        return list;
    }

    /** 生成 Runtime 请求可见的 capability 列表。
     *
     * <p>首期不做用户角色/权限过滤，直接委托 {@link #createAll()}。
     * 保留此方法作为运行时唯一出口，后续租户、角色、feature flag、灰度能力过滤都在这里收敛。
     *
     * @param userContext 当前用户上下文（首期未使用，后续用于权限感知过滤）
     */
    public List<AgentCapabilityDescriptor> createForRuntimeRequest(AgentUserContext userContext) {
        return createAll();
    }

    /** capabilityId -> AgentIntent 映射。 */
    public AgentIntent intentForCapability(String capabilityId) {
        return switch (capabilityId) {
            case "query.search" -> AgentIntent.QUERY;
            case "clarify.ask" -> AgentIntent.CLARIFY;
            case "aggregate.compute" -> AgentIntent.AGGREGATE;
            default -> throw new IllegalArgumentException("Unknown capabilityId: " + capabilityId);
        };
    }

    // ── descriptor 构造 ──────────────────────────────────────────────────────

    private AgentCapabilityDescriptor buildQuerySearch() {
        AgentCapabilityDescriptor d = new AgentCapabilityDescriptor();
        d.setCapabilityId("query.search");
        d.setIntent(AgentIntent.QUERY);
        d.setDisplayName("Search records");
        d.setDescription("Search records in a supported domain with filters, fields and pagination.");
        d.setDomainScopes(enabledScopes(queryDomainIntersection()));
        d.setRiskLevel(AgentCapabilityRiskLevel.READ_ONLY);
        d.setExecutionMode(AgentCapabilityExecutionMode.IMMEDIATE);
        d.setInputContract(contractRef("AgentPlan.query"));
        d.setOutputContract(contractRef("AgentQueryResult"));
        d.setContext(contextSpec(List.of("previousQuery"), List.of("RuntimeQueryContext")));
        d.setPermissions(List.of("domain", "field.filter", "field.display"));
        d.setEnabled(true);
        return d;
    }

    private AgentCapabilityDescriptor buildClarifyAsk() {
        AgentCapabilityDescriptor d = new AgentCapabilityDescriptor();
        d.setCapabilityId("clarify.ask");
        d.setIntent(AgentIntent.CLARIFY);
        d.setDisplayName("Ask for clarification");
        d.setDescription("Ask the user for missing or ambiguous search criteria.");
        d.setDomainScopes(List.of());
        d.setRiskLevel(AgentCapabilityRiskLevel.READ_ONLY);
        d.setExecutionMode(AgentCapabilityExecutionMode.IMMEDIATE);
        d.setInputContract(contractRef("ClarifySpec"));
        d.setOutputContract(contractRef("AgentChatResponse.CLARIFY"));
        d.setContext(contextSpec(List.of(), List.of()));
        d.setPermissions(List.of("agent.access"));
        d.setEnabled(true);
        return d;
    }

    private AgentCapabilityDescriptor buildAggregateCompute() {
        AgentCapabilityDescriptor d = new AgentCapabilityDescriptor();
        d.setCapabilityId("aggregate.compute");
        d.setIntent(AgentIntent.AGGREGATE);
        d.setDisplayName("Compute aggregate");
        d.setDescription("Compute aggregate metrics (COUNT, SUM, AVG, MIN, MAX) over records in a domain.");
        d.setDomainScopes(enabledScopes(aggregateDomainIntersection()));
        d.setRiskLevel(AgentCapabilityRiskLevel.READ_ONLY);
        d.setExecutionMode(AgentCapabilityExecutionMode.IMMEDIATE);
        d.setInputContract(contractRef("AgentPlan.aggregate"));
        d.setOutputContract(contractRef("AgentAggregateResult"));
        d.setContext(contextSpec(List.of(), List.of("RuntimeAggregateContext")));
        d.setPermissions(List.of("domain", "field.filter", "field.display"));
        d.setEnabled(true);
        return d;
    }

    // ── domain scope 计算 ────────────────────────────────────────────────────

    /** query.search 可用 domain：QueryableAdapterRegistry.domains() 与 AgentProperties.getDomains().keySet() 交集。 */
    private Set<String> queryDomainIntersection() {
        Set<String> adapterDomains = queryableAdapterRegistry.domains();
        Set<String> configDomains = properties.getDomains().keySet();
        Set<String> intersection = new java.util.HashSet<>(adapterDomains);
        intersection.retainAll(configDomains);
        return intersection;
    }

    /** aggregate.compute 可用 domain：AggregatableAdapterRegistry.domains() 与 AgentProperties.getDomains().keySet() 交集。 */
    private Set<String> aggregateDomainIntersection() {
        Set<String> adapterDomains = aggregatableAdapterRegistry.domains();
        Set<String> configDomains = properties.getDomains().keySet();
        Set<String> intersection = new java.util.HashSet<>(adapterDomains);
        intersection.retainAll(configDomains);
        return intersection;
    }

    private List<CapabilityDomainScope> enabledScopes(Set<String> domains) {
        return domains.stream()
                .sorted(Comparator.naturalOrder())
                .map(d -> {
                    CapabilityDomainScope scope = new CapabilityDomainScope();
                    scope.setDomain(d);
                    scope.setEnabled(true);
                    scope.setReasonCode(null);
                    return scope;
                })
                .toList();
    }

    // ── 辅助构造 ─────────────────────────────────────────────────────────────

    private CapabilityContractRef contractRef(String schema) {
        CapabilityContractRef ref = new CapabilityContractRef();
        ref.setSchema(schema);
        ref.setVersion("1.0");
        return ref;
    }

    private CapabilityContextSpec contextSpec(List<String> reads, List<String> writes) {
        CapabilityContextSpec spec = new CapabilityContextSpec();
        spec.setReads(reads);
        spec.setWrites(writes);
        return spec;
    }
}
