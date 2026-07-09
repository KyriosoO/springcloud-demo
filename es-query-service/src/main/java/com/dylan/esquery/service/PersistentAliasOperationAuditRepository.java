package com.dylan.esquery.service;

import org.springframework.stereotype.Repository;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/** 使用数据库持久化 alias 操作审计和回滚历史，避免服务重启后丢失回滚白名单。 */
@Repository
public class PersistentAliasOperationAuditRepository implements AliasOperationAuditRepository {

	private final DataSource dataSource;

	public PersistentAliasOperationAuditRepository(DataSource dataSource) {
		this.dataSource = dataSource;
	}

	@Override
	public void record(AliasOperationAudit audit) {
		if (audit.fromIndexes() == null || audit.fromIndexes().isEmpty()) {
			insert(audit, null);
			return;
		}
		for (String fromIndex : audit.fromIndexes()) {
			insert(audit, fromIndex);
		}
	}

	@Override
	public List<AliasOperationAudit> findAll() {
		List<AliasOperationAudit> audits = new ArrayList<>();
		try (Connection connection = dataSource.getConnection();
				PreparedStatement ps = connection.prepareStatement("""
						select alias_name, operation, from_index, to_index, task_id_prefix,
						       domain, material_type, profile_version, index_version,
						       gold_set_version, validation_report_id_prefix,
						       validation_digest_prefix, operator_ref_hash, result,
						       failure_reason, duration_ms, created_at
						from document_alias_operation_audit
						order by id
						""");
				ResultSet rs = ps.executeQuery()) {
			while (rs.next()) {
				audits.add(map(rs));
			}
			return audits;
		} catch (SQLException ex) {
			throw new IllegalStateException("Failed to query alias operation audits", ex);
		}
	}

	@Override
	public boolean hasTrustedTarget(String alias, String targetIndex) {
		try (Connection connection = dataSource.getConnection();
				PreparedStatement ps = connection.prepareStatement("""
						select 1
						from document_alias_operation_audit
						where alias_name = ?
						  and result in ('SUCCESS', 'IDEMPOTENT')
						  and (from_index = ? or to_index = ?)
						limit 1
						""")) {
			ps.setString(1, alias);
			ps.setString(2, targetIndex);
			ps.setString(3, targetIndex);
			try (ResultSet rs = ps.executeQuery()) {
				return rs.next();
			}
		} catch (SQLException ex) {
			throw new IllegalStateException("Failed to query trusted alias target", ex);
		}
	}

	private void insert(AliasOperationAudit audit, String fromIndex) {
		try (Connection connection = dataSource.getConnection();
				PreparedStatement ps = connection.prepareStatement("""
						insert into document_alias_operation_audit
						(alias_name, operation, from_index, to_index, domain, material_type,
						 profile_version, index_version, gold_set_version, validation_report_id_prefix,
						 task_id_prefix, validation_digest_prefix, operator_ref_hash, result,
						 failure_reason, duration_ms, created_at)
						values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
						""")) {
			ps.setString(1, audit.alias());
			ps.setString(2, audit.operation());
			ps.setString(3, fromIndex);
			ps.setString(4, audit.toIndex());
			ps.setString(5, audit.domain());
			ps.setString(6, audit.materialType());
			ps.setString(7, audit.profileVersion());
			ps.setString(8, audit.indexVersion());
			ps.setString(9, audit.goldSetVersion());
			ps.setString(10, audit.validationReportIdPrefix());
			ps.setString(11, audit.taskIdPrefix());
			ps.setString(12, audit.digestPrefix());
			ps.setString(13, audit.operatorRefHash());
			ps.setString(14, audit.result());
			ps.setString(15, audit.failureReason());
			ps.setLong(16, audit.durationMs());
			ps.setTimestamp(17, timestamp(audit.createdAt()));
			ps.executeUpdate();
		} catch (SQLException ex) {
			throw new IllegalStateException("Failed to persist alias operation audit", ex);
		}
	}

	private AliasOperationAudit map(ResultSet rs) throws SQLException {
		String fromIndex = rs.getString("from_index");
		return new AliasOperationAudit(
				rs.getString("alias_name"),
				rs.getString("operation"),
				fromIndex == null ? List.of() : List.of(fromIndex),
				rs.getString("to_index"),
				rs.getString("domain"),
				rs.getString("material_type"),
				rs.getString("profile_version"),
				rs.getString("index_version"),
				rs.getString("gold_set_version"),
				rs.getString("validation_report_id_prefix"),
				rs.getString("task_id_prefix"),
				rs.getString("validation_digest_prefix"),
				rs.getString("operator_ref_hash"),
				rs.getString("result"),
				rs.getString("failure_reason"),
				rs.getLong("duration_ms"),
				instant(rs.getTimestamp("created_at")));
	}

	private static Timestamp timestamp(Instant instant) {
		return instant == null ? null : Timestamp.from(instant);
	}

	private static Instant instant(Timestamp timestamp) {
		return timestamp == null ? null : timestamp.toInstant();
	}
}
