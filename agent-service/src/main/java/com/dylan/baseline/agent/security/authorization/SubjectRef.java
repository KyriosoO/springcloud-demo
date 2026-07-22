package com.dylan.baseline.agent.security.authorization;

/** Auth 已证明的稳定主体引用。 */
public record SubjectRef(String type, String id) {

    public SubjectRef {
        requireText(type, "type");
        requireText(id, "id");
    }

    private static void requireText(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
    }
}
