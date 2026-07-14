package com.dylan.agent.capability.document.acl;

/** P1 current permission evidence 的安全引用。 */
public record PermissionEvidenceReference(String evidenceId, String permissionVersion) {
    public PermissionEvidenceReference {
        evidenceId = requireText(evidenceId, "evidenceId");
        permissionVersion = requireText(permissionVersion, "permissionVersion");
    }

    private static String requireText(String value, String name) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " must not be blank");
        return value.trim();
    }
}
