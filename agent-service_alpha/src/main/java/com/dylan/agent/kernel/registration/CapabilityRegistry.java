package com.dylan.agent.kernel.registration;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;

import java.util.*;

/**
 * 按 capabilityId 唯一解析 Registration 的不可变注册表。
 *
 * <p>构造时调用 CapabilityRegistrationValidator 后冻结。
 * 不计算 Profile/Policy/Permission/Domain availability，不执行 Validator/Handler。
 */
public final class CapabilityRegistry {

    private final Map<String, CapabilityRegistration<?, ?, ?>> registrations;
    private final Map<String, ResolvedRegistration> resolved;

    public CapabilityRegistry(Collection<CapabilityRegistration<?, ?, ?>> registrations,
                              CapabilityRegistrationValidator validator,
                              com.dylan.agent.kernel.definition.ContractRegistry contracts,
                              com.dylan.agent.kernel.resource.CapabilityResourceLimitRegistry resourceContracts,
                              Set<AdapterRole> knownRoles) {
        Objects.requireNonNull(registrations);
        Objects.requireNonNull(validator);
        if (registrations.isEmpty()) {
            throw new IllegalStateException("at least one CapabilityRegistration required");
        }
        validator.validateAll(registrations, contracts, resourceContracts, knownRoles);
        Map<String, CapabilityRegistration<?, ?, ?>> map = new LinkedHashMap<>();
        Map<String, ResolvedRegistration> resMap = new LinkedHashMap<>();
        for (CapabilityRegistration<?, ?, ?> reg : registrations) {
            String id = reg.definition().capabilityId();
            if (map.containsKey(id)) {
                throw new IllegalStateException("duplicate capabilityId: " + id);
            }
            map.put(id, reg);
            resMap.put(id, new ResolvedRegistration(
                    id, reg.definition().planKind(), reg.identity(), reg));
        }
        this.registrations = Collections.unmodifiableMap(map);
        this.resolved = Collections.unmodifiableMap(resMap);
    }

    /** 按 capabilityId 唯一解析；未知值 fail closed。 */
    public ResolvedRegistration resolve(String capabilityId) {
        ResolvedRegistration r = resolved.get(capabilityId);
        if (r == null) {
            throw new IllegalArgumentException("unknown capabilityId: " + capabilityId);
        }
        return r;
    }

    /** 不可变 Registration 集合，供 Catalog 计算。 */
    public Collection<CapabilityRegistration<?, ?, ?>> registrations() {
        return registrations.values();
    }

    /** 不可变 ID 集合。 */
    public Set<String> capabilityIds() {
        return registrations.keySet();
    }

    /** 仅启动覆盖检查，不选择 Handler。 */
    public Map<AgentPlanKind, List<String>> coverageByPlanKind() {
        Map<AgentPlanKind, List<String>> result = new EnumMap<>(AgentPlanKind.class);
        for (CapabilityRegistration<?, ?, ?> reg : registrations.values()) {
            result.computeIfAbsent(reg.definition().planKind(), k -> new ArrayList<>())
                    .add(reg.definition().capabilityId());
        }
        result.replaceAll((kind, ids) -> List.copyOf(ids));
        return Collections.unmodifiableMap(result);
    }
}
