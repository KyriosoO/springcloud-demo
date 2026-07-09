package com.dylan.documentgeneration;

import com.dylan.agent.adapter.api.document.generation.CitationBinding;
import com.dylan.agent.adapter.api.document.generation.DocumentEvidenceContextItem;
import com.dylan.agent.adapter.api.document.generation.DocumentGenerationRequest;
import com.dylan.agent.adapter.api.document.generation.DocumentGenerationResult;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Component
public class DeepSeekDocumentGenerationClient {
    private static final Pattern CITATION_PATTERN = Pattern.compile("\\[([^\\]\\s]{1,120})]");

    private final RestClient restClient;
    private final DeepSeekGenerationProperties properties;
    private final ObjectMapper objectMapper;

    public DeepSeekDocumentGenerationClient(
            RestClient deepSeekRestClient,
            DeepSeekGenerationProperties properties,
            ObjectMapper objectMapper) {
        this.restClient = Objects.requireNonNull(deepSeekRestClient, "deepSeekRestClient must not be null");
        this.properties = Objects.requireNonNull(properties, "properties must not be null");
        this.objectMapper = Objects.requireNonNull(objectMapper, "objectMapper must not be null");
    }

    public DocumentGenerationResult generate(DocumentGenerationRequest request) {
        requireActiveDeadline(request.deadline());
        try {
            JsonNode response = restClient.post()
                    .uri("/v1/chat/completions")
                    .header(HttpHeaders.AUTHORIZATION, "Bearer " + properties.getApiKey())
                    .body(chatRequest(request))
                    .retrieve()
                    .body(JsonNode.class);
            String content = content(response);
            DocumentGenerationResult parsed = parseResult(content, request.operation());
            return sanitize(parsed, request);
        } catch (RestClientException | IllegalArgumentException ex) {
            throw new IllegalStateException("document generation provider call failed");
        }
    }

    private Map<String, Object> chatRequest(DocumentGenerationRequest request) {
        return Map.of(
                "model", safeModel(request),
                "temperature", 0.1,
                "response_format", Map.of("type", "json_object"),
                "messages", List.of(
                        Map.of("role", "system", "content", systemPrompt()),
                        Map.of("role", "user", "content", userPrompt(request))));
    }

    private String safeModel(DocumentGenerationRequest request) {
        if (request.model() != null && !request.model().isBlank()) {
            return request.model();
        }
        return properties.getModel();
    }

    private String systemPrompt() {
        return """
                You generate grounded document answers from supplied evidence only.
                Output JSON only, without Markdown. Use this schema:
                {
                  "answerText": string|null,
                  "summaryText": string|null,
                  "summaryBullets": string[]|null,
                  "citationBindings": [{"text": string, "citationIds": string[]}],
                  "finishReason": "stop"
                }
                Every factual sentence or bullet must include citation markers like [citationId].
                citationIds must come only from the supplied evidence ids.
                If evidence is insufficient, say so briefly and cite the closest available evidence.
                """;
    }

    private String userPrompt(DocumentGenerationRequest request) {
        StringBuilder builder = new StringBuilder();
        builder.append("operation: ").append(request.operation()).append('\n');
        builder.append("question: ").append(request.queryText()).append('\n');
        builder.append("maxOutputChars: ").append(request.maxOutputChars()).append('\n');
        builder.append("evidence:\n");
        List<DocumentEvidenceContextItem> items = request.contextPackage().evidenceItems() == null
                ? List.of()
                : request.contextPackage().evidenceItems();
        for (DocumentEvidenceContextItem item : items) {
            builder.append("[").append(item.citationId()).append("]\n");
            builder.append(item.text() == null ? "" : item.text()).append("\n\n");
        }
        return builder.toString();
    }

    private String content(JsonNode response) {
        if (response == null) {
            throw new IllegalArgumentException("empty DeepSeek response");
        }
        JsonNode content = response.path("choices").path(0).path("message").path("content");
        if (!content.isTextual() || content.asText().isBlank()) {
            throw new IllegalArgumentException("empty DeepSeek message content");
        }
        return content.asText();
    }

