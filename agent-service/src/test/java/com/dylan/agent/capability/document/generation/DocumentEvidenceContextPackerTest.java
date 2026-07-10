package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.AdapterDocumentEvidence;
import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.adapter.api.document.generation.DocumentContextBudget;
import com.dylan.agent.adapter.api.document.generation.DocumentEvidenceContextItem;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.DocumentCapabilityIds;
import com.dylan.agent.capability.document.ValidatedDocumentPlanTestSupport;
import com.dylan.agent.kernel.core.DocumentCapabilityHandlerTestSupport;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentEvidenceContextPackerTest {

    @Test
    void packsOnlyFilteredEvidenceWithinBudget() {
        AdapterDocumentEvidence evidence = new AdapterDocumentEvidence();
        evidence.setDocumentId("doc-1");
        evidence.setChunkId("c-1");
        evidence.setContent("员工年假需要直属主管审批。");
        evidence.setContextBefore(List.of("员工申请年假前需要提交申请。"));
        evidence.setContextAfter(List.of("审批通过后由人事归档。"));
        evidence.setRrfScore(new BigDecimal("0.03"));
        var request = new DocumentRetrievalRequest(
                DocumentPlanOperation.ANSWER,
                "policy_document",
                "年假审批",
                List.of(),
                List.of(),
                5,
                1,
                5,
                null,
                true);
        var plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.ANSWER,
                "policy_document",
                request);

        var packed = new DocumentEvidenceContextPacker().pack(new DocumentContextPackRequest(
                plan,
                List.of(evidence),
                DocumentCapabilityHandlerTestSupport.context(adapterRequest -> null),
                new DocumentContextBudget(100, 50, 5, 100)));

        assertThat(packed.citationIds()).containsExactly("c-1");
        assertThat(packed.evidenceItems()).singleElement()
                .extracting(DocumentEvidenceContextItem::text)
                .isEqualTo("员工申请年假前需要提交申请。\n员工年假需要直属主管审批。\n审批通过后由人事归档。");
        assertThat(packed.digest()).isNotBlank();
    }

    @Test
    void keepsOnlySafeMetadataForGenerationProvider() {
        AdapterDocumentEvidence evidence = new AdapterDocumentEvidence();
        evidence.setDocumentId("doc-1");
        evidence.setChunkId("c-1");
        evidence.setTitle("休假政策");
        evidence.setSection("年假");
        evidence.setPage(3);
        evidence.setChunkIndex(7);
        evidence.setSourceUri("https://docs.example/policy.pdf?token=secret#page=3");
        evidence.setContent("员工年假需要直属主管审批。");
        evidence.setMetadata(Map.of(
                "embedding", List.of(0.1, 0.2),
                "aclRef", "acl-1",
                "raw", "不应进入生成上下文"));
        var request = new DocumentRetrievalRequest(
                DocumentPlanOperation.ANSWER,
                "policy_document",
                "年假审批",
                List.of(),
                List.of(),
                5,
                1,
                5,
                null,
                true);
        var plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.ANSWER,
                "policy_document",
                request);

        var packed = new DocumentEvidenceContextPacker().pack(new DocumentContextPackRequest(
                plan,
                List.of(evidence),
                DocumentCapabilityHandlerTestSupport.context(adapterRequest -> null),
                new DocumentContextBudget(100, 50, 5, 100)));

        assertThat(packed.evidenceItems()).singleElement()
                .satisfies(item -> {
                    assertThat(item.metadata()).containsEntry("documentId", "doc-1");
                    assertThat(item.metadata()).containsEntry("sourceUri", "https://docs.example/policy.pdf");
                    assertThat(item.metadata()).doesNotContainKeys("embedding", "aclRef", "raw");
                    assertThat(item.metadata().get("sourceUri").toString()).doesNotContain("token", "#");
                });
    }

    @Test
    void usesGenerationTextBeforeLegacyContextWindow() {
        AdapterDocumentEvidence evidence = new AdapterDocumentEvidence();
        evidence.setDocumentId("doc-1");
        evidence.setChunkId("c-1");
        evidence.setContent("旧 chunk 正文。");
        evidence.setGenerationText("完整生成证据句子。");
        evidence.setContextBefore(List.of("上一句。"));
        evidence.setContextAfter(List.of("下一句。"));
        var request = new DocumentRetrievalRequest(
                DocumentPlanOperation.ANSWER,
                "policy_document",
                "年假审批",
                List.of(),
                List.of(),
                5,
                1,
                5,
                null,
                true);
        var plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.ANSWER,
                "policy_document",
                request);

        var packed = new DocumentEvidenceContextPacker().pack(new DocumentContextPackRequest(
                plan,
                List.of(evidence),
                DocumentCapabilityHandlerTestSupport.context(adapterRequest -> null),
                new DocumentContextBudget(100, 50, 5, 100)));

        assertThat(packed.evidenceItems()).singleElement()
                .extracting(DocumentEvidenceContextItem::text)
                .isEqualTo("完整生成证据句子。");
    }

    @Test
    void truncatesAtSentenceBoundaryWhenEvidenceTextExceedsBudget() {
        AdapterDocumentEvidence evidence = new AdapterDocumentEvidence();
        evidence.setDocumentId("doc-1");
        evidence.setChunkId("c-1");
        evidence.setGenerationText("第一句内容足够长用于通过边界阈值并保持完整表达不被截断同时说明税率适用范围并覆盖不同税种场景。第二句内容不应残缺进入上下文。第三句内容。");
        var request = new DocumentRetrievalRequest(
                DocumentPlanOperation.ANSWER,
                "policy_document",
                "年假审批",
                List.of(),
                List.of(),
                5,
                1,
                5,
                null,
                true);
        var plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.ANSWER,
                "policy_document",
                request);

        var packed = new DocumentEvidenceContextPacker().pack(new DocumentContextPackRequest(
                plan,
                List.of(evidence),
                DocumentCapabilityHandlerTestSupport.context(adapterRequest -> null),
                new DocumentContextBudget(100, 55, 5, 100)));

        assertThat(packed.evidenceItems()).singleElement()
                .extracting(DocumentEvidenceContextItem::text)
                .isEqualTo("第一句内容足够长用于通过边界阈值并保持完整表达不被截断同时说明税率适用范围并覆盖不同税种场景。");
    }
}
