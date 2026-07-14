package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentSchemaRefDto;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.jdbc.core.JdbcTemplate;
import com.dylan.esquery.service.EsIndexAliasService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.elasticsearch.client.RestClient;
import com.dylan.esquery.security.DocumentProtectedFilterCompiler;
import com.dylan.esquery.security.DocumentProtectedFilterGuard;
import com.dylan.esquery.document.search.DocumentChannelExecutorRegistry;
import com.dylan.esquery.document.search.DocumentHybridSearchUseCase;
import com.dylan.esquery.document.search.DocumentResultSelector;
import com.dylan.esquery.document.search.DocumentRrfMerger;
import com.dylan.esquery.document.search.DocumentContextWindowLoader;
import java.time.Clock;
import java.util.LinkedHashMap;
import com.dylan.esquery.service.DocumentChunkSchemaValidator;
import com.dylan.esquery.service.DocumentIndexDefinitionValidator;

@Configuration
@EnableConfigurationProperties({DocumentCorpusCatalogProperties.class, DocumentRebuildProperties.class})
public class DocumentCorpusConfiguration {
    @Bean DocumentCorpusCatalog documentCorpusCatalog(DocumentCorpusCatalogProperties properties) {
        return new DocumentCorpusCatalog(properties.getDefinitions().stream().map(entry -> new DocumentCorpusDefinition(
                new DocumentCorpusKeyDto(entry.getDomain(), entry.getMaterialType()), entry.getReadAlias(),
                new DocumentSchemaRefDto(entry.getSchemaName(), entry.getSchemaVersion(), entry.getSchemaDigest()),
                entry.getAnalyzerRef(), entry.getVectorPolicyRef(), entry.getChunkStrategyRef(), entry.getSourceConnectorId(),
                java.util.Set.copyOf(entry.getIndexedBusinessFields()))).toList());
    }
    @Bean DocumentIndexAccessGuard documentIndexAccessGuard(DocumentCorpusCatalog catalog) { return new DocumentIndexAccessGuard(catalog); }
    @Bean DocumentSearchAccessGuard documentSearchAccessGuard() { return new DocumentSearchAccessGuard(); }
    @Bean DocumentIndexTargetResolver documentIndexTargetResolver(
            DocumentCorpusCatalog catalog,
            EsIndexAliasService aliases,
            @Qualifier("documentRestClient") RestClient restClient,
            ObjectMapper objectMapper) {
        return new DocumentIndexTargetResolver(catalog, aliases, restClient, objectMapper);
    }
    @Bean DocumentRebuildTaskRepository documentRebuildTaskRepository(JdbcTemplate jdbc) { return new PersistentDocumentRebuildTaskRepository(jdbc); }
    @Bean DocumentIndexRebuildService documentIndexRebuildService(DocumentCorpusCatalog catalog, DocumentRebuildTaskRepository repository) { return new DocumentIndexRebuildService(catalog, repository); }
    @Bean DocumentSourceConnectorRegistry documentSourceConnectorRegistry(ObjectProvider<DocumentSourceConnector> connectors) {
        return new DocumentSourceConnectorRegistry(connectors.orderedStream().toList());
    }
    @Bean DocumentIndexDefinitionRegistry documentIndexDefinitionRegistry(DocumentCorpusCatalog catalog) {
        LinkedHashMap<DocumentSchemaRefDto, DocumentIndexDefinition> definitions = new LinkedHashMap<>();
        for (DocumentCorpusDefinition corpus : catalog.snapshot().definitions().values()) {
            DocumentIndexDefinition candidate = new DocumentIndexDefinition(corpus.schemaRef(), corpus.analyzerRef(),
                    null, null, corpus.indexedBusinessFields().stream().sorted()
                    .map(name -> new DocumentBusinessFieldDefinition(name, DocumentBusinessFieldDefinition.Type.KEYWORD)).toList());
            DocumentIndexDefinition previous = definitions.putIfAbsent(corpus.schemaRef(), candidate);
            if (previous != null && !previous.equals(candidate)) throw new IllegalArgumentException("document schema ref has conflicting definitions");
        }
        return new DocumentIndexDefinitionRegistry(definitions.values().stream().toList());
    }
    @Bean DocumentIndexDefinitionJsonFactory documentIndexDefinitionJsonFactory() { return new DocumentIndexDefinitionJsonFactory(); }
    @Bean DocumentChunkDocumentMapper documentChunkDocumentMapper() { return new DocumentChunkDocumentMapper(); }
    @Bean IndexBuildWriter indexBuildWriter(@Qualifier("documentRestClient") RestClient restClient, ObjectMapper objectMapper,
                                            DocumentIndexDefinitionJsonFactory definitions, DocumentChunkDocumentMapper chunks) {
        return new EsIndexBuildWriter(restClient, objectMapper, definitions, chunks);
    }
    @Bean DocumentPhysicalIndexManifestService documentPhysicalIndexManifestService(@Qualifier("documentRestClient") RestClient restClient, ObjectMapper objectMapper) {
        return new EsDocumentPhysicalIndexManifestService(restClient, objectMapper);
    }
    @Bean IndexTechnicalValidationPort indexTechnicalValidationPort(@Qualifier("documentRestClient") RestClient restClient, ObjectMapper objectMapper,
            DocumentCorpusCatalog catalog, DocumentIndexDefinitionRegistry schemas, DocumentIndexDefinitionValidator validator) {
        return new EsIndexTechnicalValidationPort(restClient, objectMapper, catalog, schemas, validator);
    }
    @Bean ReleaseAttestationTechnicalPort releaseAttestationTechnicalPort(@Qualifier("documentRestClient") RestClient restClient, ObjectMapper objectMapper) {
        return new EsReleaseAttestationTechnicalPort(restClient, objectMapper);
    }
    @Bean PhysicalIndexTechnicalPort physicalIndexTechnicalPort(@Qualifier("documentRestClient") RestClient restClient,
                                                                 ObjectMapper objectMapper, JdbcTemplate jdbc) {
        return new EsPhysicalIndexTechnicalPort(restClient, objectMapper, jdbc);
    }
    @Bean DocumentIndexEmbeddingPort documentIndexEmbeddingPort() {
        return (chunks, corpus, schema, deadline) -> { throw new DocumentRebuildFailure("INDEX_EMBEDDING_BINDING_UNAVAILABLE"); };
    }
    @Bean IndexBuildWorker indexBuildWorker(DocumentRebuildTaskRepository tasks, DocumentCorpusCatalog catalog,
            DocumentSourceConnectorRegistry connectors, DocumentIndexDefinitionRegistry schemas,
            DocumentIndexEmbeddingPort embeddings, DocumentChunkSchemaValidator chunkValidator,
            DocumentChunkDocumentMapper chunkMapper, IndexBuildWriter writer,
            DocumentPhysicalIndexManifestService manifests, IndexTechnicalValidationPort technicalValidation,
            DocumentRebuildProperties properties, Clock clock) {
        return new IndexBuildWorker(tasks, catalog, connectors, schemas,
                new DocumentNormalizer(properties.getMaxDocumentCodePoints()),
                new DocumentChunker(properties.getChunkWindowCodePoints(), properties.getChunkOverlapCodePoints()),
                embeddings, chunkValidator, chunkMapper, writer, manifests, technicalValidation,
                new DocumentRebuildWorkerPolicy(properties.getPageSize(), properties.getMaxBulkAttempts(),
                        properties.getLeaseDuration(), properties.getTaskTimeout()), clock);
    }
    @Bean IndexBuildWorkerScheduler indexBuildWorkerScheduler(IndexBuildWorker worker) { return new IndexBuildWorkerScheduler(worker); }
    @Bean DocumentProtectedFilterGuard documentProtectedFilterGuard() { return new DocumentProtectedFilterGuard(); }
    @Bean DocumentProtectedFilterCompiler documentProtectedFilterCompiler() { return new DocumentProtectedFilterCompiler(); }
    @Bean DocumentChannelExecutorRegistry documentChannelExecutorRegistry(
            @Qualifier("documentRestClient") RestClient restClient,ObjectMapper objectMapper,DocumentProtectedFilterCompiler compiler,Clock clock){
        return new DocumentChannelExecutorRegistry(restClient,objectMapper,compiler,clock);
    }
    @Bean DocumentHybridSearchUseCase documentHybridSearchUseCase(
            DocumentCorpusCatalog catalog,
            DocumentIndexTargetResolver targetResolver,
            DocumentProtectedFilterGuard guard,
            DocumentChannelExecutorRegistry executors,
            @Qualifier("documentRestClient") RestClient restClient,
            ObjectMapper objectMapper,
            Clock clock) {
        DocumentContextWindowLoader contextLoader = new DocumentContextWindowLoader(
                restClient, objectMapper, executors, clock);
        return new DocumentHybridSearchUseCase(catalog,targetResolver,guard,executors,
                new DocumentRrfMerger(),new DocumentResultSelector(),contextLoader,clock);
    }
}
