package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.AgentAdapterPort;
import com.dylan.agent.adapter.api.AggregatableAdapter;
import com.dylan.agent.adapter.api.QueryableAdapter;

import java.util.Map;
import java.util.Objects;
import java.util.Set;

/** Fixed D04 mapping from stable AdapterRole values to typed adapter ports. */
public final class AdapterRolePortTypes {

    private static final Map<AdapterRole, Class<? extends AgentAdapterPort>> TYPES = Map.of(
            AdapterRole.QUERYABLE, QueryableAdapter.class,
            AdapterRole.AGGREGATABLE, AggregatableAdapter.class);

    private AdapterRolePortTypes() {
    }

    public static Class<? extends AgentAdapterPort> requirePortType(AdapterRole role) {
        Class<? extends AgentAdapterPort> type = TYPES.get(Objects.requireNonNull(role, "role must not be null"));
        if (type == null) {
            throw new IllegalStateException("Unknown adapter role: " + role);
        }
        return type;
    }

    public static boolean isKnown(AdapterRole role) {
        return TYPES.containsKey(role);
    }

    public static Set<AdapterRole> knownRoles() {
        return TYPES.keySet();
    }
}
