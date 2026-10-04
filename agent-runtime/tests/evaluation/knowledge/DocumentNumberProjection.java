package com.dylan.esquery.service;

import java.nio.charset.StandardCharsets;
import java.util.Objects;

import org.springframework.beans.factory.config.YamlPropertiesFactoryBean;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.MapConfigurationPropertySource;
import org.springframework.core.io.FileSystemResource;

import com.dylan.esquery.api.knowledge.KnowledgeSearchRequest;
import com.dylan.esquery.config.KnowledgeSearchProperties;
import com.dylan.esquery.config.KnowledgeSearchProperties.KnowledgeSearchProfile;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;

/** Offline inspector only. No application context, RestClient or server. */
public final class DocumentNumberProjection {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            throw new IllegalArgumentException("projection_arguments_invalid");
        }
        var mapper = new ObjectMapper().enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION)
                .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);
        byte[] input = System.in.readNBytes(65537);
        if (input.length == 0 || input.length > 65536) {
            throw new IllegalArgumentException("projection_input_invalid");
        }
        var rows = mapper.readTree(input);
        if (!rows.isArray() || rows.size() != 11) {
            throw new IllegalArgumentException("projection_input_invalid");
        }
        var yaml = new YamlPropertiesFactoryBean();
        yaml.setResources(new FileSystemResource(args[0]));
        var binder = new Binder(new MapConfigurationPropertySource(Objects.requireNonNull(yaml.getObject())));
        var service = new KnowledgeSearchService(null, mapper, new KnowledgeSearchProperties());
        for (var row : rows) {
            String domain = row.required("domain").asText();
            String profileId = switch (domain) {
                case "tax.policy" -> "tax-policy-v1";
                case "tax.law" -> "tax-law-v1";
                default -> throw new IllegalArgumentException("projection_domain_invalid");
            };
            var profile = binder.bind("es.query.knowledge.profiles." + profileId,
                    Bindable.of(KnowledgeSearchProfile.class)).get();
            if (!domain.equals(profile.getLogicalDomainId())) {
                throw new IllegalArgumentException("projection_profile_invalid");
            }
            var request = new KnowledgeSearchRequest(1, domain, profileId, "keyword",
                    row.required("question").asText(), null, 20);
            var output = mapper.createObjectNode();
            output.put("caseId", row.required("caseId").asText());
            output.put("domain", domain);
            output.set("request", mapper.valueToTree(service.buildSearchBody(request, profile)));
            System.out.write(mapper.writeValueAsString(output).getBytes(StandardCharsets.UTF_8));
            System.out.write(10);
        }
    }
}
