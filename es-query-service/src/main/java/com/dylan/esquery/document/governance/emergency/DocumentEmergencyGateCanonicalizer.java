package com.dylan.esquery.document.governance.emergency;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;

final class DocumentEmergencyGateCanonicalizer {
    private DocumentEmergencyGateCanonicalizer() {}

    static byte[] canonicalBytes(DocumentEmergencyGateEvidence evidence) {
        List<String> fields=new ArrayList<>();
        fields.add("EGE-1");
        fields.add(evidence.rolloutBinding().unitType());
        fields.add(evidence.rolloutBinding().unitKeyDigest());
        fields.add(evidence.rolloutBinding().expectedStateDigest());
        fields.add(evidence.rolloutBinding().targetStateDigest());
        fields.add(evidence.rolloutBinding().validationReportId());
        fields.add(Integer.toString(evidence.orderedTargets().size()));
        for(var target:evidence.orderedTargets()){
            fields.add(target.targetType().name());
            fields.add(target.targetKeyDigest());
        }
        fields.add(evidence.emergencyViewVersion());
        fields.add(evidence.status().name());
        fields.add(evidence.issuedAt().toString());
        fields.add(evidence.validUntil().toString());
        return lengthPrefixed(fields.toArray(String[]::new));
    }

    static DocumentEmergencyGateTargetBinding targetBinding(DocumentEmergencyTargetType type,String canonicalKey){
        return new DocumentEmergencyGateTargetBinding(type,sha256(lengthPrefixed("DET-1",type.name(),canonicalKey)));
    }

    static String canonicalDigest(byte[] bytes){return sha256(bytes);}
    static String evidenceId(String canonicalDigest){return sha256(lengthPrefixed("EGE-ID-1",canonicalDigest));}

    private static byte[] lengthPrefixed(String... values){
        try{
            ByteArrayOutputStream output=new ByteArrayOutputStream();
            for(String value:values){byte[] bytes=value.getBytes(StandardCharsets.UTF_8);output.write(ByteBuffer.allocate(4).putInt(bytes.length).array());output.write(bytes);}
            return output.toByteArray();
        }catch(java.io.IOException ex){throw new IllegalStateException(ex);}
    }
    private static String sha256(byte[] bytes){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}catch(Exception ex){throw new IllegalStateException(ex);}}
}
