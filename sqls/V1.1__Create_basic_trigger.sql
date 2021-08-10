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