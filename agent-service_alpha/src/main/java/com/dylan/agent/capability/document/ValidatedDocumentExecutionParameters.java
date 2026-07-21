package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.DocumentContextOptions;
import com.dylan.agent.adapter.api.document.ValidatedDocumentCallerFilter;
import com.dylan.agent.adapter.api.query.ValidatedSort;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.plan.DocumentRetrievalMode;
import com.dylan.agent.api.plan.DocumentSummaryScope;

import java.util.List;

/** Validator 冻结的 Document 领域参数；不包含 ACL、target、Provider、deadline 或 Adapter command。 */
public record ValidatedDocumentExecutionParameters(
        DocumentPlanOperation operation,
        String normalizedQuery,
        List<ValidatedDocumentCallerFilter> callerFilters,
        List<ValidatedSort> sorts,
        int topK,
        int page,
        int size,
        DocumentSummaryScope summaryScope,
        boolean citationRequired,
        DocumentRetrievalMode retrievalMode,
        DocumentChannelProfileProjection channelProjection,
        DocumentContextOptions contextOptions) {
    public ValidatedDocumentExecutionParameters {
        if(operation==null||normalizedQuery==null||normalizedQuery.isBlank()||topK<=0||page<=0||size<=0
                ||retrievalMode==null||channelProjection==null)throw new IllegalArgumentException("validated document parameters incomplete");
        callerFilters=List.copyOf(callerFilters==null?List.of():callerFilters);sorts=List.copyOf(sorts==null?List.of():sorts);
    }
}
