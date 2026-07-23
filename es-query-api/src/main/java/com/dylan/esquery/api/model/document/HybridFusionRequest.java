package com.dylan.esquery.api.model.document;

/** RRF 固定参数。 */
public record HybridFusionRequest(int rrfK,int maxFusedCandidates){
    public HybridFusionRequest{if(rrfK<=0||maxFusedCandidates<=0)throw new IllegalArgumentException("fusion invalid");}
}
