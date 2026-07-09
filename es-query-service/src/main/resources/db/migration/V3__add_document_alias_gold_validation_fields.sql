alter table document_alias_operation_audit
    add column gold_set_version varchar(128) null,
    add column validation_report_id_prefix varchar(64) null;

create index idx_document_alias_operation_gold
    on document_alias_operation_audit (alias_name, profile_version, gold_set_version, validation_report_id_prefix);
