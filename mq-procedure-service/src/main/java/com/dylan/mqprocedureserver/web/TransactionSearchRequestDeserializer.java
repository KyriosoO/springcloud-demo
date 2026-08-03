package com.dylan.mqprocedureserver.web;

import java.io.IOException;
import java.math.BigDecimal;
import java.util.Arrays;
import java.util.Date;

import com.dylan.transaction.api.model.Transaction;
import com.dylan.transaction.api.query.TransactionSearchRequest;
import com.dylan.transaction.api.query.TransactionSearchSort;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.JsonToken;
import com.fasterxml.jackson.databind.DeserializationContext;
import com.fasterxml.jackson.databind.deser.std.StdDeserializer;

/** Keeps the existing DTO while rejecting quoted amount coercion for transaction.search. */
public final class TransactionSearchRequestDeserializer extends StdDeserializer<TransactionSearchRequest> {
	public TransactionSearchRequestDeserializer() {
		super(TransactionSearchRequest.class);
	}

	@Override
	public TransactionSearchRequest deserialize(JsonParser parser, DeserializationContext context) throws IOException {
		if (!parser.isExpectedStartObjectToken()) {
			return (TransactionSearchRequest) context.handleUnexpectedToken(
					TransactionSearchRequest.class, parser);
		}
		TransactionSearchRequest request = new TransactionSearchRequest();
		while (parser.nextToken() != JsonToken.END_OBJECT) {
			String field = parser.currentName();
			parser.nextToken();
			switch (field) {
				case "condition" -> request.setCondition(readCondition(parser, context));
				case "sorts" -> request.setSorts(readSorts(parser, context));
				case "page" -> request.setPage(parser.getValueAsInt());
				case "size" -> request.setSize(parser.getValueAsInt());
				default -> parser.skipChildren();
			}
		}
		return request;
	}

	private static Transaction readCondition(JsonParser parser, DeserializationContext context) throws IOException {
		if (parser.currentToken() == JsonToken.VALUE_NULL) {
			return null;
		}
		if (!parser.isExpectedStartObjectToken()) {
			return (Transaction) context.handleUnexpectedToken(Transaction.class, parser);
		}
		Transaction condition = new Transaction();
		while (parser.nextToken() != JsonToken.END_OBJECT) {
			String field = parser.currentName();
			parser.nextToken();
			switch (field) {
				case "transId" -> condition.setTransId(nullableText(parser, context, field));
				case "transType" -> condition.setTransType(nullableText(parser, context, field));
				case "transDate" -> condition.setTransDate(nullableDate(parser, context));
				case "amount" -> condition.setAmount(exactAmount(parser, context, field));
				case "transDateGt" -> condition.setTransDateGt(nullableDate(parser, context));
				case "transDateLt" -> condition.setTransDateLt(nullableDate(parser, context));
				case "amountGt" -> condition.setAmountGt(exactAmount(parser, context, field));
				case "amountLt" -> condition.setAmountLt(exactAmount(parser, context, field));
				case "transTypeContains" -> condition.setTransTypeContains(nullableText(parser, context, field));
				default -> parser.skipChildren();
			}
		}
		return condition;
	}

	private static java.util.List<TransactionSearchSort> readSorts(JsonParser parser,
			DeserializationContext context) throws IOException {
		if (parser.currentToken() == JsonToken.VALUE_NULL) {
			return null;
		}
		TransactionSearchSort[] sorts = context.readValue(parser, TransactionSearchSort[].class);
		return new java.util.ArrayList<>(Arrays.asList(sorts));
	}

	private static String nullableText(JsonParser parser, DeserializationContext context, String field)
			throws IOException {
		if (parser.currentToken() == JsonToken.VALUE_NULL) {
			return null;
		}
		if (parser.currentToken() != JsonToken.VALUE_STRING) {
			return (String) context.handleUnexpectedToken(String.class, parser);
		}
		return parser.getText();
	}

	private static Date nullableDate(JsonParser parser, DeserializationContext context) throws IOException {
		if (parser.currentToken() == JsonToken.VALUE_NULL) {
			return null;
		}
		return context.readValue(parser, Date.class);
	}

	private static BigDecimal exactAmount(JsonParser parser, DeserializationContext context, String field)
			throws IOException {
		if (parser.currentToken() == JsonToken.VALUE_NULL) {
			return null;
		}
		if (!parser.currentToken().isNumeric()) {
			context.reportInputMismatch(TransactionSearchRequest.class, "%s must be a JSON number", field);
		}
		return parser.getDecimalValue();
	}
}
