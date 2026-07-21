package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentSchemaRefDto;
import com.dylan.esquery.service.EsIndexAliasService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.http.entity.ContentType;
import org.apache.http.nio.entity.NStringEntity;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestClient;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class DocumentIndexTargetResolverTest {
    private static final Instant NOW = Instant.parse("2026-07-14T00:00:00Z");
    private static final DocumentCorpusKeyDto KEY = new DocumentCorpusKeyDto("policy", "document");
    private static final DocumentSchemaRefDto SCHEMA =
            new DocumentSchemaRefDto("document", "3", "a".repeat(64));
    private static final String PHYSICAL = "agent-doc-policy-document-s3-build";

    @Test
    void resolvesOnlyFullyVerifiedManifestAndAttestation() throws Exception {
        Fixture fixture = new Fixture(manifest(SCHEMA));

        ResolvedIndexTargetRef resolved = fixture.resolver.resolve(KEY);

        assertThat(resolved.physicalIndex()).isEqualTo(PHYSICAL);
        assertThat(resolved.binding().manifestDigest()).isEqualTo("d".repeat(64));
        assertThat(resolved.validationReportRef()).isEqualTo("report-1");
    }

    @Test
    void rejectsSameVersionWithDifferentSchemaDigest() throws Exception {
        Fixture fixture = new Fixture(manifest(
                new DocumentSchemaRefDto("document", "3", "b".repeat(64))));

        assertThatThrownBy(() -> fixture.resolver.resolve(KEY))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("corpus/schema binding mismatch");
    }

    @Test
    void rejectsTamperedReleaseAttestationDigest() {
        assertThatThrownBy(() -> new DocumentReleaseAttestation(
                "report-1", "e".repeat(64), "d".repeat(64), NOW, "f".repeat(64)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("release attestation invalid");
    }

    private static DocumentPhysicalIndexManifest manifest(DocumentSchemaRefDto schema) {
        return new DocumentPhysicalIndexManifest(PHYSICAL, KEY, schema, "standard", "disabled",
                "char-window-v3", "snapshot:v1", "b".repeat(64), "task-1", 1, 1,
                "c".repeat(64), NOW, "d".repeat(64));
    }

    private static final class Fixture {
        final DocumentIndexTargetResolver resolver;

        Fixture(DocumentPhysicalIndexManifest manifest) throws Exception {
            DocumentCorpusCatalog catalog = new DocumentCorpusCatalog(List.of(new DocumentCorpusDefinition(
                    KEY, "agent-doc-policy-document-read", SCHEMA, "standard", "disabled",
                    "char-window-v3", "connector-v1", Set.of())));
            EsIndexAliasService aliases = mock(EsIndexAliasService.class);
            when(aliases.readCurrent("agent-doc-policy-document-read"))
                    .thenReturn(new EsIndexAliasService.AliasTargetView(
                            "agent-doc-policy-document-read", List.of(PHYSICAL)));
            RestClient client = mock(RestClient.class);
            Response response = mock(Response.class);
            when(response.getEntity()).thenReturn(new NStringEntity(meta(), ContentType.APPLICATION_JSON));
            when(client.performRequest(any(Request.class))).thenReturn(response);
            DocumentPhysicalIndexManifestService manifests = mock(DocumentPhysicalIndexManifestService.class);
            when(manifests.requireSealed(any(), any())).thenReturn(manifest);
            ReleaseAttestationTechnicalPort attestations = mock(ReleaseAttestationTechnicalPort.class);
            String attestationDigest = DocumentReleaseAttestation.canonicalDigest(
                    "report-1", "e".repeat(64), "d".repeat(64));
            when(attestations.read(PHYSICAL)).thenReturn(Optional.of(new DocumentReleaseAttestation(
                    "report-1", "e".repeat(64), "d".repeat(64), NOW, attestationDigest)));
            resolver = new DocumentIndexTargetResolver(catalog, aliases, client, new ObjectMapper(),
                    manifests, attestations, Clock.fixed(NOW, ZoneOffset.UTC));
        }

        private static String meta() {
            String attestationDigest = DocumentReleaseAttestation.canonicalDigest(
                    "report-1", "e".repeat(64), "d".repeat(64));
            return "{\"" + PHYSICAL + "\":{\"mappings\":{\"_meta\":{\"agent_document_manifest\":{" +
                    "\"sealed\":true,\"taskId\":\"task-1\",\"manifestDigest\":\"" + "d".repeat(64) +
                    "\",\"validationReportRef\":\"report-1\",\"attestationDigest\":\"" +
                    attestationDigest + "\"}}}}}";
        }
    }
}
