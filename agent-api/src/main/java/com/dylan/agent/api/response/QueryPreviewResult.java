package com.dylan.agent.api.response;

import java.util.List;
import java.util.Map;

/** 查询预览结果，包含预览字段、样例行和总数估计。 */
public class QueryPreviewResult {

    private List<String> columns;
    private List<Map<String, Object>> sampleRows;
    private Long totalEstimate;
    private Boolean totalExact;
    private Integer previewSize;

    public QueryPreviewResult() {
    }

    public QueryPreviewResult(List<String> columns,
                              List<Map<String, Object>> sampleRows,
                              Long totalEstimate,
                              Boolean totalExact,
                              Integer previewSize) {
        this.columns = columns;
        this.sampleRows = sampleRows;
        this.totalEstimate = totalEstimate;
        this.totalExact = totalExact;
        this.previewSize = previewSize;
    }

    public List<String> getColumns() {
        return columns;
    }

    public void setColumns(List<String> columns) {
        this.columns = columns;
    }

    public List<Map<String, Object>> getSampleRows() {
        return sampleRows;
    }

    public void setSampleRows(List<Map<String, Object>> sampleRows) {
        this.sampleRows = sampleRows;
    }

    public Long getTotalEstimate() {
        return totalEstimate;
    }

    public void setTotalEstimate(Long totalEstimate) {
        this.totalEstimate = totalEstimate;
    }

    public Boolean isTotalExact() {
        return totalExact;
    }

    public void setTotalExact(Boolean totalExact) {
        this.totalExact = totalExact;
    }

    public Integer getPreviewSize() {
        return previewSize;
    }

    public void setPreviewSize(Integer previewSize) {
        this.previewSize = previewSize;
    }
}