    private DocumentGenerationResult parseResult(String content, DocumentPlanOperation operation) {
        String json = stripCodeFence(content);
        try {
            DocumentGenerationResult result = objectMapper.readValue(json, DocumentGenerationResult.class);
            if (operation == DocumentPlanOperation.ANSWER && blank(result.answerText()) && !blank(result.summaryText())) {
                return new DocumentGenerationResult(
                        result.summaryText(),
                        null,
                        null,
                        result.citationBindings(),
                        result.finishReason());
            }
            return result;
        } catch (JsonProcessingException ex) {
            throw new IllegalArgumentException("DeepSeek content is not DocumentGenerationResult JSON");
        }
    }

    private DocumentGenerationResult sanitize(DocumentGenerationResult source, DocumentGenerationRequest request) {
        Set<String> allowed = request.contextPackage().citationIds() == null
                ? Set.of()
                : request.contextPackage().citationIds();
        String answerText = limit(source.answerText(), request.maxOutputChars());
        String summaryText = limit(source.summaryText(), request.maxOutputChars());
        List<String> summaryBullets = source.summaryBullets() == null ? null : source.summaryBullets().stream()
                .filter(value -> value != null && !value.isBlank())
                .map(value -> limit(value, request.maxOutputChars()))
                .toList();
        List<CitationBinding> bindings = sanitizeBindings(source.citationBindings(), allowed);
        if (bindings.isEmpty()) {
            bindings = deriveBindings(answerText, summaryText, summaryBullets, allowed);
        }
        return new DocumentGenerationResult(
                answerText,
                summaryText,
                summaryBullets,
                bindings,
                blank(source.finishReason()) ? "stop" : source.finishReason());
    }

    private List<CitationBinding> sanitizeBindings(List<CitationBinding> source, Set<String> allowed) {
        if (source == null || source.isEmpty() || allowed.isEmpty()) {
            return List.of();
        }
        List<CitationBinding> sanitized = new ArrayList<>();
        for (CitationBinding binding : source) {
            List<String> ids = binding.citationIds() == null ? List.of() : binding.citationIds().stream()
                    .filter(allowed::contains)
                    .distinct()
                    .toList();
            if (!ids.isEmpty()) {
                sanitized.add(new CitationBinding(binding.text(), ids));
            }
        }
        return sanitized;
    }

    private List<CitationBinding> deriveBindings(
            String answerText,
            String summaryText,
            List<String> summaryBullets,
            Set<String> allowed) {
        LinkedHashSet<String> ids = new LinkedHashSet<>();
        collectCitationIds(answerText, allowed, ids);
        collectCitationIds(summaryText, allowed, ids);
        if (summaryBullets != null) {
            summaryBullets.forEach(value -> collectCitationIds(value, allowed, ids));
        }
        if (ids.isEmpty()) {
            return List.of();
        }
        String text = !blank(answerText) ? answerText : summaryText;
        if (blank(text) && summaryBullets != null && !summaryBullets.isEmpty()) {
            text = summaryBullets.get(0);
        }
        return List.of(new CitationBinding(limit(text, 500), List.copyOf(ids)));
    }

    private void collectCitationIds(String text, Set<String> allowed, Set<String> target) {
        if (text == null || allowed.isEmpty()) {
            return;
        }
        Matcher matcher = CITATION_PATTERN.matcher(text);
        while (matcher.find()) {
            String id = matcher.group(1);
            if (allowed.contains(id)) {
                target.add(id);
            }
        }
    }

    private static String stripCodeFence(String content) {
        String value = content.trim();
        if (value.startsWith("```")) {
            int firstNewline = value.indexOf('\n');
            int lastFence = value.lastIndexOf("```");
            if (firstNewline >= 0 && lastFence > firstNewline) {
                value = value.substring(firstNewline + 1, lastFence).trim();
            }
        }
        return value;
    }

    private static String limit(String value, int maxChars) {
        if (value == null) {
            return null;
        }
        int limit = maxChars <= 0 ? 2000 : maxChars;
        return value.length() <= limit ? value : value.substring(0, limit);
    }

    private static boolean blank(String value) {
        return value == null || value.isBlank();
    }

    private static void requireActiveDeadline(Instant deadline) {
        if (deadline == null || !deadline.isAfter(Instant.now())) {
            throw new IllegalArgumentException("document generation deadline expired");
        }
    }
}
