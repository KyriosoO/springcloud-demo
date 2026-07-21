package com.dylan.esquery.document.search;

import com.dylan.esquery.api.model.document.DocumentChannelRank;

import java.math.BigDecimal;
import java.util.List;

/** RRF 后、document selection 前的内部稳定候选。 */
record FusedDocumentHit(
        BoundDocumentChannelHit representative,
        BigDecimal rrfScore,
        int bestRank,
        List<DocumentChannelRank> channelRanks) {
    FusedDocumentHit { channelRanks=List.copyOf(channelRanks); }
}
