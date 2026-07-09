alter table document_alias_operation_audit
    add column domain varchar(128) null,
    add column material_type varchar(128) null,
    add column profile_version varchar(128) null,
    add column index_version varchar(128) null;

create index idx_document_alias_operation_profile
    on document_alias_operation_audit (alias_name, domain, material_type, profile_version, index_version);
