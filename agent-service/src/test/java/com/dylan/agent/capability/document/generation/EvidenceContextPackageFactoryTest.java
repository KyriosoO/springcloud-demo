package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.DocumentCapabilityIds;
import com.dylan.agent.capability.document.ValidatedDocumentPlanTestSupport;
import com.dylan.agent.kernel.core.DocumentCapabilityHandlerTestSupport;
import com.dylan.agent.kernel.core.ExecutionContext;
import com.dylan.agent.capability.document.ValidatedDocumentPlan;
import com.dylan.agent.capability.document.provider.security.*;
import com.dylan.agent.mask.*;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class EvidenceContextPackageFactoryTest {

    @Test
    void packsOnlyFilteredEvidenceWithinBudget() {
        AclBoundDocumentHit evidence = DocumentEvidenceTestFixtures.evidence(
                null, null, null, null, null, "员工年假需要直属主管审批。", null,
                List.of("员工申请年假前需要提交申请。"), List.of("审批通过后由人事归档。"), 0,
                new BigDecimal("0.03"));
        var request = ValidatedDocumentPlanTestSupport.request(
                DocumentPlanOperation.ANSWER, "policy_document", "年假审批", true);
        var plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.ANSWER,
                "policy_document",
                request);

        var context = DocumentCapabilityHandlerTestSupport.context((adapterRequest, operationContext) -> null);
        var decision = decision(plan, context, evidence);
        var projection = projector().project(
                List.of(evidence), new DocumentEvidencePackingLimit(100, 50, 5), decision,
                context.executionScope());
        var packed = new EvidenceContextPackageFactory().create(new EvidenceContextPackageRequest(
                plan,
                context,
                DocumentEvidenceTestFixtures.responseBinding(evidence, plan, context), decision), projection);

        assertThat(packed.citationIds()).containsExactly("C1");
        assertThat(packed.items()).singleElement()
                .extracting(GenerationEvidencePackageItem::outboundText)
                .isEqualTo("员工申请年假前需要提交申请。\n员工年假需要直属主管审批。\n审批通过后由人事归档。");
        assertThat(packed.canonicalDigest()).hasSize(64);
    }

    @Test
    void keepsOnlySafeMetadataForGenerationProvider() {
        AclBoundDocumentHit evidence = DocumentEvidenceTestFixtures.evidence(
                "休假政策", "年假", 3, "https://docs.example/policy.pdf?token=secret#page=3",
                null, "员工年假需要直属主管审批。", null, List.of(), List.of(), 7, null);
        var request = ValidatedDocumentPlanTestSupport.request(
                DocumentPlanOperation.ANSWER, "policy_document", "年假审批", true);
        var plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.ANSWER,
                "policy_document",
                request);

        var context = DocumentCapabilityHandlerTestSupport.context((adapterRequest, operationContext) -> null);
        var decision = decision(plan, context, evidence);
        var projection = projector().project(
                List.of(evidence), new DocumentEvidencePackingLimit(100, 50, 5), decision,
                context.executionScope());
        var packed = new EvidenceContextPackageFactory().create(new EvidenceContextPackageRequest(
                plan,
                context,
                DocumentEvidenceTestFixtures.responseBinding(evidence, plan, context), decision), projection);

        assertThat(packed.items()).singleElement()
                .satisfies(item -> {
                    assertThat(item.citationId()).isEqualTo("C1");
                    assertThat(item.outboundTitle()).isEqualTo("休假政策");
                    assertThat(item.outboundSection()).isEqualTo("年假");
                    assertThat(item.outboundPage()).isEqualTo(3);
                    assertThat(item.outboundText()).doesNotContain("doc-1", "acl-1", "token");
                });
    }

    @Test
    void usesGenerationTextWithoutRecombiningContextWindow() {
        AclBoundDocumentHit evidence = DocumentEvidenceTestFixtures.evidence(
                null, null, null, null, null, "旧 chunk 正文。", "完整生成证据句子。",
                List.of("上一句。"), List.of("下一句。"), 0, null);
        var request = ValidatedDocumentPlanTestSupport.request(
                DocumentPlanOperation.ANSWER, "policy_document", "年假审批", true);
        var plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.ANSWER,
                "policy_document",
                request);

        var context = DocumentCapabilityHandlerTestSupport.context((adapterRequest, operationContext) -> null);
        var decision = decision(plan, context, evidence);
        var projection = projector().project(
                List.of(evidence), new DocumentEvidencePackingLimit(100, 50, 5), decision,
                context.executionScope());
        var packed = new EvidenceContextPackageFactory().create(new EvidenceContextPackageRequest(
                plan,
                context,
                DocumentEvidenceTestFixtures.responseBinding(evidence, plan, context), decision), projection);

        assertThat(packed.items()).singleElement()
                .extracting(GenerationEvidencePackageItem::outboundText)
                .isEqualTo("完整生成证据句子。");
    }

    @Test
    void truncatesAtSentenceBoundaryWhenEvidenceTextExceedsBudget() {
        AclBoundDocumentHit evidence = DocumentEvidenceTestFixtures.evidence(
                null, null, null, null, null, null,
                "第一句内容足够长用于通过边界阈值并保持完整表达不被截断同时说明税率适用范围并覆盖不同税种场景。第二句内容不应残缺进入上下文。第三句内容。",
                List.of(), List.of(), 0, null);
        var request = ValidatedDocumentPlanTestSupport.request(
                DocumentPlanOperation.ANSWER, "policy_document", "年假审批", true);
        var plan = ValidatedDocumentPlanTestSupport.documentPlan(
                DocumentCapabilityIds.ANSWER,
                "policy_document",
                request);

        var context = DocumentCapabilityHandlerTestSupport.context((adapterRequest, operationContext) -> null);
        var decision = decision(plan, context, evidence);
        var projection = projector().project(
                List.of(evidence), new DocumentEvidencePackingLimit(100, 55, 5), decision,
                context.executionScope());
        var packed = new EvidenceContextPackageFactory().create(new EvidenceContextPackageRequest(
                plan,
                context,
                DocumentEvidenceTestFixtures.responseBinding(evidence, plan, context), decision), projection);

        assertThat(packed.items()).singleElement()
                .extracting(GenerationEvidencePackageItem::outboundText)
                .isEqualTo("第一句内容足够长用于通过边界阈值并保持完整表达不被截断同时说明税率适用范围并覆盖不同税种场景。");
    }

    private static DocumentGenerationEvidenceProjector projector() {
        return new DocumentGenerationEvidenceProjector(new DocumentProviderOutboundFieldProjector(
                new com.dylan.agent.metadata.result.ResultValueMaskingSupport(new FieldMaskerRegistry(List.of(
                        new NoneFieldMasker(), new IdCardFieldMasker(), new MobileFieldMasker(),
                        new EmailFieldMasker(), new AddressFieldMasker())))));
    }

    private static DocumentProviderOutboundPolicyDecision decision(
            ValidatedDocumentPlan plan,
            ExecutionContext context,
            AclBoundDocumentHit evidence) {
        List<com.dylan.agent.metadata.domain.port.CanonicalFieldRef> fields = new java.util.ArrayList<>();
        String domain = plan.selectedCorpus().domain();
        if (evidence.title() != null) fields.add(new com.dylan.agent.metadata.domain.port.CanonicalFieldRef(domain, "title"));
        if (evidence.section() != null) fields.add(new com.dylan.agent.metadata.domain.port.CanonicalFieldRef(domain, "section"));
        if (evidence.page() != null) fields.add(new com.dylan.agent.metadata.domain.port.CanonicalFieldRef(domain, "page"));
        fields.add(new com.dylan.agent.metadata.domain.port.CanonicalFieldRef(domain, "snippet"));
        var factory = new DocumentProviderOutboundPolicyDecisionFactory(
                new DocumentProviderOutboundPolicyCanonicalizer(),
                java.time.Clock.fixed(context.executionScope().recheckedAt().plusMillis(1), java.time.ZoneOffset.UTC));
        var result = factory.create(
                com.dylan.agent.adapter.api.operation.CapabilityOperationType.of("DOCUMENT_GENERATION"),
                context.executionScope(), plan.selectedCorpus(), plan.profile().generationPolicy(),
                new DocumentProviderIntendedFieldView(fields), plan.profile().profileProjectionDigest(),
                context.absoluteDeadline());
        return ((DocumentProviderOutboundPolicyAllowed) result).decision();
    }
}
