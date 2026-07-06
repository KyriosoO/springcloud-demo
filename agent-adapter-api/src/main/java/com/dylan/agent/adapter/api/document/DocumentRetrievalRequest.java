package com.dylan.agent.adapter.api.document;

import java.util.List;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedSort;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.plan.DocumentSummaryScope;

/** Java 校验后的文档检索请求。 */
public final class DocumentRetrievalRequest {

    private final DocumentPlanOperation operation;
    private final String domain;
    private final String queryText;
    private final List<ValidatedFilter> filters;
    private final List<ValidatedSort> sorts;
    private final int topK;
    private final int page;
    private final int size;
    private final DocumentSummaryScope summaryScope;
    private final boolean citationRequired;

    public DocumentRetrievalRequest(
            DocumentPlanOperation operation,
            String domain,
            String queryText,
            List<ValidatedFilter> filters,
            List<ValidatedSort> sorts,
            int topK,
            int page,
            int size,
            DocumentSummaryScope summaryScope,
            boolean citationRequired) {
        this.operation = operation;
        this.domain = domain;
        this.queryText = queryText;
        this.filters = List.copyOf(filters == null ? List.of() : filters);
        this.sorts = List.copyOf(sorts == null ? List.of() : sorts);
        this.topK = topK;
        this.page = page;
        this.size = size;
        this.summaryScope = summaryScope;
        this.citationRequired = citationRequired;
    }

    public DocumentPlanOperation getOperation() { return operation; }
    public String getDomain() { return domain; }
    public String getQueryText() { return queryText; }
    public List<ValidatedFilter> getFilters() { return filters; }
    public List<ValidatedSort> getSorts() { return sorts; }
    public int getTopK() { return topK; }
    public int getPage() { return page; }
    public int getSize() { return size; }
    public DocumentSummaryScope getSummaryScope() { return summaryScope; }
    public boolean isCitationRequired() { return citationRequired; }
}
