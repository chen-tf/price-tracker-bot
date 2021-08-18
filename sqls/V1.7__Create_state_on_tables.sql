ALTER TABLE public.user_sub_good ADD state int4 NULL DEFAULT 1;
COMMENT ON COLUMN public.user_sub_good.state IS '0: disable
1: enable';

ALTER TABLE public."user" ADD state int4 NULL DEFAULT 1;
COMMENT ON COLUMN public.user_sub_good.state IS '0: disable
1: enable';

ALTER TABLE public.good_info ADD state int4 NULL DEFAULT 1;
COMMENT ON COLUMN public.user_sub_good.state IS '0: disable
1: enable';