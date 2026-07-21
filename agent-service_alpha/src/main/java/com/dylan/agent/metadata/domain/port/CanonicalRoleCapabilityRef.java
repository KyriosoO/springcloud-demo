package com.dylan.agent.metadata.domain.port;

import com.dylan.agent.adapter.api.AdapterRole;

import java.util.Objects;

/** Registration 绑定的 canonical role capability 身份，不复制字段事实。 */
public record CanonicalRoleCapabilityRef(
        String catalogVersion,
        String catalogDigest,
        String domain,
        AdapterRole role) {

    public CanonicalRoleCapabilityRef {
        catalogVersion = DomainMetadataStaticEvidence.requireText(catalogVersion, "catalogVersion");
        catalogDigest = DomainMetadataStaticEvidence.requireDigest(catalogDigest, "catalogDigest");
        domain = DomainMetadataStaticEvidence.requireText(domain, "domain");
        Objects.requireNonNull(role, "role must not be null");
    }

    public String safeRef() {
        return DomainMetadataEvidence.sha256(DomainMetadataEvidence.canonical(
                "DCR-1", catalogVersion, catalogDigest, domain, role.value()));
    }
}
