package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.document.*;
import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;
import com.dylan.agent.adapter.api.operation.CapabilityOperationContext;
import com.dylan.esquery.api.model.document.DocumentChannelResultSummary;
import com.dylan.esquery.api.model.document.HybridSearchHit;
import com.dylan.esquery.api.model.document.HybridSearchResponse;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
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
        Set<com.dylan.esquery.api.model.DocumentSearchChannel> succeededChannels=validateChannels(response,request);
        DocumentTargetBindingReference target=new DocumentTargetBindingReference(binding.targetBinding().schemaVersion(),binding.targetBinding().indexContentDigest(),
                binding.targetBinding().manifestDigest(),binding.targetBinding().attestationDigest());
        int maxHits=Math.multiplyExact(request.dedup().maxReturnedDocuments(),request.dedup().maxChunksPerDocument());
        long rawCount=response.channelResults().stream().mapToLong(DocumentChannelResultSummary::hitCount).sum();
        long returnedDocuments=response.hits().stream().map(hit->hit.documentId()+"\u001f"+hit.documentVersion()).distinct().count();
        boolean truncated=response.diagnostics().fusedCandidateCount()>=request.fusion().maxFusedCandidates()
                ||response.hits().size()<response.diagnostics().fusedCandidateCount();
        if(response.hits().size()>maxHits||response.diagnostics().returnedChunkCount()!=response.hits().size()
                ||rawCount!=response.diagnostics().rawCandidateCount()
                ||response.hits().size()>response.diagnostics().fusedCandidateCount()
                ||returnedDocuments!=response.diagnostics().returnedDocumentCount()
                ||truncated!=response.diagnostics().candidateTruncated())
            throw new IllegalArgumentException("document response diagnostics/count mismatch");
        List<AclBoundDocumentHit> result=new ArrayList<>();Set<String> identities=new HashSet<>();HybridSearchHit previous=null;
        for(HybridSearchHit hit:response.hits()){
            DocumentCandidateIdentity identity=new DocumentCandidateIdentity(hit.documentId(),hit.documentVersion(),hit.chunkId(),hit.chunkIndex());
            String key=identity.documentId()+"\u001f"+identity.documentVersion()+"\u001f"+identity.chunkId();if(!identities.add(key))throw new IllegalArgumentException("duplicate document candidate identity");
            Set<com.dylan.esquery.api.model.DocumentSearchChannel> rankedChannels=new HashSet<>();
            if(hit.channelRanks().stream().anyMatch(rank->!rankedChannels.add(rank.channel())
                    ||!succeededChannels.contains(rank.channel())||rank.rank()>candidateCount(request,rank.channel().name())))
                throw new IllegalArgumentException("document response channel ranks invalid");
            BigDecimal recomputed=hit.channelRanks().stream().map(rank->BigDecimal.valueOf(weight(request,rank.channel().name()))
                    .divide(BigDecimal.valueOf((long)request.fusion().rrfK()+rank.rank()),18,RoundingMode.HALF_EVEN))
                    .reduce(BigDecimal.ZERO.setScale(18),BigDecimal::add).setScale(18,RoundingMode.HALF_EVEN);
            String expectedCandidateId=candidateId(expected.corpusKey(),target,expected,hit);
            if(recomputed.compareTo(hit.rrfScore())!=0||!expectedCandidateId.equals(hit.candidateId())
                    ||(previous!=null&&ORDER.compare(previous,hit)>0))
                throw new IllegalArgumentException("document response RRF/order/identity mismatch");
            previous=hit;
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
    private static Set<com.dylan.esquery.api.model.DocumentSearchChannel> validateChannels(HybridSearchResponse response,DocumentRetrievalCommand request){Set<String> expected=request.channels().enabled().stream().map(Enum::name).collect(java.util.stream.Collectors.toSet());
        Set<String> actual=new HashSet<>();Set<com.dylan.esquery.api.model.DocumentSearchChannel> succeeded=new HashSet<>();for(DocumentChannelResultSummary summary:response.channelResults()){
            if(!actual.add(summary.channel().name())||(summary.outcome()!=DocumentChannelResultSummary.Outcome.SUCCEEDED
                    && request.channels().required().stream().anyMatch(channel->channel.name().equals(summary.channel().name())))
                    ||summary.hitCount()>candidateCount(request,summary.channel().name())
                    ||summary.outcome()==DocumentChannelResultSummary.Outcome.DEGRADED&&summary.hitCount()!=0)
                throw new IllegalArgumentException("document required channel outcome invalid");}
        response.channelResults().stream().filter(summary->summary.outcome()==DocumentChannelResultSummary.Outcome.SUCCEEDED)
                .forEach(summary->succeeded.add(summary.channel()));
        if(!actual.equals(expected))throw new IllegalArgumentException("document channel response incomplete");return Set.copyOf(succeeded);}
    private static int weight(DocumentRetrievalCommand request,String channel){Integer value=request.channels().weights().get(DocumentRetrievalChannel.valueOf(channel));
        if(value==null||value<=0)throw new IllegalArgumentException("document channel weight invalid");return value;}
    private static int candidateCount(DocumentRetrievalCommand request,String channel){
        DocumentRetrievalChannel value=DocumentRetrievalChannel.valueOf(channel);
        if(!request.channels().enabled().contains(value))throw new IllegalArgumentException("document response channel is not enabled");
        return request.channels().candidatesPerChannel();}
    private static final Comparator<HybridSearchHit> ORDER=Comparator
            .comparing(HybridSearchHit::rrfScore).reversed()
            .thenComparingInt(hit->hit.channelRanks().stream().mapToInt(com.dylan.esquery.api.model.document.DocumentChannelRank::rank).min().orElseThrow())
            .thenComparing((HybridSearchHit hit)->hit.channelRanks().size(),Comparator.reverseOrder())
            .thenComparing(HybridSearchHit::documentId).thenComparing(HybridSearchHit::documentVersion)
            .thenComparingInt(HybridSearchHit::chunkIndex).thenComparing(HybridSearchHit::chunkId);
    private static String candidateId(DocumentCorpusKey corpus,DocumentTargetBindingReference target,
                                      DocumentProtectedFilterBinding binding,HybridSearchHit hit){
        return sha("DCI-1",corpus.domain(),corpus.materialType(),target.manifestDigest(),target.attestationDigest(),
                hit.documentId(),hit.documentVersion(),hit.chunkId(),hit.aclRef(),hit.aclVersion(),
                binding.filterDigest(),binding.aclEvidenceDigest());}
    private static String sha(String...values){try{MessageDigest digest=MessageDigest.getInstance("SHA-256");
        for(String value:values){byte[] bytes=value.getBytes(StandardCharsets.UTF_8);digest.update(new byte[]{
                (byte)(bytes.length>>>24),(byte)(bytes.length>>>16),(byte)(bytes.length>>>8),(byte)bytes.length});digest.update(bytes);}
        return HexFormat.of().formatHex(digest.digest());}catch(NoSuchAlgorithmException ex){throw new IllegalStateException(ex);}}
}
