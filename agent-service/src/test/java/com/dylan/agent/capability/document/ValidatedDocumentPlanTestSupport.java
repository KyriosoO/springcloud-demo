package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.DocumentCorpusKey;
import com.dylan.agent.adapter.api.document.DocumentRetrievalChannel;
import com.dylan.agent.api.plan.DocumentGenerationOptions;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.plan.DocumentRetrievalMode;
import com.dylan.agent.capability.document.profile.DocumentFeaturePolicy;
import com.dylan.agent.capability.document.profile.DocumentPlanningProfileProjector;
import com.dylan.agent.capability.document.profile.DocumentProfileProjectionDigest;
import com.dylan.agent.capability.document.profile.DocumentProfileAssets;

import java.util.List;
import java.util.Map;

public final class ValidatedDocumentPlanTestSupport {
    private ValidatedDocumentPlanTestSupport() {}
    public static ValidatedDocumentPlan documentPlan(String capabilityId,String domain,ValidatedDocumentExecutionParameters parameters){
        return documentPlan(capabilityId,domain,parameters,null);}
    public static ValidatedDocumentExecutionParameters request(DocumentPlanOperation operation,String domain,String queryText,boolean citationRequired){
        return new ValidatedDocumentExecutionParameters(operation,queryText,List.of(),List.of(),5,1,5,null,citationRequired,
                DocumentRetrievalMode.KEYWORD,channels(),null);}
    public static ValidatedDocumentPlan documentPlan(String capabilityId,String domain,ValidatedDocumentExecutionParameters parameters,
                                                      DocumentGenerationOptions generationOptions){
        return documentPlan(capabilityId,domain,parameters,generationOptions,
                DocumentFeaturePolicy.DISABLED,DocumentFeaturePolicy.DISABLED,DocumentFeaturePolicy.DISABLED);
    }
    public static ValidatedDocumentPlan documentPlan(String capabilityId,String domain,ValidatedDocumentExecutionParameters parameters,
                                                      DocumentGenerationOptions generationOptions,
                                                      DocumentFeaturePolicy rewritePolicy,
                                                      DocumentFeaturePolicy embeddingPolicy,
                                                      DocumentFeaturePolicy rerankPolicy){
        DocumentCorpusKey corpus=new DocumentCorpusKey(domain,domain);
        DocumentExecutionProfileProjection profile=profile(
                corpus,parameters,rewritePolicy,embeddingPolicy,rerankPolicy);
        return new ValidatedDocumentPlan(capabilityId,domain,corpus,parameters,generationOptions,profile);}
    private static DocumentExecutionProfileProjection profile(DocumentCorpusKey corpus,
                                                               ValidatedDocumentExecutionParameters parameters,
                                                               DocumentFeaturePolicy rewritePolicy,
                                                               DocumentFeaturePolicy embeddingPolicy,
                                                               DocumentFeaturePolicy rerankPolicy){
        var properties=DocumentProfileTestSupport.properties();
        var entry=properties.getDefinitions().get(0);
        entry.setAllowedChannels(List.of("BM25"));entry.setRequiredChannels(List.of("BM25"));
        entry.setChannelWeights(Map.of("BM25",1));entry.setEmbeddingPolicy(embeddingPolicy);
        entry.setRewritePolicy(rewritePolicy);entry.setRerankPolicy(rerankPolicy);
        DocumentProfileAssets.BuiltAssets assets=DocumentProfileAssets.build(properties);
        String capabilityId=switch(parameters.operation()){
            case SEARCH->DocumentCapabilityIds.SEARCH;case ANSWER->DocumentCapabilityIds.ANSWER;case SUMMARIZE->DocumentCapabilityIds.SUMMARIZE;};
        var planning=new DocumentPlanningProfileProjector().project(
                DocumentProfileTestSupport.selection(assets,parameters.operation()),
                DocumentProfileTestSupport.limits(10,20,2_000),capabilityId);
        return new DocumentExecutionProfileProjection(
                planning.profileName(),planning.documentProfileVersion(),DocumentProfileProjectionDigest.compute(planning),
                corpus,parameters.operation(),planning.allowedChannels(),planning.requiredChannels(),planning.channelWeights(),
                planning.fusionPolicy(),planning.dedupPolicy(),planning.contextPolicy(),planning.rewritePolicy(),
                planning.embeddingPolicy(),planning.rerankPolicy(),planning.generationPolicy(),
                planning.searchableFields(),planning.returnableFields());}
    private static DocumentChannelProfileProjection channels(){return new DocumentChannelProfileProjection(10,10,60,20,1,
            List.of(DocumentRetrievalChannel.BM25),List.of(DocumentRetrievalChannel.BM25),Map.of(DocumentRetrievalChannel.BM25,1),false,0);}
}
