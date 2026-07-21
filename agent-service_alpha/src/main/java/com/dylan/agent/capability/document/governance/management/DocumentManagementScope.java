package com.dylan.agent.capability.document.governance.management;

/** 07 operation-specific 管理权限；不得用通用 admin scope 替代。 */
public enum DocumentManagementScope {
    EMERGENCY_EVIDENCE_ISSUE,
    PROVIDER_ACTIVATE,
    PROVIDER_DEACTIVATE,
    PROVIDER_ROLLBACK,
    EMERGENCY_DISABLE,
    EMERGENCY_CLEAR,
    GOVERNANCE_READ,
    GOVERNANCE_RECONCILE
}
