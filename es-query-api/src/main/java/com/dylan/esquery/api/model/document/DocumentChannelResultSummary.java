package com.dylan.esquery.api.model.document;

import com.dylan.esquery.api.model.DocumentSearchChannel;

/** channel closed outcome 的安全摘要。 */
public record DocumentChannelResultSummary(
        DocumentSearchChannel channel,
        Outcome outcome,
        int hitCount,
        String reasonCode) {
    public DocumentChannelResultSummary {
        if(channel==null||outcome==null||hitCount<0)throw new IllegalArgumentException("channel result invalid");
        if(outcome==Outcome.SUCCEEDED&&reasonCode!=null)throw new IllegalArgumentException("successful channel cannot have reason");
        if(outcome==Outcome.DEGRADED&&(reasonCode==null||reasonCode.isBlank()))throw new IllegalArgumentException("degraded reason required");
    }
    public enum Outcome { SUCCEEDED, DEGRADED }
}
