package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.document.*;
import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;
import com.dylan.agent.adapter.api.operation.CapabilityOperationContext;
import com.dylan.esquery.api.model.document.DocumentChannelResultSummary;
import com.dylan.esquery.api.model.document.HybridSearchHit;
import com.dylan.esquery.api.model.document.HybridSearchResponse;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/** Document response 的 envelope/channel/RRF/identity 跨服务完整性复核。 */
public final class DocumentRetrievalResponseBindingValidator {
    public List<AclBoundDocumentHit> validate(HybridSearchResponse response,DocumentRetrievalCommand request,CapabilityOperationContext context){
        Objects.requireNonNull(response,"document retrieval response required");DocumentProtectedFilterBinding expected=request.protectedFilter();
        var binding=response.binding();
        if(!context.requestCorrelationId().equals(binding.requestCorrelationId())||!context.operationId().equals(binding.operationId())
                ||!expected.corpusKey().domain().equals(binding.corpusKey().domain())||!expected.corpusKey().materialType().equals(binding.corpusKey().materialType())
                ||!expected.filterDigest().equals(binding.protectedFilterDigest())||!expected.aclEvidenceDigest().equals(binding.aclEvidenceDigest())
                ||!expected.profileProjectionDigest().equals(binding.profileProjectionDigest())
                ||!context.resourceLimits().reference().canonicalDigest().equals(binding.resourceLimit().canonicalDigest())
                ||!context.resourceLimits().reference().canonicalDigest().equals(binding.authorizationBindingDigest())){
            throw new IllegalArgumentException("document retrieval response envelope binding mismatch");}
        validateChannels(response,request);
        DocumentTargetBindingReference target=new DocumentTargetBindingReference(binding.targetBinding().schemaVersion(),binding.targetBinding().indexContentDigest(),
                binding.targetBinding().manifestDigest(),binding.targetBinding().attestationDigest());
        int maxHits=Math.multiplyExact(request.dedup().maxReturnedDocuments(),request.dedup().maxChunksPerDocument());
        if(response.hits().size()>maxHits||response.diagnostics().returnedChunkCount()!=response.hits().size())throw new IllegalArgumentException("document response hit count mismatch");
        List<AclBoundDocumentHit> result=new ArrayList<>();Set<String> identities=new HashSet<>();BigDecimal previous=null;
        for(HybridSearchHit hit:response.hits()){
            DocumentCandidateIdentity identity=new DocumentCandidateIdentity(hit.documentId(),hit.documentVersion(),hit.chunkId(),hit.chunkIndex());
            String key=identity.documentId()+"\u001f"+identity.documentVersion()+"\u001f"+identity.chunkId();if(!identities.add(key))throw new IllegalArgumentException("duplicate document candidate identity");
            BigDecimal recomputed=hit.channelRanks().stream().map(rank->BigDecimal.valueOf(weight(request,rank.channel().name()))
                    .divide(BigDecimal.valueOf((long)request.fusion().rrfK()+rank.rank()),18,RoundingMode.HALF_EVEN))
                    .reduce(BigDecimal.ZERO.setScale(18),BigDecimal::add).setScale(18,RoundingMode.HALF_EVEN);
            if(recomputed.compareTo(hit.rrfScore())!=0||(previous!=null&&previous.compareTo(hit.rrfScore())<0))throw new IllegalArgumentException("document response RRF/order mismatch");previous=hit.rrfScore();
            DocumentCandidateSecurityBinding security=new DocumentCandidateSecurityBinding(context.invocationId(),context.requestCorrelationId(),
                    context.resourceLimits().reference().registrationIdentity(),expected.corpusKey(),target,expected.filterDigest(),expected.aclEvidenceDigest(),
                    new DocumentAclObjectRef(hit.aclRef(),hit.aclVersion()),expected.profileProjectionDigest(),context.resourceLimits().reference());
            result.add(new AclBoundDocumentHit(hit.candidateId(),identity,hit.title(),hit.sourceType(),hit.section(),hit.page(),hit.sourceUri(),hit.snippet(),
                    hit.content(),hit.citationText(),hit.generationText(),hit.contextBefore(),hit.contextAfter(),hit.charStart(),hit.charEnd(),hit.score(),
                    hit.rrfScore(),hit.channelRanks().stream().map(rank->rank.channel().name()).toList(),safeFieldNames(hit),security));
        }
        return List.copyOf(result);
    }
    private static List<String> safeFieldNames(HybridSearchHit hit){List<String> fields=new ArrayList<>();
        if(hit.title()!=null)fields.add("title");if(hit.sourceType()!=null)fields.add("sourceType");if(hit.section()!=null)fields.add("section");
        if(hit.page()!=null)fields.add("page");if(hit.sourceUri()!=null)fields.add("sourceUri");if(hit.snippet()!=null)fields.add("snippet");
        if(hit.content()!=null)fields.add("content");if(hit.citationText()!=null)fields.add("citationText");if(hit.generationText()!=null)fields.add("generationText");
        if(!hit.contextBefore().isEmpty()||!hit.contextAfter().isEmpty())fields.add("context");return List.copyOf(fields);}
    private static void validateChannels(HybridSearchResponse response,DocumentRetrievalCommand request){Set<String> expected=request.channels().enabled().stream().map(Enum::name).collect(java.util.stream.Collectors.toSet());
        Set<String> actual=new HashSet<>();for(DocumentChannelResultSummary summary:response.channelResults()){
            if(!actual.add(summary.channel().name())||(summary.outcome()!=DocumentChannelResultSummary.Outcome.SUCCEEDED
                    && request.channels().required().stream().anyMatch(channel->channel.name().equals(summary.channel().name()))))throw new IllegalArgumentException("document required channel outcome invalid");}
        if(!actual.equals(expected))throw new IllegalArgumentException("document channel response incomplete");}
    private static int weight(DocumentRetrievalCommand request,String channel){Integer value=request.channels().weights().get(DocumentRetrievalChannel.valueOf(channel));
        if(value==null||value<=0)throw new IllegalArgumentException("document channel weight invalid");return value;}
}
