package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.*;
import com.dylan.agent.adapter.api.operation.CapabilityOperationContext;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;

/** Handler internal execution 到 Spring-free Adapter command 的唯一工厂。 */
final class DocumentRetrievalCommandFactory {
    DocumentRetrievalCommand create(DocumentRetrievalExecution source,CapabilityOperationContext context){
        DocumentProtectedFilterBinding filter=java.util.Objects.requireNonNull(source.getProtectedFilterBinding(),"protected filter required");
        var ref=context.resourceLimits().reference();
        DocumentRetrievalExecutionBinding binding=new DocumentRetrievalExecutionBinding(source.getProfileName(),source.getProfileVersion(),
                filter.profileProjectionDigest(),ref,ref.canonicalDigest(),filter.aclEvidenceDigest());
        Optional<DocumentQueryEmbedding> embedding=source.getQueryVector().isEmpty()?Optional.empty():Optional.of(new DocumentQueryEmbedding(
                source.getQueryVector(),source.getQueryVector().size(),new DocumentEmbeddingBindingReference(source.getEmbeddingBindingDigest(),source.getQueryVector().size())));
        DocumentPreparedQuery query=new DocumentPreparedQuery(source.getQueryText(),source.getRuleKeywords(),source.getRewriteCandidates(),embedding);
        List<DocumentRetrievalChannel> enabled=new ArrayList<>();Map<DocumentRetrievalChannel,Integer> weights=new EnumMap<>(DocumentRetrievalChannel.class);
        var profile=source.getChannelProjection();enabled.addAll(profile.enabledChannels());weights.putAll(profile.channelWeights());
        if(source.getRetrievalMode()==com.dylan.agent.api.plan.DocumentRetrievalMode.KEYWORD)enabled.remove(DocumentRetrievalChannel.DENSE_VECTOR);
        DocumentResourceLimit limits=context.resourceLimits().require(com.dylan.agent.api.contract.common.AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT,DocumentResourceLimit.class);
        List<DocumentRetrievalChannel> required=profile.requiredChannels().stream().filter(enabled::contains).toList();
        DocumentRetrievalChannels channels=new DocumentRetrievalChannels(enabled,required,weights,
                Math.min(limits.retrieval().maxCandidatesPerChannel(),Math.max(profile.keywordCandidateCount(),profile.vectorCandidateCount())));
        DocumentContextOptions old=source.getContextOptions();DocumentContextSpec contextSpec=old==null?new DocumentContextSpec(0,0,0):
                new DocumentContextSpec(old.beforeChunks(),old.afterChunks(),old.maxContextChars());
        return new DocumentRetrievalCommand(source.getCorpusKey(),binding,source.getFilters().stream().map(f->new ValidatedDocumentCallerFilter(
                f.getField(),ValidatedDocumentCallerFilter.Operator.valueOf(f.getOperator().name()),f.getValue(),f.getValues())).toList(),filter,query,channels,
                new DocumentFusionSpec(profile.rrfK(),limits.retrieval().maxFusedCandidates()),
                new DocumentDedupSpec(Math.min(source.getTopK(),limits.retrieval().maxReturnedDocuments()),
                        Math.min(profile.maxChunksPerDocument(),limits.retrieval().maxChunksPerDocument())),contextSpec);
    }
}
