package com.dylan.esquery.api.model.document;

import com.dylan.esquery.api.model.DocumentSearchChannel;

import java.math.BigDecimal;

/** 可见的单 channel rank/score。 */
public record DocumentChannelRank(DocumentSearchChannel channel,int rank,BigDecimal score){
    public DocumentChannelRank{if(channel==null||rank<=0||score==null||score.signum()<0)throw new IllegalArgumentException("channel rank invalid");}
}
