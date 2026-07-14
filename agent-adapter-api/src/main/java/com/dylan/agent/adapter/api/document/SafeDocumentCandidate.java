package com.dylan.agent.adapter.api.document;
import java.util.List;
public record SafeDocumentCandidate(String candidateId,DocumentCandidateIdentity identity,String title,String section,Integer page,String safeSnippet,String safeContext,String safeSourceUri,List<String> safeFields,List<String> channelRanks,double fusedScore,DocumentCandidateSecurityBinding securityBinding) {
    public SafeDocumentCandidate { if(candidateId==null||candidateId.isBlank()||identity==null||securityBinding==null||!Double.isFinite(fusedScore)) throw new IllegalArgumentException("safe candidate binding invalid"); safeFields=List.copyOf(safeFields==null?List.of():safeFields); channelRanks=List.copyOf(channelRanks==null?List.of():channelRanks); }
}
