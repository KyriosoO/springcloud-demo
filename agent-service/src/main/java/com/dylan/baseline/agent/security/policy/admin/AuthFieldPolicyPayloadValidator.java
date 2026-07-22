package com.dylan.baseline.agent.security.policy.admin;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Pattern;

/** agent-field-policy-v0.1的封闭校验与规范化；仅支持ASCII标识符和集合数组。 */
public final class AuthFieldPolicyPayloadValidator {

    public static final String SCHEMA_VERSION = "agent-field-policy-v0.1";
    private static final int MAX_PAYLOAD_CHARS = 1_048_576;
    private static final Set<String> RULES = Set.of(
            "filterableFields", "displayableFields", "allowedOperators", "allowedFunctions");
    private static final Pattern TOKEN = Pattern.compile("[A-Za-z0-9_.:-]{1,128}");
    private final ObjectMapper objectMapper;

    public AuthFieldPolicyPayloadValidator(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public ValidatedPolicy validate(String schemaVersion, String payload) {
        if (!SCHEMA_VERSION.equals(schemaVersion)) {
            throw invalid("unsupported schemaVersion");
        }
        if (payload == null || payload.length() > MAX_PAYLOAD_CHARS) {
            throw invalid("policy payload is missing or exceeds 1048576 characters");
        }
        try {
            JsonNode root = objectMapper.readTree(payload);
            requireObject(root, "payload");
            requireExactFields(root, Set.of("fieldPolicies"), "payload");
            JsonNode policies = root.get("fieldPolicies");
            requireObject(policies, "fieldPolicies");
            if (policies.isEmpty()) {
                throw invalid("fieldPolicies must not be empty");
            }

            ObjectNode canonicalRoot = objectMapper.createObjectNode();
            ObjectNode canonicalPolicies = objectMapper.createObjectNode();
            Set<String> grants = new TreeSet<>();
            sortedFieldNames(policies).forEach(permissionCode -> {
                requireToken(permissionCode, "permissionCode");
                JsonNode rules = policies.get(permissionCode);
                requireObject(rules, "fieldPolicies." + permissionCode);
                requireExactFields(rules, RULES, "fieldPolicies." + permissionCode);
                ObjectNode canonicalRules = objectMapper.createObjectNode();
                RULES.stream().sorted().forEach(rule -> canonicalRules.set(
                        rule,
                        validateGrantMap(permissionCode, rule, rules.get(rule), grants)));
                canonicalPolicies.set(permissionCode, canonicalRules);
            });
            canonicalRoot.set("fieldPolicies", canonicalPolicies);
            String canonicalJson = objectMapper.writeValueAsString(canonicalRoot);
            return new ValidatedPolicy(canonicalJson, sha256(canonicalJson), Set.copyOf(grants));
        } catch (JsonProcessingException ex) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_PAYLOAD_INVALID", "policy payload is not valid JSON", ex);
        }
    }

    private ObjectNode validateGrantMap(
            String permissionCode, String rule, JsonNode node, Set<String> grants) {
        requireObject(node, permissionCode + "." + rule);
        ObjectNode canonical = objectMapper.createObjectNode();
        sortedFieldNames(node).forEach(key -> {
            requireToken(key, rule + " key");
            JsonNode values = node.get(key);
            if (!values.isArray() || values.isEmpty()) {
                throw invalid(rule + "." + key + " must be a non-empty array");
            }
            TreeSet<String> sorted = new TreeSet<>();
            values.forEach(value -> {
                if (!value.isTextual()) {
                    throw invalid(rule + "." + key + " values must be strings");
                }
                String token = value.textValue();
                requireToken(token, rule + " value");
                if (!sorted.add(token)) {
                    throw invalid(rule + "." + key + " contains duplicate values");
                }
                grants.add(permissionCode + "|" + rule + "|" + key + "|" + token);
            });
            ArrayNode array = objectMapper.createArrayNode();
            sorted.forEach(array::add);
            canonical.set(key, array);
        });
        return canonical;
    }

    private static void requireExactFields(JsonNode node, Set<String> expected, String path) {
        Set<String> actual = new HashSet<>();
        node.fieldNames().forEachRemaining(actual::add);
        if (!actual.equals(expected)) {
            throw invalid(path + " fields must be exactly " + expected);
        }
    }

    private static void requireObject(JsonNode node, String path) {
        if (node == null || !node.isObject()) {
            throw invalid(path + " must be an object");
        }
    }

    private static void requireToken(String value, String name) {
        if (value == null || !TOKEN.matcher(value).matches()) {
            throw invalid(name + " is not a stable ASCII identifier");
        }
    }

    private static List<String> sortedFieldNames(JsonNode node) {
        List<String> names = new ArrayList<>();
        Iterator<String> iterator = node.fieldNames();
        iterator.forEachRemaining(names::add);
        names.sort(String::compareTo);
        return names;
    }

    private static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            return java.util.HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 is unavailable", ex);
        }
    }

    private static PolicyAdministrationException invalid(String message) {
        return new PolicyAdministrationException("SECURITY_POLICY_PAYLOAD_INVALID", message);
    }

    public record ValidatedPolicy(String canonicalJson, String digest, Set<String> atomicGrants) {
    }
}
