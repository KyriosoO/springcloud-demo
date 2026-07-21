package com.dylan.esquery.service;

import com.dylan.esquery.api.model.VectorSearchRequest;
import com.dylan.esquery.config.EsQueryProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.apache.http.HttpEntity;
import org.apache.http.entity.ContentType;
import org.apache.http.nio.entity.NStringEntity;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.ResponseException;
import org.elasticsearch.client.RestClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 非Document generic ES操作；Document target由Controller guard拒绝并走专用服务。 */
@Service
public class EsDocumentService {
    private static final String DEFAULT_EMBEDDING_FIELD = "embedding";
    private final RestClient restClient;
    private final ObjectMapper objectMapper;
    private final EsQueryProperties properties;
    private final DocumentIndexPolicy documentIndexPolicy;
    private final DocumentChunkSchemaValidator chunkSchemaValidator;
    private final DocumentIndexDefinitionValidator indexDefinitionValidator;

    public EsDocumentService(RestClient restClient, ObjectMapper objectMapper, EsQueryProperties properties) {
        this(restClient, objectMapper, properties, new DocumentIndexPolicy(properties),
                new DocumentChunkSchemaValidator(), new DocumentIndexDefinitionValidator());
    }

    @Autowired
    public EsDocumentService(RestClient restClient, ObjectMapper objectMapper, EsQueryProperties properties,
                             DocumentIndexPolicy documentIndexPolicy,
                             DocumentChunkSchemaValidator chunkSchemaValidator,
                             DocumentIndexDefinitionValidator indexDefinitionValidator) {
        this.restClient = restClient;this.objectMapper = objectMapper;this.properties = properties;
        this.documentIndexPolicy = documentIndexPolicy;this.chunkSchemaValidator = chunkSchemaValidator;
        this.indexDefinitionValidator = indexDefinitionValidator;
    }

    public String search(String index, String queryDsl) throws IOException {
        Request request = new Request("POST", "/" + index + "/_search");
        request.setEntity(jsonEntity(applyDefaultTrackTotalHits(queryDsl)));
        return responseBody(restClient.performRequest(request));
    }

    public String indexDocument(String index, String id, Map<String,Object> document) throws IOException {
        validateDocumentChunkIfNeeded(index, document);
        String endpoint=id==null||id.isBlank()?"/"+index+"/_doc":"/"+index+"/_doc/"+id;
        Request request=new Request(id==null||id.isBlank()?"POST":"PUT",endpoint);
        request.setEntity(jsonEntity(objectMapper.writeValueAsString(document)));
        return responseBody(restClient.performRequest(request));
    }

    public String deleteDocument(String index,String id)throws IOException{
        if(id==null||id.isBlank())throw new IllegalArgumentException("document id must not be blank");
        return responseBody(restClient.performRequest(new Request("DELETE","/"+index+"/_doc/"+id)));
    }

    public String bulkIndex(String index,String idField,List<Map<String,Object>> documents)throws IOException{
        if(documentIndexPolicy.isDocumentIndex(index)&&(idField==null||idField.isBlank()))throw new IllegalArgumentException("document index bulk idField must not be blank");
        if(documents!=null)documents.forEach(document->validateDocumentChunkIfNeeded(index,document));
        Request request=new Request("POST","/_bulk");
        request.setEntity(new NStringEntity(buildBulkBody(index,idField,documents),ContentType.create("application/x-ndjson","UTF-8")));
        return responseBody(restClient.performRequest(request));
    }

    public void recreateIndex(String index)throws IOException{recreateIndex(index,null);}
    public void recreateIndex(String index,Map<String,Object> definition)throws IOException{
        if(documentIndexPolicy.isDocumentIndex(index))indexDefinitionValidator.validate(index,definition);
        deleteIndexIfExists(index);Request create=new Request("PUT","/"+index);
        if(definition!=null&&!definition.isEmpty())create.setEntity(jsonEntity(objectMapper.writeValueAsString(definition)));
        restClient.performRequest(create);
    }

