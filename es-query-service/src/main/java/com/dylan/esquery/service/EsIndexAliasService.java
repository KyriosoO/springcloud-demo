package com.dylan.esquery.service;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.http.entity.ContentType;
import org.apache.http.nio.entity.NStringEntity;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.ResponseException;
import org.elasticsearch.client.RestClient;
import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Qualifier;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.time.Instant;

/** 01 仅拥有 alias actual read 与一次 compare-and-switch 技术原语。 */
@Service
public final class EsIndexAliasService {
    private final RestClient restClient;
    private final ObjectMapper objectMapper;

    public EsIndexAliasService(@Qualifier("documentRestClient") RestClient restClient, ObjectMapper objectMapper) {
        this.restClient = restClient;
        this.objectMapper = objectMapper;
    }

    public AliasTargetView readCurrent(String alias) throws IOException {
        Request request = new Request("GET", "/_alias/" + alias);
        try {
            Response response = restClient.performRequest(request);
            JsonNode root = objectMapper.readTree(response.getEntity().getContent());
            List<String> indexes = new ArrayList<>();
            root.fieldNames().forEachRemaining(indexes::add);
            indexes.sort(String::compareTo);
            return new AliasTargetView(alias, indexes);
        } catch (ResponseException ex) {
            if (ex.getResponse().getStatusLine().getStatusCode() == 404) return new AliasTargetView(alias, List.of());
            throw ex;
        }
    }

    public AliasChangeResult compareAndSwitch(AuthorizedAliasChangeCommand command) throws IOException {
        AliasTargetView before = readCurrent(command.alias());
        if (before.targets().size() > 1) return AliasChangeResult.AMBIGUOUS;
        if (before.targets().equals(List.of(command.targetIndex()))) return AliasChangeResult.ALREADY_APPLIED;
        if (!before.targets().equals(command.expectedTargets())) return AliasChangeResult.CONFLICT;
        validateTargetBinding(command);
        List<Object> actions = new ArrayList<>();
        before.targets().forEach(index -> actions.add(Map.of("remove", Map.of("index", index, "alias", command.alias(), "must_exist", true))));
        actions.add(Map.of("add", Map.of("index", command.targetIndex(), "alias", command.alias())));
        Request request = new Request("POST", "/_aliases");
        request.setEntity(new NStringEntity(objectMapper.writeValueAsString(Map.of("actions", actions)), ContentType.APPLICATION_JSON));
        restClient.performRequest(request);
        AliasTargetView after = readCurrent(command.alias());
        if (after.targets().equals(List.of(command.targetIndex()))) return AliasChangeResult.APPLIED;
        if (after.targets().equals(before.targets())) return AliasChangeResult.CONFLICT;
        return AliasChangeResult.UNKNOWN;
    }

    private void validateTargetBinding(AuthorizedAliasChangeCommand command) throws IOException {
        JsonNode mapping = objectMapper.readTree(restClient.performRequest(new Request("GET", "/" + command.targetIndex() + "/_mapping"))
                .getEntity().getContent()).path(command.targetIndex()).path("mappings").path("_meta").path("agent_document_manifest");
        if (!mapping.path("sealed").asBoolean(false)
                || !command.corpusKey().domain().equals(mapping.path("domain").asText(null))
                || !command.corpusKey().materialType().equals(mapping.path("materialType").asText(null))
                || !command.manifestDigest().equals(mapping.path("manifestDigest").asText(null))
                || !command.validationReportRef().equals(mapping.path("validationReportRef").asText(null))
                || !command.attestationDigest().equals(mapping.path("attestationDigest").asText(null))) {
            throw new IllegalStateException("document alias target binding invalid");
        }
        JsonNode settings = objectMapper.readTree(restClient.performRequest(new Request("GET", "/" + command.targetIndex()
                + "/_settings?flat_settings=true")).getEntity().getContent());
        if (!"true".equals(settings.path(command.targetIndex()).path("settings").path("index.blocks.write").asText(null))) {
            throw new IllegalStateException("document alias target is not write blocked");
        }
    }

    public record AliasTargetView(String alias, List<String> targets) {
        public AliasTargetView { targets = List.copyOf(targets); }
    }
    public record AuthorizedAliasChangeCommand(
            String changeId, DocumentCorpusKeyDto corpusKey, String alias, List<String> expectedTargets,
            String targetIndex, String manifestDigest, String validationReportRef, String attestationDigest,
            String authorizationDigest, Instant deadline) {
        public AuthorizedAliasChangeCommand {
            if (changeId == null || changeId.isBlank() || corpusKey == null || alias == null || !alias.startsWith("agent-doc-")
                    || targetIndex == null || !targetIndex.startsWith("agent-doc-") || deadline == null || !Instant.now().isBefore(deadline)) {
                throw new IllegalArgumentException("invalid document alias change target");
            }
            expectedTargets = List.copyOf(expectedTargets == null ? List.of() : expectedTargets);
            if (expectedTargets.size() > 1 || expectedTargets.stream().anyMatch(value -> !value.startsWith("agent-doc-"))
                    || !digest(manifestDigest) || validationReportRef == null || validationReportRef.isBlank()
                    || !digest(attestationDigest) || !digest(authorizationDigest)) throw new IllegalArgumentException("invalid authorized alias change");
        }
        private static boolean digest(String value) { return value != null && value.matches("[0-9a-f]{64}"); }
    }
    public enum AliasChangeResult { APPLIED, ALREADY_APPLIED, CONFLICT, UNKNOWN, AMBIGUOUS }
}
