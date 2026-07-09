package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.AdapterDocumentEvidence;
import com.dylan.agent.adapter.api.document.generation.DocumentContextBudget;
import com.dylan.agent.capability.document.ValidatedDocumentPlan;
import com.dylan.agent.kernel.core.ExecutionContext;

import java.util.List;

/** 文档证据上下文打包请求。 */
public record DocumentContextPackRequest(
        ValidatedDocumentPlan plan,
        List<AdapterDocumentEvidence> evidence,
        ExecutionContext context,
        DocumentContextBudget budget) {
}
