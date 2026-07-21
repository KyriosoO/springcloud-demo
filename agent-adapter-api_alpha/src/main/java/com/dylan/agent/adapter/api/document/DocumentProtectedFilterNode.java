package com.dylan.agent.adapter.api.document;

/** 不允许承载 raw DSL 的封闭 ACL filter AST。 */
public sealed interface DocumentProtectedFilterNode
        permits DocumentAllOf, DocumentAnyOf, DocumentExactTerm, DocumentAnyTerms, DocumentNoneTerms {}
