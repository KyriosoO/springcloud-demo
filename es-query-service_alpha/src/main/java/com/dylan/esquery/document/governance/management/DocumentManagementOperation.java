package com.dylan.esquery.document.governance.management;

public enum DocumentManagementOperation {
    INDEX_ACTIVATE(DocumentManagementScope.INDEX_ACTIVATE, "SCOPE_es.document.governance.index.activate"),
    INDEX_ROLLBACK(DocumentManagementScope.INDEX_ROLLBACK, "SCOPE_es.document.governance.index.rollback"),
    READ(DocumentManagementScope.READ, "SCOPE_es.document.governance.read"),
    RECONCILE(DocumentManagementScope.RECONCILE, "SCOPE_es.document.governance.reconcile");
    private final DocumentManagementScope scope; private final String authority;
    DocumentManagementOperation(DocumentManagementScope scope,String authority){this.scope=scope;this.authority=authority;}
    public DocumentManagementScope scope(){return scope;} public String authority(){return authority;}
}
