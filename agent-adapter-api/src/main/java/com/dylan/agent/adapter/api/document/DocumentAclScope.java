package com.dylan.agent.adapter.api.document;

import java.time.Instant;
import java.util.List;
import java.util.Objects;

/** 当前执行主体的文档 ACL 安全投影。 */
public final class DocumentAclScope {

    private final String tenantId;
    private final String userId;
    private final List<String> departmentIds;
    private final List<String> roleIds;
    private final List<String> attributeKeys;
    private final String aclSnapshotVersion;
    private final Instant expiresAt;

    public DocumentAclScope(
            String tenantId,
            String userId,
            List<String> departmentIds,
            List<String> roleIds,
            List<String> attributeKeys,
            String aclSnapshotVersion,
            Instant expiresAt) {
        this.tenantId = requireNonBlank(tenantId, "tenantId");
        this.userId = requireNonBlank(userId, "userId");
        this.departmentIds = copyList(departmentIds);
        this.roleIds = copyList(roleIds);
        this.attributeKeys = copyList(attributeKeys);
        this.aclSnapshotVersion = requireNonBlank(aclSnapshotVersion, "aclSnapshotVersion");
        this.expiresAt = Objects.requireNonNull(expiresAt, "expiresAt must not be null");
    }

    public String getTenantId() { return tenantId; }
    public String getUserId() { return userId; }
    public List<String> getDepartmentIds() { return departmentIds; }
    public List<String> getRoleIds() { return roleIds; }
    public List<String> getAttributeKeys() { return attributeKeys; }
    public String getAclSnapshotVersion() { return aclSnapshotVersion; }
    public Instant getExpiresAt() { return expiresAt; }

    public boolean isExpiredAt(Instant now) {
        return !expiresAt.isAfter(Objects.requireNonNull(now, "now must not be null"));
    }

    private static List<String> copyList(List<String> values) {
        return values == null ? List.of() : values.stream()
                .filter(value -> value != null && !value.isBlank())
                .toList();
    }

    private static String requireNonBlank(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return value;
    }
}
