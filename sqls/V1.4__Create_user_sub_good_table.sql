CREATE TABLE public.user_sub_good (
	id uuid NOT NULL,
	user_id varchar NOT NULL,
	good_id varchar NOT NULL,
	price int8 NOT NULL,
	create_time timestamp NOT NULL,
	update_time timestamp NOT NULL,
	is_notified bool NOT NULL,
	CONSTRAINT user_sub_good_pk PRIMARY KEY (id),
	CONSTRAINT user_sub_good_un UNIQUE (user_id, good_id),
	CONSTRAINT user_sub_good_good_fk FOREIGN KEY (good_id) REFERENCES good_info(id),
	CONSTRAINT user_sub_good_user_fk FOREIGN KEY (user_id) REFERENCES "user"(id)
);
CREATE INDEX user_sub_good_good_id_idx ON public.user_sub_good USING btree (good_id, price);

create trigger set_create_time_update_time before
insert
    on
    public.user_sub_good for each row execute function trigger_set_create_time_update_time();

create trigger set_update_time before
update
    on
    public.user_sub_good for each row execute function trigger_set_update_time();