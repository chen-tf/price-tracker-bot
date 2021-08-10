CREATE TABLE public."user" (
	id varchar NOT NULL,
	chat_id varchar NOT NULL,
	create_time timestamp NOT NULL,
	update_time timestamp NOT NULL,
	CONSTRAINT user_pk PRIMARY KEY (id)
);

create trigger set_create_time_update_time before
insert
    on
    public."user" for each row execute function trigger_set_create_time_update_time();

create trigger set_update_time before
update
    on
    public."user" for each row execute function trigger_set_update_time();
