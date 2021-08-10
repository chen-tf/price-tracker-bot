CREATE TABLE public.good_info (
	id varchar NOT NULL,
	"name" varchar NULL,
	price int8 NOT NULL,
	create_time timestamp NOT NULL,
	update_time timestamp NOT NULL,
	CONSTRAINT good_info_pk PRIMARY KEY (id)
);

create trigger set_create_time_update_time before
insert
    on
    public.good_info for each row execute function trigger_set_create_time_update_time();

create trigger set_update_time before
update
    on
    public.good_info for each row execute function trigger_set_update_time();