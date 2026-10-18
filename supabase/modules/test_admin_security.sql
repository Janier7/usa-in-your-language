begin;
do $$declare a uuid=gen_random_uuid();o uuid=gen_random_uuid();z uuid=gen_random_uuid();s uuid=gen_random_uuid();begin
 perform set_config('test.admin',a::text,true);perform set_config('test.owner',o::text,true);perform set_config('test.other',z::text,true);perform set_config('test.session',s::text,true);
 insert into auth.users(id,email,email_confirmed_at,raw_user_meta_data) values(a,a::text||'@example.invalid',now(),'{"name":"Test admin"}'),(o,o::text||'@example.invalid',now(),'{"name":"Test owner","role":"primary"}'),(z,z::text||'@example.invalid',now(),'{"name":"Test other"}');
 insert into private.account_roles(user_id,role,active) values(a,'primary',true);
 insert into auth.sessions(id,user_id,aal) values(s,a,'aal2');
end $$;
set local role authenticated;
select set_config('request.jwt.claims',json_build_object('sub',current_setting('test.admin'),'role','authenticated','aal','aal1','session_id',current_setting('test.session'))::text,true);
do $$begin if private.has_permission('team') then raise exception 'FAIL: aal1 permitted';end if;begin perform public.register_admin_device(gen_random_uuid(),'test');raise exception 'FAIL: device without MFA';exception when raise_exception then if sqlerrm like 'FAIL:%' then raise;end if;end;end $$;
select set_config('request.jwt.claims',json_build_object('sub',current_setting('test.admin'),'role','authenticated','aal','aal2','session_id',current_setting('test.session'))::text,true);
do $$begin if private.has_permission('team') then raise exception 'FAIL: unregistered session permitted';end if;end $$;
select public.register_admin_device(gen_random_uuid(),'Test browser');
do $$begin if not private.has_permission('team') then raise exception 'FAIL: verified admin denied';end if;perform public.manage_team(current_setting('test.owner')||'@example.invalid','Support','support',true);end $$;
select set_config('request.jwt.claims',json_build_object('sub',current_setting('test.owner'),'role','authenticated','aal','aal1')::text,true);
insert into public.support_tickets(subject,message) values('QA ticket','QA message');
insert into public.business_applications(payload) values('{"name":"QA business","family":"Automóviles","activity":"Grúas y remolque","description":"QA service","entity":"individual","phone":"1234567890","email":"qa@example.invalid","street":"Private street","city":"Test","state":"FL","zip":"34201","primaryLanguage":"es","additionalLanguages":[]}');
select set_config('test.listing',(select id::text from public.business_applications where payload->>'name'='QA business'),true);
update public.business_applications set status='approved' where id=current_setting('test.listing')::bigint;
do $$begin if exists(select 1 from public.business_applications where id=current_setting('test.listing')::bigint and status<>'pending') then raise exception 'FAIL: owner self-approved';end if;end $$;

do $$begin
 if private.has_permission('team') then raise exception 'FAIL: role escalation';end if;
 begin perform public.manage_team(current_setting('test.other')||'@example.invalid','Bad','finance',true);raise exception 'FAIL: team escalation';exception when raise_exception then if sqlerrm like 'FAIL:%' then raise;end if;end;
 begin insert into public.platform_ledger(entry_date,kind,category,amount_cents,description,request_key) values(current_date,'income','other',100,'unauthorized',gen_random_uuid());raise exception 'FAIL: ledger write';exception when insufficient_privilege or raise_exception then if sqlerrm like 'FAIL:%' then raise;end if;end;
 begin insert into public.business_applications(payload) values('{"name":"Test","activity":"Test","description":"Test","entity":"individual","phone":"1234567890","email":"qa@example.invalid","street":"Test","city":"Test","state":"FL","zip":"34201","primaryLanguage":"es","additionalLanguages":[],"ssn":"not-allowed"}');raise exception 'FAIL: sensitive key accepted';exception when raise_exception then if sqlerrm like 'FAIL:%' then raise;end if;end;
end $$;
select set_config('request.jwt.claims',json_build_object('sub',current_setting('test.other'),'role','authenticated','aal','aal1')::text,true);
do $$begin if exists(select 1 from public.support_tickets where subject='QA ticket') then raise exception 'FAIL: ticket leaked';end if;if exists(select 1 from public.platform_ledger) then raise exception 'FAIL: ledger leaked';end if;end $$;
select set_config('request.jwt.claims',json_build_object('sub',current_setting('test.admin'),'role','authenticated','aal','aal2','session_id',current_setting('test.session'))::text,true);
do $$begin if not exists(select 1 from public.support_tickets where subject='QA ticket') then raise exception 'FAIL: admin ticket denied';end if;begin perform public.manage_team(current_setting('test.admin')||'@example.invalid','Bad','support',false);raise exception 'FAIL: principal modified';exception when raise_exception then if sqlerrm like 'FAIL:%' then raise;end if;end;end $$;

update public.business_applications set status='approved' where id=current_setting('test.listing')::bigint;
insert into public.platform_ledger(entry_date,kind,category,amount_cents,description,listing_id,request_key) values(current_date,'income','membership',2500,'QA membership',current_setting('test.listing')::bigint,gen_random_uuid());
insert into public.promotions(listing_id,title,description,language,starts_at,ends_at,status) values(current_setting('test.listing')::bigint,'QA promotion','QA description','es',now()-interval '1 minute',now()+interval '1 day','published');
insert into public.business_verifications(listing_id,kind,reference) values(current_setting('test.listing')::bigint,'registration','QA public register');
do $$begin if not exists(select 1 from public.business_directory where id=current_setting('test.listing')::bigint and family='Automóviles') then raise exception 'FAIL: directory not published';end if;if not exists(select 1 from public.platform_ledger where description='QA membership' and activation_at is not null) then raise exception 'FAIL: ledger activation snapshot';end if;end $$;
select public.revoke_admin_device(current_setting('test.session')::uuid);
do $$begin if private.has_permission('team') then raise exception 'FAIL: revoked session permitted';end if;end $$;
set local role anon;
do $$begin if not exists(select 1 from public.promotions where title='QA promotion') then raise exception 'FAIL: public promotion absent';end if;perform count(*) from public.service_catalog;perform count(*) from public.promotions;begin perform count(*) from public.platform_ledger;raise exception 'FAIL: anon ledger';exception when insufficient_privilege then null;end;end $$;
rollback;
