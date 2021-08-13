ALTER TABLE public.good_info ADD stock_state int4 NULL DEFAULT 1;
COMMENT ON COLUMN public.good_info.stock_state IS '0: out of stock
1: in stock';
