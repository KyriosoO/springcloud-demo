package com.dylan.esquery.document.search;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentTargetBindingDto;
import com.dylan.esquery.api.model.document.HybridSearchHit;
import com.dylan.esquery.api.model.document.HybridSearchRequest;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HashMap;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** security-bound distinct-document/chunk selection。 */
public final class DocumentResultSelector {
    public List<HybridSearchHit> select(List<FusedDocumentHit> fused,HybridSearchRequest request,DocumentTargetBindingDto target){
        Set<String> acceptedDocuments=new HashSet<>();Map<String,Integer> chunks=new HashMap<>();
        Map<String,String> bindingByDocumentId=new HashMap<>();
        java.util.ArrayList<HybridSearchHit> result=new java.util.ArrayList<>();
        for(FusedDocumentHit item:fused){BoundDocumentChannelHit hit=item.representative();
            String documentKey=hit.documentId()+"|"+hit.documentVersion()+"|"+hit.aclRef()+"|"+hit.aclVersion();
            String priorBinding=bindingByDocumentId.putIfAbsent(hit.documentId(),documentKey);
            if(priorBinding!=null&&!priorBinding.equals(documentKey))throw new IllegalArgumentException("document selection security binding conflict");
            if(!acceptedDocuments.contains(documentKey)){
                if(acceptedDocuments.size()>=request.dedup().maxReturnedDocuments())continue;
                acceptedDocuments.add(documentKey);
            }
            int count=chunks.getOrDefault(documentKey,0);if(count>=request.dedup().maxChunksPerDocument())continue;
            chunks.put(documentKey,count+1);
            result.add(new HybridSearchHit(candidateId(request.corpusKey(),target,request,hit),hit.documentId(),hit.documentVersion(),
                    hit.chunkId(),hit.chunkIndex(),hit.aclRef(),hit.aclVersion(),hit.title(),hit.sourceType(),hit.section(),hit.page(),
                    hit.sourceUri(),hit.snippet(),hit.content(),hit.citationText(),hit.generationText(),List.of(),List.of(),
                    hit.charStart(),hit.charEnd(),hit.esScore(),item.rrfScore(),item.channelRanks()));
        }
        return List.copyOf(result);
    }
    private static String candidateId(DocumentCorpusKeyDto corpus,DocumentTargetBindingDto target,HybridSearchRequest request,BoundDocumentChannelHit hit){
        return sha("DCI-1",corpus.domain(),corpus.materialType(),target.manifestDigest(),target.attestationDigest(),hit.documentId(),
                hit.documentVersion(),hit.chunkId(),hit.aclRef(),hit.aclVersion(),request.protectedFilterDigest(),request.executionBinding().aclEvidenceDigest());
    }
    private static String sha(String...values){try{MessageDigest digest=MessageDigest.getInstance("SHA-256");for(String value:values){byte[] bytes=value.getBytes(StandardCharsets.UTF_8);digest.update(new byte[]{(byte)(bytes.length>>>24),(byte)(bytes.length>>>16),(byte)(bytes.length>>>8),(byte)bytes.length});digest.update(bytes);}return HexFormat.of().formatHex(digest.digest());}catch(NoSuchAlgorithmException ex){throw new IllegalStateException(ex);}}
}
