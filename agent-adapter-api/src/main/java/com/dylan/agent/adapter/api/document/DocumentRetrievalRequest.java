package com.dylan.agent.adapter.api.document;

import java.util.List;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedSort;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.plan.DocumentRetrievalMode;
import com.dylan.agent.api.plan.DocumentSummaryScope;

/** Java 校验后的文档检索请求。 */
public final class DocumentRetrievalRequest {

    private final DocumentPlanOperation operation;
    private final String domain;
    private final String materialType;
    private final String retrievalProfile;
    private final String profileVersion;
    private final String indexAlias;
    private final String permissionEvidenceId;
    private final String permissionVersion;
    private final String queryText;
    private final List<String> ruleKeywords;
    private final List<String> rewriteCandidates;
    private final List<ValidatedFilter> filters;
    private final List<ValidatedSort> sorts;
    private final int topK;
    private final int page;
    private final int size;
    private final DocumentSummaryScope summaryScope;
    private final boolean citationRequired;
    private final DocumentRetrievalMode retrievalMode;
    private final List<Double> queryVector;
    private final DocumentHybridOptions hybridOptions;
    private final DocumentContextOptions contextOptions;
    private final DocumentAclScope aclScope;

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
        this(operation, domain, queryText, filters, sorts, topK, page, size, summaryScope, citationRequired,
                DocumentRetrievalMode.KEYWORD, List.of(), null, null);
    }

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
            boolean citationRequired,
            DocumentRetrievalMode retrievalMode,
            List<Double> queryVector,
            DocumentHybridOptions hybridOptions,
            DocumentContextOptions contextOptions) {
        this(operation, domain, queryText, filters, sorts, topK, page, size, summaryScope, citationRequired,
                retrievalMode, queryVector, hybridOptions, contextOptions, null);
    }

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
            boolean citationRequired,
            DocumentRetrievalMode retrievalMode,
            List<Double> queryVector,
            DocumentHybridOptions hybridOptions,
            DocumentContextOptions contextOptions,
            DocumentAclScope aclScope) {
        this(operation, domain, null, null, null, null, queryText, List.of(), List.of(),
                filters, sorts, topK, page, size, summaryScope, citationRequired, retrievalMode,
                queryVector, hybridOptions, contextOptions, aclScope, null, null);
    }

    public DocumentRetrievalRequest(
            DocumentPlanOperation operation,
            String domain,
            String materialType,
            String retrievalProfile,
            String profileVersion,
            String indexAlias,
            String queryText,
            List<String> ruleKeywords,
            List<String> rewriteCandidates,
            List<ValidatedFilter> filters,
            List<ValidatedSort> sorts,
            int topK,
            int page,
            int size,
            DocumentSummaryScope summaryScope,
            boolean citationRequired,
            DocumentRetrievalMode retrievalMode,
            List<Double> queryVector,
            DocumentHybridOptions hybridOptions,
            DocumentContextOptions contextOptions,
            DocumentAclScope aclScope) {
        this(operation, domain, materialType, retrievalProfile, profileVersion, indexAlias, queryText,
                ruleKeywords, rewriteCandidates, filters, sorts, topK, page, size, summaryScope,
                citationRequired, retrievalMode, queryVector, hybridOptions, contextOptions,
                aclScope, null, null);
    }

    public DocumentRetrievalRequest(
            DocumentPlanOperation operation,
            String domain,
            String materialType,
            String retrievalProfile,
            String profileVersion,
            String indexAlias,
            String queryText,
            List<String> ruleKeywords,
            List<String> rewriteCandidates,
            List<ValidatedFilter> filters,
            List<ValidatedSort> sorts,
            int topK,
            int page,
            int size,
            DocumentSummaryScope summaryScope,
            boolean citationRequired,
            DocumentRetrievalMode retrievalMode,
            List<Double> queryVector,
            DocumentHybridOptions hybridOptions,
            DocumentContextOptions contextOptions,
            DocumentAclScope aclScope,
            String permissionEvidenceId,
            String permissionVersion) {
        this.operation = operation;
        this.domain = domain;
        this.materialType = materialType;
        this.retrievalProfile = retrievalProfile;
        this.profileVersion = profileVersion;
        this.indexAlias = indexAlias;
        this.permissionEvidenceId = permissionEvidenceId;
        this.permissionVersion = permissionVersion;
        this.queryText = queryText;
        this.ruleKeywords = List.copyOf(ruleKeywords == null ? List.of() : ruleKeywords);
        this.rewriteCandidates = List.copyOf(rewriteCandidates == null ? List.of() : rewriteCandidates);
        this.filters = List.copyOf(filters == null ? List.of() : filters);
        this.sorts = List.copyOf(sorts == null ? List.of() : sorts);
        this.topK = topK;
        this.page = page;
        this.size = size;
        this.summaryScope = summaryScope;
        this.citationRequired = citationRequired;
        this.retrievalMode = retrievalMode == null ? DocumentRetrievalMode.KEYWORD : retrievalMode;
        this.queryVector = List.copyOf(queryVector == null ? List.of() : queryVector);
        this.hybridOptions = hybridOptions;
        this.contextOptions = contextOptions;
        this.aclScope = aclScope;
    }

    public DocumentPlanOperation getOperation() { return operation; }
    public String getDomain() { return domain; }
    public String getMaterialType() { return materialType; }
    public String getRetrievalProfile() { return retrievalProfile; }
    public String getProfileVersion() { return profileVersion; }
    public String getIndexAlias() { return indexAlias; }
    public String getPermissionEvidenceId() { return permissionEvidenceId; }
    public String getPermissionVersion() { return permissionVersion; }
    public String getQueryText() { return queryText; }
    public List<String> getRuleKeywords() { return ruleKeywords; }
    public List<String> getRewriteCandidates() { return rewriteCandidates; }
    public List<ValidatedFilter> getFilters() { return filters; }
    public List<ValidatedSort> getSorts() { return sorts; }
    public int getTopK() { return topK; }
    public int getPage() { return page; }
    public int getSize() { return size; }
    public DocumentSummaryScope getSummaryScope() { return summaryScope; }
    public boolean isCitationRequired() { return citationRequired; }
    public DocumentRetrievalMode getRetrievalMode() { return retrievalMode; }
    public List<Double> getQueryVector() { return queryVector; }
    public DocumentHybridOptions getHybridOptions() { return hybridOptions; }
    public DocumentContextOptions getContextOptions() { return contextOptions; }
    public DocumentAclScope getAclScope() { return aclScope; }

    public DocumentRetrievalRequest withAclScope(DocumentAclScope aclScope) {
        return withAclScope(aclScope, permissionEvidenceId, permissionVersion);
    }

    public DocumentRetrievalRequest withAclScope(
            DocumentAclScope aclScope,
            String permissionEvidenceId,
            String permissionVersion) {
        return new DocumentRetrievalRequest(
                operation,
                domain,
                materialType,
                retrievalProfile,
                profileVersion,
                indexAlias,
                queryText,
                ruleKeywords,
                rewriteCandidates,
                filters,
                sorts,
                topK,
                page,
                size,
                summaryScope,
                citationRequired,
                retrievalMode,
                queryVector,
                hybridOptions,
                contextOptions,
                aclScope,
                permissionEvidenceId,
                permissionVersion);
    }
}
