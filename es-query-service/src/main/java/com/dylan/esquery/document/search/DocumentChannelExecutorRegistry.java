package com.dylan.esquery.document.search;

import com.dylan.esquery.api.model.DocumentSearchChannel;
import com.dylan.esquery.api.model.document.DocumentCallerFilterNode;
import com.dylan.esquery.api.model.document.DocumentHybridChannelRequest;
import com.dylan.esquery.api.model.document.HybridSearchRequest;
import com.dylan.esquery.document.DocumentCorpusDefinition;
import com.dylan.esquery.document.ResolvedIndexTargetRef;
import com.dylan.esquery.security.DocumentProtectedFilterCompiler;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.http.entity.ContentType;
import org.apache.http.nio.entity.NStringEntity;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestClient;

import java.io.IOException;
import java.time.Clock;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** 三个 closed channel executor 的有界 registry；每次请求只使用同一 resolved target/filter。 */
public final class DocumentChannelExecutorRegistry {
    private static final Set<String> PROTECTED_FIELDS=Set.of("tenantId","status","visibility","userIds","departmentIds","roleIds","attributeKeys","documentId");
    private final RestClient restClient;private final ObjectMapper objectMapper;private final DocumentProtectedFilterCompiler protectedCompiler;
    private final DocumentChannelHitBindingValidator hitValidator;private final Clock clock;
    public DocumentChannelExecutorRegistry(RestClient restClient,ObjectMapper objectMapper,DocumentProtectedFilterCompiler protectedCompiler,Clock clock){
        this.restClient=restClient;this.objectMapper=objectMapper;this.protectedCompiler=protectedCompiler;this.clock=clock;this.hitValidator=new DocumentChannelHitBindingValidator();}

    public List<BoundDocumentChannelHit> execute(
            DocumentHybridChannelRequest channel,HybridSearchRequest request,ResolvedIndexTargetRef target,DocumentCorpusDefinition corpus) throws IOException{
        requireLive(request);
        Map<String,Object> body=body(channel,request,target,corpus);
        Request es=new Request("POST","/"+target.physicalIndex()+"/_search");
        es.setEntity(new NStringEntity(objectMapper.writeValueAsString(body), ContentType.APPLICATION_JSON));
        Response response=restClient.performRequest(es);requireLive(request);
        JsonNode hits=objectMapper.readTree(response.getEntity().getContent()).path("hits").path("hits");
        if(!hits.isArray())throw new IllegalArgumentException("document channel response hits missing");
        List<BoundDocumentChannelHit> result=new ArrayList<>();int rank=1;
        for(JsonNode hit:hits){result.add(hitValidator.bind(hit,channel.channel(),rank++,corpus.indexedBusinessFields()));}
        return List.copyOf(result);
    }

    private Map<String,Object> body(DocumentHybridChannelRequest channel,HybridSearchRequest request,ResolvedIndexTargetRef target,DocumentCorpusDefinition corpus){
        List<Object> filter=compileFilters(request,corpus);
        Map<String,Object> body=new LinkedHashMap<>();
        body.put("_source",Map.of("excludes",List.of("embedding","embeddingText","aclPredicate")));
        body.put("track_total_hits",false);body.put("size",channel.candidateCount());
        if(channel.channel()==DocumentSearchChannel.DENSE_VECTOR){
            var embedding=request.queryPlan().embedding().orElseThrow(()->new IllegalArgumentException("dense vector embedding required"));
            if(target.vectorField()==null||target.vectorDimension()==null||target.vectorBindingDigest()==null
                    ||embedding.dimension()!=target.vectorDimension()||!embedding.providerBindingDigest().equals(target.vectorBindingDigest())){
                throw new IllegalArgumentException("VECTOR_INDEX_BINDING_MISMATCH");
            }
            body.put("knn",Map.of("field",target.vectorField(),"query_vector",embedding.vector(),"k",channel.candidateCount(),
                    "num_candidates",Math.max(channel.candidateCount(),channel.candidateCount()*4),"filter",Map.of("bool",Map.of("filter",filter))));
        }else{
            Object text=channel.channel()==DocumentSearchChannel.BM25?bm25(request):exactPhrase(request);
            body.put("query",Map.of("bool",Map.of("must",List.of(text),"filter",filter)));
        }
        return body;
    }
    List<Object> compileFilters(HybridSearchRequest request,DocumentCorpusDefinition corpus){
        List<Object> filter=new ArrayList<>();filter.add(protectedCompiler.compile(request.protectedFilter()));
        request.callerFilters().forEach(value->filter.add(caller(value,corpus)));return List.copyOf(filter);
    }
    private Object bm25(HybridSearchRequest request){List<String> variants=variants(request);return Map.of("bool",Map.of("should",variants.stream().map(v->Map.of("multi_match",Map.of("query",v,"fields",List.of("title^2","content","section")))).toList(),"minimum_should_match",1));}
    private Object exactPhrase(HybridSearchRequest request){return Map.of("match_phrase",Map.of("content",request.queryPlan().normalizedOriginal()));}
    private List<String> variants(HybridSearchRequest request){java.util.LinkedHashSet<String> values=new java.util.LinkedHashSet<>();values.add(request.queryPlan().normalizedOriginal());values.addAll(request.queryPlan().ruleKeywords());values.addAll(request.queryPlan().rewriteCandidates());return List.copyOf(values);}
    private Object caller(DocumentCallerFilterNode f,DocumentCorpusDefinition corpus){
        if(f==null||PROTECTED_FIELDS.contains(f.field())||!corpus.indexedBusinessFields().contains(f.field()))throw new IllegalArgumentException("unsupported document caller filter field");
        return switch(f.operator()){
            case EQ->Map.of("term",Map.of(f.field(),f.value()));case IN,CONTAINS_ANY->Map.of("terms",Map.of(f.field(),f.values()));
            case CONTAINS->Map.of("match",Map.of(f.field(),f.value()));case GT->range(f,"gt");case GTE->range(f,"gte");case LT->range(f,"lt");case LTE->range(f,"lte");};
    }
    private Object range(DocumentCallerFilterNode f,String op){return Map.of("range",Map.of(f.field(),Map.of(op,f.value())));}
    private void requireLive(HybridSearchRequest request){if(!Instant.ofEpochMilli(request.operationMetadata().absoluteDeadlineEpochMilli()).isAfter(clock.instant()))throw new IllegalStateException("document search deadline exceeded");}
}
