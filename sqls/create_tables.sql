CREATE OR REPLACE FUNCTION public.trigger_set_create_time_update_time()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
begin
  NEW.create_time = NOW() at time zone 'utc' ;
  NEW.update_time = NOW() at time zone 'utc' ;
  RETURN NEW;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.trigger_set_update_time()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  NEW.update_time = NOW() at time zone 'utc' ;
  RETURN NEW;
END;
$function$
;

-- public.good_info definition

-- Drop table

-- DROP TABLE public.good_info;

CREATE TABLE public.good_info (
	id varchar NOT NULL,
	"name" varchar NULL,
	price int8 NOT NULL,
	create_time timestamp NOT NULL,
	update_time timestamp NOT NULL,
	checksum varchar NULL,
	stock_state int4 NULL DEFAULT 1, -- 0: out of stock¶1: in stock
	state int4 NULL DEFAULT 1,
	CONSTRAINT good_info_pk PRIMARY KEY (id)
);

-- Column comments

COMMENT ON COLUMN public.good_info.stock_state IS '0: out of stock
1: in stock';

-- Table Triggers

create trigger set_create_time_update_time before
insert
    on
    public.good_info for each row execute function trigger_set_create_time_update_time();
create trigger set_update_time before
update
    on
    public.good_info for each row execute function trigger_set_update_time();


-- public."user" definition

-- Drop table

-- DROP TABLE public."user";

CREATE TABLE public."user" (
	id varchar NOT NULL,
	chat_id varchar NOT NULL,
	create_time timestamp NOT NULL,
	update_time timestamp NOT NULL,
	state int4 NULL DEFAULT 1,
	line_notify_token varchar NULL,
	CONSTRAINT user_pk PRIMARY KEY (id)
);
CREATE INDEX user_state_enable_ix ON public."user" USING btree (id, chat_id) WHERE (state = 1);

-- Table Triggers

create trigger set_create_time_update_time before
insert
    on
    public."user" for each row execute function trigger_set_create_time_update_time();
create trigger set_update_time before
update
    on
    public."user" for each row execute function trigger_set_update_time();


-- public.user_sub_good definition

-- Drop table

-- DROP TABLE public.user_sub_good;

CREATE TABLE public.user_sub_good (
	id uuid NOT NULL,
	user_id varchar NOT NULL,
	good_id varchar NOT NULL,
	price int8 NOT NULL,
	create_time timestamp NOT NULL,
	update_time timestamp NOT NULL,
	is_notified bool NOT NULL,
	state int4 NULL DEFAULT 1, -- 0: disable¶1: enable
	CONSTRAINT user_sub_good_pk PRIMARY KEY (id),
	CONSTRAINT user_sub_good_un UNIQUE (user_id, good_id),
	CONSTRAINT user_sub_good_good_fk FOREIGN KEY (good_id) REFERENCES public.good_info(id),
	CONSTRAINT user_sub_good_user_fk FOREIGN KEY (user_id) REFERENCES public."user"(id)
);
CREATE INDEX good_info_state_enable_ix ON public.user_sub_good USING btree (good_id) WHERE (state = 1);
CREATE INDEX user_sub_good_good_id_idx ON public.user_sub_good USING btree (good_id, price);
CREATE INDEX user_sub_good_good_id_price_state_enable_ix ON public.user_sub_good USING btree (good_id, price) WHERE (state = 1);

-- Column comments

COMMENT ON COLUMN public.user_sub_good.state IS '0: disable
1: enable';

-- Table Triggers

create trigger set_create_time_update_time before
insert
    on
    public.user_sub_good for each row execute function trigger_set_create_time_update_time();
create trigger set_update_time before
update
    on
    public.user_sub_good for each row execute function trigger_set_update_time();
