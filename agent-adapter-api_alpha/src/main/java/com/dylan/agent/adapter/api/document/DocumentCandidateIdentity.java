package com.dylan.agent.adapter.api.document;
public record DocumentCandidateIdentity(String documentId, String documentVersion, String chunkId, int chunkIndex) {
    public DocumentCandidateIdentity { if(documentId==null||documentId.isBlank()||documentVersion==null||documentVersion.isBlank()||chunkId==null||chunkId.isBlank()||chunkIndex<0) throw new IllegalArgumentException("candidate identity must be complete"); }
    /** 05 selection仅按opaque source identity分组，不向Provider暴露原始字段名。 */
    public String sourceIdentity(){return documentId;}
}
