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

    public CitationVerificationResult verify(DocumentUntrustedGenerationPayload payload, EvidenceContextPackage context) {
        if (context.citationIds().isEmpty()) return result(GroundingStatus.NO_EVIDENCE, 0, 0, "NO_EVIDENCE");
        if (payload == null || payload.operation() != context.operation()
                || payload.finishReason() != DocumentProviderFinishReason.COMPLETED) {
            return result(GroundingStatus.UNVERIFIED, 0, 0, "PAYLOAD_BINDING_INVALID");
        }
        return verifyVisible(payload, context.citationIds());
    }

    /** Result Security可用的纯本地复核；要求公开citation与可见marker完全相等。 */
    public CitationVerificationResult verifyVisible(
            DocumentPlanOperation operation,
            String answerText,
            String summaryText,
            List<String> summaryBullets,
            List<String> citedIds,
            Set<String> allowedIds) {
        try {
            return verifyVisible(new DocumentUntrustedGenerationPayload(
                    operation, answerText, summaryText, summaryBullets, citedIds,
                    DocumentProviderFinishReason.COMPLETED), allowedIds);
        } catch (RuntimeException ex) {
            return result(GroundingStatus.UNVERIFIED, 0, 0, "PAYLOAD_BINDING_INVALID");
        }
    }

    private CitationVerificationResult verifyVisible(
            DocumentUntrustedGenerationPayload payload,
            Set<String> allowed) {
        if (allowed.isEmpty()) return result(GroundingStatus.NO_EVIDENCE, 0, 0, "NO_EVIDENCE");
        List<String> units = visibleUnits(payload);
        if (units.isEmpty()) return result(GroundingStatus.UNVERIFIED, 0, 0, "VISIBLE_TEXT_EMPTY");
        LinkedHashSet<String> markerOrder = new LinkedHashSet<>();
        for (String unit : units) {
            Matcher matcher = MARKER.matcher(unit);
            boolean found = false;
            while (matcher.find()) {
                found = true;
                if (!validPositiveInt(matcher.group(1).substring(1))
                        || !markerAtAllowedBoundary(unit, matcher.start(), matcher.end())) {
                    return result(GroundingStatus.UNVERIFIED, 0, 0, "CITATION_POSITION_INVALID");
                }
                markerOrder.add(matcher.group(1));
            }
            if (!found || containsMalformedMarker(unit)) return result(GroundingStatus.UNVERIFIED, 0, 0, "CITATION_SYNTAX_INVALID");
        }
        List<String> declared = payload.citedIds();
        if (declared.stream().anyMatch(value -> value == null || !value.matches("C[1-9][0-9]{0,9}"))
                || new LinkedHashSet<>(declared).size() != declared.size()
                || !declared.equals(List.copyOf(markerOrder))) {
            return result(GroundingStatus.UNVERIFIED, units.size(), markerOrder.size(), "CITATION_DECLARATION_MISMATCH");
        }
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
    private static boolean markerAtAllowedBoundary(String unit, int start, int end) {
        if (insideBackticks(unit, start) || insideHtmlTag(unit, start) || insideUriToken(unit, start)) return false;
        if (start > 0) {
            char previous = unit.charAt(start - 1);
            if (isAsciiWord(previous) || "_-/@:#?=&%".indexOf(previous) >= 0) return false;
        }
        int next = end;
        while (next < unit.length() && Character.isWhitespace(unit.charAt(next))) next++;
        if (next == unit.length()) return true;
        char value = unit.charAt(next);
        return "。！？.!?;；".indexOf(value) >= 0
                || value == '[' && MARKER.matcher(unit.substring(next)).lookingAt();
    }
    private static boolean insideBackticks(String unit, int markerStart) {
        long count = unit.substring(0, markerStart).chars().filter(value -> value == '`').count();
        return (count & 1L) != 0L;
    }
    private static boolean insideHtmlTag(String unit, int markerStart) {
        String prefix = unit.substring(0, markerStart);
        return prefix.lastIndexOf('<') > prefix.lastIndexOf('>');
    }
    private static boolean insideUriToken(String unit, int markerStart) {
        int tokenStart = markerStart;
        while (tokenStart > 0 && !Character.isWhitespace(unit.charAt(tokenStart - 1))) tokenStart--;
        String token = unit.substring(tokenStart, markerStart).toLowerCase(java.util.Locale.ROOT);
        return token.contains("://") || token.startsWith("www.");
    }
    private static boolean isAsciiWord(char value) {
        return value >= 'a' && value <= 'z' || value >= 'A' && value <= 'Z'
                || value >= '0' && value <= '9';
    }
    private static boolean validPositiveInt(String value) {
        try { return Integer.parseInt(value) > 0; }
        catch (NumberFormatException ex) { return false; }
    }
    private static boolean containsMalformedMarker(String unit) {
        int start = unit.indexOf("[C");
        while (start >= 0) {
            Matcher matcher = MARKER.matcher(unit);
            matcher.region(start, unit.length());
            if (!matcher.lookingAt()) return true;
            start = unit.indexOf("[C", matcher.end());
        }
        return false;
    }
    private static boolean blank(String value) { return value == null || value.isBlank(); }
    private static CitationVerificationResult result(GroundingStatus status, int units, int citations, String reason) { return new CitationVerificationResult(status, units, citations, reason); }
}
