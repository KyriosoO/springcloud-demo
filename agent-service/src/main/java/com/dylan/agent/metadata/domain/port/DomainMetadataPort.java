package com.dylan.agent.metadata.domain.port;

import com.dylan.agent.adapter.api.AdapterRole;

import java.util.Set;

/** D02/D04 seam for domain metadata capabilities consumed by kernel startup. */
public interface DomainMetadataPort {
    Set<AdapterRole> knownRoles();
}
