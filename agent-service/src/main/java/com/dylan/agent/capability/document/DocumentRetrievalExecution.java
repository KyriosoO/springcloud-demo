package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.*;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedSort;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.plan.DocumentRetrievalMode;
import com.dylan.agent.api.plan.DocumentSummaryScope;

import java.util.List;

/** Handler 内 Invocation 短生命周期执行值；只在 command factory 前演进。 */
final class DocumentRetrievalExecution {
    private final DocumentPlanOperation operation;private final DocumentCorpusKey corpusKey;private final String profileName;private final String profileVersion;
    private final String queryText;private final List<String> ruleKeywords;private final List<String> rewriteCandidates;private final List<ValidatedFilter> filters;
    private final List<ValidatedSort> sorts;private final int topK;private final int page;private final int size;private final DocumentSummaryScope summaryScope;
    private final boolean citationRequired;private final DocumentRetrievalMode retrievalMode;private final List<Double> queryVector;
    private final String embeddingBindingDigest;private final DocumentChannelProfileProjection channelProjection;private final DocumentContextOptions contextOptions;
    private final DocumentProtectedFilterBinding protectedFilterBinding;
    DocumentRetrievalExecution(DocumentPlanOperation operation,DocumentCorpusKey corpusKey,String profileName,String profileVersion,String queryText,
            List<String> ruleKeywords,List<String> rewriteCandidates,List<ValidatedFilter> filters,List<ValidatedSort> sorts,int topK,int page,int size,
            DocumentSummaryScope summaryScope,boolean citationRequired,DocumentRetrievalMode retrievalMode,List<Double> queryVector,String embeddingBindingDigest,
            DocumentChannelProfileProjection channelProjection,DocumentContextOptions contextOptions,DocumentProtectedFilterBinding protectedFilterBinding){
        this.operation=operation;this.corpusKey=corpusKey;this.profileName=profileName;this.profileVersion=profileVersion;this.queryText=queryText;
        this.ruleKeywords=List.copyOf(ruleKeywords==null?List.of():ruleKeywords);this.rewriteCandidates=List.copyOf(rewriteCandidates==null?List.of():rewriteCandidates);
        this.filters=List.copyOf(filters==null?List.of():filters);this.sorts=List.copyOf(sorts==null?List.of():sorts);this.topK=topK;this.page=page;this.size=size;
        this.summaryScope=summaryScope;this.citationRequired=citationRequired;this.retrievalMode=retrievalMode;this.queryVector=List.copyOf(queryVector==null?List.of():queryVector);
        this.embeddingBindingDigest=embeddingBindingDigest;this.channelProjection=channelProjection;this.contextOptions=contextOptions;this.protectedFilterBinding=protectedFilterBinding;
    }
    DocumentPlanOperation getOperation(){return operation;}String getDomain(){return corpusKey.domain();}String getMaterialType(){return corpusKey.materialType();}
    DocumentCorpusKey getCorpusKey(){return corpusKey;}String getProfileName(){return profileName;}String getProfileVersion(){return profileVersion;}
    String getQueryText(){return queryText;}List<String> getRuleKeywords(){return ruleKeywords;}List<String> getRewriteCandidates(){return rewriteCandidates;}
    List<ValidatedFilter> getFilters(){return filters;}List<ValidatedSort> getSorts(){return sorts;}int getTopK(){return topK;}int getPage(){return page;}int getSize(){return size;}
    DocumentSummaryScope getSummaryScope(){return summaryScope;}boolean isCitationRequired(){return citationRequired;}DocumentRetrievalMode getRetrievalMode(){return retrievalMode;}
    List<Double> getQueryVector(){return queryVector;}String getEmbeddingBindingDigest(){return embeddingBindingDigest;}DocumentChannelProfileProjection getChannelProjection(){return channelProjection;}
    DocumentContextOptions getContextOptions(){return contextOptions;}DocumentProtectedFilterBinding getProtectedFilterBinding(){return protectedFilterBinding;}
    DocumentRetrievalExecution withProtectedFilterBinding(DocumentProtectedFilterBinding binding){return copy(retrievalMode,queryVector,embeddingBindingDigest,ruleKeywords,rewriteCandidates,binding);}
    DocumentRetrievalExecution copy(DocumentRetrievalMode mode,List<Double> vector,String binding,List<String> rules,List<String> rewrites,DocumentProtectedFilterBinding protectedBinding){
        return new DocumentRetrievalExecution(operation,corpusKey,profileName,profileVersion,queryText,rules,rewrites,filters,sorts,topK,page,size,summaryScope,
                citationRequired,mode,vector,binding,channelProjection,contextOptions,protectedBinding);}
}
