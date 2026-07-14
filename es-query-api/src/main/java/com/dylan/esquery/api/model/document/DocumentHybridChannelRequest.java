package com.dylan.esquery.api.model.document;

import com.dylan.esquery.api.model.DocumentSearchChannel;

/** 单 channel 的 frozen requiredness/weight/count。 */
public record DocumentHybridChannelRequest(
        DocumentSearchChannel channel,
        boolean required,
        int weight,
        int candidateCount) {
    public DocumentHybridChannelRequest {
        if(channel==null||weight<=0||candidateCount<=0)throw new IllegalArgumentException("document channel request invalid");
    }
}
