package com.dylan.esquery.document;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.RestClient;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

/** Sealed manifest 的 absent→present one-time attestation 更新。 */
public final class EsReleaseAttestationTechnicalPort implements ReleaseAttestationTechnicalPort {
    private final RestClient client;
    private final ObjectMapper mapper;

    public EsReleaseAttestationTechnicalPort(RestClient client, ObjectMapper mapper) { this.client = client; this.mapper = mapper; }

    @Override
    public DocumentReleaseAttestation attach(AuthorizedReleaseAttestationCommand command) {
        if (!Instant.now().isBefore(command.deadline())) throw new IllegalStateException("release attestation deadline reached");
        try {
            JsonNode root = mapping(command.physicalIndex());
            JsonNode manifest = root.path("agent_document_manifest");
            if (!manifest.path("sealed").asBoolean(false)
                    || !command.manifestDigest().equals(manifest.path("manifestDigest").asText(null))) {
                throw new IllegalStateException("release attestation manifest binding mismatch");
            }
            Optional<DocumentReleaseAttestation> current = parse(manifest);
            String expectedDigest = digest("ATTEST-1", command.validationReportRef(), command.validationReportDigest(), command.manifestDigest());
            if (current.isPresent()) {
                if (!current.get().attestationDigest().equals(expectedDigest)) throw new IllegalStateException("release attestation already bound to another report");
                return current.get();
            }
            Instant now = Instant.now();
            DocumentReleaseAttestation attestation = new DocumentReleaseAttestation(command.validationReportRef(),
                    command.validationReportDigest(), command.manifestDigest(), now, expectedDigest);
            Map<String, Object> updated = new LinkedHashMap<>(mapper.convertValue(manifest, new TypeReference<>() { }));
            updated.put("validationReportRef", attestation.validationReportRef());
            updated.put("validationReportDigest", attestation.validationReportDigest());
            updated.put("attestedAt", attestation.attestedAt().toString());
            updated.put("attestationDigest", attestation.attestationDigest());
            Map<String, Object> build = mapper.convertValue(root.path("agent_document_build"), new TypeReference<>() { });
            Request request = new Request("PUT", "/" + command.physicalIndex() + "/_mapping");
            request.setJsonEntity(mapper.writeValueAsString(Map.of("_meta", Map.of(
                    "agent_document_build", build, "agent_document_manifest", Map.copyOf(updated)))));
            client.performRequest(request);
            return read(command.physicalIndex()).filter(value -> value.equals(attestation))
                    .orElseThrow(() -> new IllegalStateException("release attestation readback mismatch"));
        } catch (RuntimeException failure) {
            throw failure;
        } catch (Exception ex) {
            throw new IllegalStateException("release attestation update failed", ex);
        }
    }

    @Override
    public Optional<DocumentReleaseAttestation> read(String physicalIndex) {
        if (physicalIndex == null || !physicalIndex.startsWith("agent-doc-")) throw new IllegalArgumentException("document physical index invalid");
        try { return parse(mapping(physicalIndex).path("agent_document_manifest")); }
        catch (RuntimeException failure) { throw failure; }
        catch (Exception ex) { throw new IllegalStateException("release attestation read failed", ex); }
    }

    private JsonNode mapping(String physicalIndex) throws Exception {
        return mapper.readTree(client.performRequest(new Request("GET", "/" + physicalIndex + "/_mapping"))
                .getEntity().getContent()).path(physicalIndex).path("mappings").path("_meta");
    }
    private static Optional<DocumentReleaseAttestation> parse(JsonNode manifest) {
        String digest = manifest.path("attestationDigest").asText(null);
        if (digest == null || digest.isBlank()) return Optional.empty();
        return Optional.of(new DocumentReleaseAttestation(text(manifest, "validationReportRef"),
                text(manifest, "validationReportDigest"), text(manifest, "manifestDigest"),
                Instant.parse(text(manifest, "attestedAt")), digest));
    }
    private static String text(JsonNode node, String field) { String value = node.path(field).asText(null); if (value == null || value.isBlank()) throw new IllegalStateException("attestation field missing"); return value; }
    private static String digest(String... values) {
        try { MessageDigest digest = MessageDigest.getInstance("SHA-256"); for (String value : values) { byte[] bytes = value.getBytes(StandardCharsets.UTF_8); digest.update(ByteBuffer.allocate(4).putInt(bytes.length).array()); digest.update(bytes); } return HexFormat.of().formatHex(digest.digest()); }
        catch (Exception ex) { throw new IllegalStateException("SHA-256 unavailable", ex); }
    }
}