    public String vectorSearch(String index,VectorSearchRequest request)throws IOException{
        Request es=new Request("POST","/"+index+"/_search");es.setEntity(jsonEntity(objectMapper.writeValueAsString(vectorSearchBody(index,request))));
        return responseBody(restClient.performRequest(es));
    }
    Map<String,Object> vectorSearchBody(VectorSearchRequest request){return vectorSearchBody(null,request);}
    Map<String,Object> vectorSearchBody(String index,VectorSearchRequest request){
        if(request.getQueryVector()==null||request.getQueryVector().isEmpty())throw new IllegalArgumentException("queryVector must not be empty");
        String field=request.getEmbeddingField()==null||request.getEmbeddingField().isBlank()?DEFAULT_EMBEDDING_FIELD:request.getEmbeddingField();
        Map<String,Object> body=new LinkedHashMap<>();body.put("_source",Map.of("excludes",List.of(field)));
        body.put("track_total_hits",resolveTrackTotalHits(request.getTrackTotalHits()));Map<String,Object> knn=new LinkedHashMap<>();
        knn.put("field",field);knn.put("query_vector",request.getQueryVector());knn.put("k",positiveOrDefault(request.getK(),10,"k"));
        knn.put("num_candidates",positiveOrDefault(request.getNumCandidates(),100,"numCandidates"));
        if(request.getFilter()!=null&&!request.getFilter().isEmpty())knn.put("filter",request.getFilter());
        else if(documentIndexPolicy.isDocumentIndex(index))throw new IllegalArgumentException("document vector search requires protected ACL filter");
        body.put("knn",knn);return body;
    }

    String applyDefaultTrackTotalHits(String queryDsl){
        if(queryDsl==null||queryDsl.isBlank())throw new IllegalArgumentException("query DSL must not be blank");
        JsonNode root;try{root=objectMapper.readTree(queryDsl);}catch(IOException ex){throw new IllegalArgumentException("query DSL must be a valid JSON object",ex);}
        if(!(root instanceof ObjectNode body))throw new IllegalArgumentException("query DSL must be a JSON object");
        if(!body.hasNonNull("track_total_hits"))body.put("track_total_hits",properties.getTotalHitsThreshold());return body.toString();
    }
    int resolveTrackTotalHits(Integer requested){if(requested==null)return properties.getTotalHitsThreshold();if(requested<1)throw new IllegalArgumentException("trackTotalHits must be greater than 0");return requested;}
    private static int positiveOrDefault(Integer value,int fallback,String field){int resolved=value==null?fallback:value;if(resolved<=0)throw new IllegalArgumentException(field+" must be positive");return resolved;}

    private void deleteIndexIfExists(String index)throws IOException{Request head=new Request("HEAD","/"+index);try{Response response=restClient.performRequest(head);if(response.getStatusLine().getStatusCode()==404)return;}catch(ResponseException ex){if(ex.getResponse().getStatusLine().getStatusCode()==404)return;throw ex;}restClient.performRequest(new Request("DELETE","/"+index));}
    private String buildBulkBody(String index,String idField,List<Map<String,Object>> documents)throws IOException{if(documents==null||documents.isEmpty())throw new IllegalArgumentException("documents must not be empty");StringBuilder body=new StringBuilder();for(Map<String,Object> document:documents){Object id=idField==null||idField.isBlank()?null:document.get(idField);body.append("{\"index\":{\"_index\":\"").append(index).append("\"");if(id!=null)body.append(",\"_id\":").append(objectMapper.writeValueAsString(String.valueOf(id)));body.append("}}\n").append(objectMapper.writeValueAsString(document)).append("\n");}return body.toString();}
    private void validateDocumentChunkIfNeeded(String index,Map<String,Object> document){if(documentIndexPolicy.isDocumentIndex(index))chunkSchemaValidator.validate(index,document);}
    private HttpEntity jsonEntity(String json){return new NStringEntity(json,ContentType.APPLICATION_JSON);}
    private String responseBody(Response response)throws IOException{return new String(response.getEntity().getContent().readAllBytes(),StandardCharsets.UTF_8);}
}
