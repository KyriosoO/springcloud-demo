package com.dylan.agent.capability.document.rewrite;

import com.dylan.agent.config.AgentProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatusCode;
import org.springframework.web.client.RestClient;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.time.Instant;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/** Runtime LLM 改写客户端，Runtime 输出只能作为不可信候选。 */
public final class RuntimeDocumentQueryRewriteClient implements DocumentQueryRewritePort {

    private static final List<String> FORBIDDEN_FIELDS = List.of(
            "dsl",
            "filter",
            "indexAlias",
            "retrievalProfile",
            "aclScope",
            "topK",
            "sort");

    private final RestClient restClient;
    private final ObjectMapper objectMapper;
    private final AgentProperties properties;

    public RuntimeDocumentQueryRewriteClient(
            RestClient restClient,
            ObjectMapper objectMapper,
            AgentProperties properties) {
        this.restClient = Objects.requireNonNull(restClient, "restClient must not be null");
        this.objectMapper = Objects.requireNonNull(objectMapper, "objectMapper must not be null");
        this.properties = Objects.requireNonNull(properties, "properties must not be null");
    }

    @Override
    public DocumentRewriteResponse rewrite(DocumentRewriteRequest request) {
        try {
            requireActiveDeadline(request.deadline());
            return restClient.post()
                    .uri(properties.getDocument().getRewrite().getPath())
                    .header("X-Agent-Runtime-Key", properties.getRuntime().getSharedKey())
                    .header("X-Agent-Request-Id", safeHeader(request.requestId()))
                    .body(body(request))
                    .exchange((httpRequest, response) -> {
                        byte[] responseBytes = readLimited(
                                response.getBody(),
                                properties.getRuntime().getMaxResponseBytes());
                        HttpStatusCode status = response.getStatusCode();
                        if (!status.is2xxSuccessful()) {
                            throw providerCallFailed();
                        }
                        JsonNode root = objectMapper.readTree(responseBytes);
                        if (containsForbiddenField(root)) {
                            throw new IllegalArgumentException("runtime rewrite response contains forbidden field");
                        }
                        DocumentRewriteResponse result = objectMapper.treeToValue(root, DocumentRewriteResponse.class);
                        return result == null ? new DocumentRewriteResponse(List.of(), null, null) : result;
                    });
        } catch (Exception ex) {
            throw providerCallFailed();
        }
    }

    private static Map<String, Object> body(DocumentRewriteRequest request) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("requestId", safeValue(request.requestId()));
        body.put("query", safeValue(request.query()));
        body.put("domain", safeValue(request.domain()));
        body.put("materialType", safeValue(request.materialType()));
        body.put("language", safeValue(request.language()));
        body.put("maxCandidates", request.maxCandidates());
        body.put("timeoutMs", request.timeoutMs());
        return body;
    }

    private static boolean containsForbiddenField(JsonNode node) {
        if (node == null) {
            return false;
        }
        if (node.isObject()) {
            Iterator<String> names = node.fieldNames();
            while (names.hasNext()) {
                String name = names.next();
                if (FORBIDDEN_FIELDS.stream().anyMatch(forbidden -> forbidden.equalsIgnoreCase(name))) {
                    return true;
                }
                if (containsForbiddenField(node.get(name))) {
                    return true;
                }
            }
        } else if (node.isArray()) {
            for (JsonNode child : node) {
                if (containsForbiddenField(child)) {
                    return true;
                }
            }
        }
        return false;
    }

    private static byte[] readLimited(InputStream input, int maxBytes) throws IOException {
        if (input == null) {
            return new byte[0];
        }
        try (input; ByteArrayOutputStream output = new ByteArrayOutputStream(Math.min(maxBytes, 8192))) {
            byte[] buffer = new byte[4096];
            int total = 0;
            int read;
            while ((read = input.read(buffer)) != -1) {
                total += read;
                if (total > maxBytes) {
                    throw providerCallFailed();
                }
                output.write(buffer, 0, read);
            }
            return output.toByteArray();
        }
    }

    private static void requireActiveDeadline(Instant deadline) {
        if (deadline == null || !deadline.isAfter(Instant.now())) {
            throw new IllegalArgumentException("document rewrite deadline expired");
        }
    }

    private static IllegalStateException providerCallFailed() {
        return new IllegalStateException("document rewrite provider call failed");
    }

    private static String safeValue(String value) {
        return value == null ? "" : value;
    }

    private static String safeHeader(String value) {
        return value == null || value.isBlank() ? "unknown" : value;
    }
}
