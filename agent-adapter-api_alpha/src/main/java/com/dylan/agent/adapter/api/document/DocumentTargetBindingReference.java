package com.dylan.agent.adapter.api.document;
public record DocumentTargetBindingReference(String schemaVersion, String contentDigest, String manifestDigest, String attestationDigest) {
    public DocumentTargetBindingReference { if(schemaVersion==null||schemaVersion.isBlank()||!digest(contentDigest)||!digest(manifestDigest)||!digest(attestationDigest)) throw new IllegalArgumentException("target binding must be complete"); }
    /** 与治理层 ITB-1 共用的 exact target binding digest。 */
    public String canonicalDigest() {
        try {
            var digest = java.security.MessageDigest.getInstance("SHA-256");
            for (String value : java.util.List.of("ITB-1", schemaVersion, contentDigest, manifestDigest, attestationDigest)) {
                byte[] bytes = value.getBytes(java.nio.charset.StandardCharsets.UTF_8);
                digest.update(java.nio.ByteBuffer.allocate(Integer.BYTES).putInt(bytes.length).array());
                digest.update(bytes);
            }
            return java.util.HexFormat.of().formatHex(digest.digest());
        } catch (java.security.NoSuchAlgorithmException ex) {
            throw new IllegalStateException(ex);
        }
    }
    private static boolean digest(String value){return value!=null&&value.matches("[0-9a-f]{64}");}
}
