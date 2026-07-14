create table if not exists document_rebuild_task (
    task_id varchar(64) not null,
    index_name varchar(255) not null,
    target_index varchar(255) not null,
    type varchar(32) not null,
    status varchar(32) not null,
    total_indexed bigint not null default 0,
    last_cursor varchar(1024) null,
    error_message varchar(2048) null,
    validation_status varchar(32) null,
    validation_digest varchar(128) null,
    validated_at timestamp null,
    validation_message varchar(512) null,
    created_at timestamp not null,
    updated_at timestamp not null,
    primary key (task_id)
);

create index idx_document_rebuild_task_target_index
    on document_rebuild_task (target_index);

create index idx_document_rebuild_task_status_updated
    on document_rebuild_task (status, updated_at);
