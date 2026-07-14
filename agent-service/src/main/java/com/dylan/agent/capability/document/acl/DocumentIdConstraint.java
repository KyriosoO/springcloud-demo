package com.dylan.agent.capability.document.acl;

public sealed interface DocumentIdConstraint
        permits AllPrincipalVisibleDocuments, OnlyDocumentIds {
}
