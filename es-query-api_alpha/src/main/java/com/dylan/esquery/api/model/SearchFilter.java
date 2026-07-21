package com.dylan.esquery.api.model;

import java.util.List;

/**
 * 通用搜索过滤条件，描述字段、操作符、单值和多值条件。
 */
public class SearchFilter {
	private String field;
	private String operator;
	private String value;
	private List<String> values;

	public String getField() {
		return field;
	}

	public void setField(String field) {
		this.field = field;
	}

	public String getOperator() {
		return operator;
	}

	public void setOperator(String operator) {
		this.operator = operator;
	}

	public String getValue() {
		return value;
	}

	public void setValue(String value) {
		this.value = value;
	}

	public List<String> getValues() {
		return values;
	}

	public void setValues(List<String> values) {
		this.values = values;
	}
}
