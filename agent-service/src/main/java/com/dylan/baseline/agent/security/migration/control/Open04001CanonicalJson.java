package com.dylan.baseline.agent.security.migration.control;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.TreeSet;

/** OPEN-04-001签名制品共享的受限canonical JSON实现。 */
final class Open04001CanonicalJson {

    private Open04001CanonicalJson() {
    }

    static byte[] canonical(ObjectMapper mapper, JsonNode node) {
        try {
            return mapper.writeValueAsBytes(canonicalNode(mapper, node));
        } catch (IOException ex) {
            throw new IllegalArgumentException("cannot canonicalize OPEN-04-001 JSON", ex);
        }
    }

    static byte[] canonicalWithout(ObjectMapper mapper, JsonNode node, String field) {
        if (!node.isObject()) {
            throw new IllegalArgumentException("canonical JSON root must be an object");
        }
        ObjectNode copy = node.deepCopy();
        copy.remove(field);
        return canonical(mapper, copy);
    }

    static String sha256(byte[] value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }

    private static JsonNode canonicalNode(ObjectMapper mapper, JsonNode node) {
        if (node.isObject()) {
            ObjectNode result = mapper.createObjectNode();
            TreeSet<String> names = new TreeSet<>();
            node.fieldNames().forEachRemaining(names::add);
            names.forEach(name -> result.set(name, canonicalNode(mapper, node.get(name))));
            return result;
        }
        if (node.isArray()) {
            ArrayNode result = mapper.createArrayNode();
            node.forEach(value -> result.add(canonicalNode(mapper, value)));
            return result;
        }
        if (!node.isTextual() && !node.isBoolean() && !node.isIntegralNumber() && !node.isNull()) {
            throw new IllegalArgumentException("canonical JSON contains an unsupported value type");
        }
        return node.deepCopy();
    }
}
