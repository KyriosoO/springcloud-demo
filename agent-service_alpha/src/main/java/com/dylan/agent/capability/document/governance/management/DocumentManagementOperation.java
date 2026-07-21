package com.dylan.agent.capability.document.governance.management;

public enum DocumentManagementOperation {
    EMERGENCY_EVIDENCE_ISSUE(
            "SCOPE_agent.document.governance.emergency-evidence.issue",
            DocumentManagementScope.EMERGENCY_EVIDENCE_ISSUE),
    PROVIDER_ACTIVATE("SCOPE_agent.document.governance.provider.activate", DocumentManagementScope.PROVIDER_ACTIVATE),
    PROVIDER_DEACTIVATE("SCOPE_agent.document.governance.provider.deactivate", DocumentManagementScope.PROVIDER_DEACTIVATE),
    PROVIDER_ROLLBACK("SCOPE_agent.document.governance.provider.rollback", DocumentManagementScope.PROVIDER_ROLLBACK),
    EMERGENCY_DISABLE("SCOPE_agent.document.governance.emergency.disable", DocumentManagementScope.EMERGENCY_DISABLE),
    EMERGENCY_CLEAR("SCOPE_agent.document.governance.emergency.clear", DocumentManagementScope.EMERGENCY_CLEAR),
    GOVERNANCE_READ("SCOPE_agent.document.governance.read", DocumentManagementScope.GOVERNANCE_READ),
    GOVERNANCE_RECONCILE("SCOPE_agent.document.governance.reconcile", DocumentManagementScope.GOVERNANCE_RECONCILE);

    private final String authority;
    private final DocumentManagementScope scope;

    DocumentManagementOperation(String authority, DocumentManagementScope scope) {
        this.authority = authority;
        this.scope = scope;
    }

    public String authority() { return authority; }
    public DocumentManagementScope scope() { return scope; }
}
