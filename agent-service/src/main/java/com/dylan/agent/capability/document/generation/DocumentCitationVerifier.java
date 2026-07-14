package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.provider.DocumentProviderFinishReason;
import com.dylan.agent.adapter.api.document.provider.DocumentUntrustedGenerationPayload;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.response.GroundingStatus;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Exact citation marker/ownership/unit coverage verifier；不修复Provider输出。 */
public final class DocumentCitationVerifier {
    private static final Pattern MARKER = Pattern.compile("\\[(C[1-9][0-9]{0,9})]");
    private static final Pattern MARKER_AT_END = Pattern.compile(".*\\[(C[1-9][0-9]{0,9})][。！？.!?]?\\s*$", Pattern.DOTALL);

    public CitationVerificationResult verify(DocumentUntrustedGenerationPayload payload, EvidenceContextPackage context) {
        if (context.citationIds().isEmpty()) return result(GroundingStatus.NO_EVIDENCE, 0, 0, "NO_EVIDENCE");
        if (payload == null || payload.operation() != context.operation()
                || payload.finishReason() != DocumentProviderFinishReason.COMPLETED) {
            return result(GroundingStatus.UNVERIFIED, 0, 0, "PAYLOAD_BINDING_INVALID");
        }
        List<String> units = visibleUnits(payload);
        if (units.isEmpty()) return result(GroundingStatus.UNVERIFIED, 0, 0, "VISIBLE_TEXT_EMPTY");
        LinkedHashSet<String> markerOrder = new LinkedHashSet<>();
        for (String unit : units) {
            if (!MARKER_AT_END.matcher(unit).matches()) return result(GroundingStatus.UNVERIFIED, 0, 0, "UNIT_CITATION_MISSING");
            Matcher matcher = MARKER.matcher(unit);
            boolean found = false;
            while (matcher.find()) { found = true; markerOrder.add(matcher.group(1)); }
            if (!found || containsMalformedMarker(unit)) return result(GroundingStatus.UNVERIFIED, 0, 0, "CITATION_SYNTAX_INVALID");
        }
        List<String> declared = payload.citedIds();
        if (declared.stream().anyMatch(value -> value == null || !value.matches("C[1-9][0-9]{0,9}"))
                || new LinkedHashSet<>(declared).size() != declared.size()
                || !declared.equals(List.copyOf(markerOrder))) {
            return result(GroundingStatus.UNVERIFIED, units.size(), markerOrder.size(), "CITATION_DECLARATION_MISMATCH");
        }
        Set<String> allowed = context.citationIds();
        if (!allowed.equals(Set.copyOf(markerOrder))) {
            return result(GroundingStatus.UNVERIFIED, units.size(), markerOrder.size(), "CITATION_OWNERSHIP_MISMATCH");
        }
        return result(GroundingStatus.VERIFIED, units.size(), markerOrder.size(), null);
    }

    public CitationVerificationResult verify(
            DocumentGeneratedTextCandidate candidate,
            EvidenceContextPackage context) {
        if (candidate == null || context == null
                || !candidate.evidencePackageDigest().equals(context.canonicalDigest())
                || !candidate.authorizationBindingDigest().equals(context.authorizationBindingDigest())
                || !candidate.resourceLimitReference().equals(context.resourceLimitReference())) {
            return result(GroundingStatus.UNVERIFIED, 0, 0, "CANDIDATE_BINDING_INVALID");
        }
        DocumentGeneratedContent content = candidate.content();
        return verify(new DocumentUntrustedGenerationPayload(
                candidate.operation(), content.answerText(), content.summaryText(),
                content.summaryBullets(), candidate.citedIds(), DocumentProviderFinishReason.COMPLETED), context);
    }

    private static List<String> visibleUnits(DocumentUntrustedGenerationPayload payload) {
        List<String> units = new ArrayList<>();
        if (payload.operation() == DocumentPlanOperation.ANSWER) {
            if (blank(payload.answerText()) || !blank(payload.summaryText()) || !payload.summaryBullets().isEmpty()) return List.of();
            addParagraphs(units, payload.answerText());
        } else if (payload.operation() == DocumentPlanOperation.SUMMARIZE) {
            if (!blank(payload.answerText()) || (blank(payload.summaryText()) && payload.summaryBullets().isEmpty())) return List.of();
            if (!blank(payload.summaryText())) addParagraphs(units, payload.summaryText());
            payload.summaryBullets().stream().filter(value -> !blank(value)).forEach(value -> units.add(value.strip()));
        } else return List.of();
        return List.copyOf(units);
    }
    private static void addParagraphs(List<String> target, String text) { for (String unit : text.split("(?:\\R\\s*){2,}|\\R")) if (!unit.isBlank()) target.add(unit.strip()); }
    private static boolean containsMalformedMarker(String unit) { return unit.contains("[C") && !unit.replaceAll("\\[C[1-9][0-9]{0,9}]", "").equals(unit.replaceAll("\\[[^]]*]", "")); }
    private static boolean blank(String value) { return value == null || value.isBlank(); }
    private static CitationVerificationResult result(GroundingStatus status, int units, int citations, String reason) { return new CitationVerificationResult(status, units, citations, reason); }
}
