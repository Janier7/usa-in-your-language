begin;
select set_config('test.owner',gen_random_uuid()::text,true),set_config('test.other',gen_random_uuid()::text,true),set_config('test.admin',gen_random_uuid()::text,true);
insert into auth.users(id,aud,role,email,email_confirmed_at,raw_app_meta_data,raw_user_meta_data)
select current_setting('test.owner')::uuid,'authenticated','authenticated','rls-owner@example.invalid',now(),'{}'::jsonb,'{"name":"Owner","role":"primary","admin":true}'::jsonb union all
select current_setting('test.other')::uuid,'authenticated','authenticated','rls-other@example.invalid',now(),'{}'::jsonb,'{"name":"Other"}'::jsonb union all
select current_setting('test.admin')::uuid,'authenticated','authenticated','rls-admin@example.invalid',now(),'{}'::jsonb,'{"name":"Admin"}'::jsonb;
insert into private.account_roles(user_id,role) values(current_setting('test.admin')::uuid,'primary');
set local role authenticated;
select set_config('request.jwt.claims',json_build_object('sub',current_setting('test.owner'),'role','authenticated')::text,true);
do $$begin
 if cardinality(public.my_permissions())<>0 then raise exception 'editable metadata granted privileges';end if;
end$$;
insert into public.business_applications(payload) values('{"name":"RLS Test","activity":"Mariachi","description":"Test only","entity":"individual","phone":"555","email":"private@example.invalid","street":"PRIVATE","city":"Bradenton","state":"FL","zip":"34205","primaryLanguage":"es","additionalLanguages":["en"]}');
do $$begin
 begin update public.business_applications set status='approved'; if found then raise exception 'owner approved listing';end if;exception when insufficient_privilege then null;end;
 if (select count(*) from public.business_applications)<>1 then raise exception 'owner cannot read own listing';end if;
end$$;
select set_config('request.jwt.claims',json_build_object('sub',current_setting('test.other'),'role','authenticated')::text,true);
do $$begin if (select count(*) from public.business_applications)<>0 then raise exception 'private listing leaked';end if;
if (select count(*) from public.profiles)<>1 then raise exception 'profiles leaked';end if;end$$;
select set_config('request.jwt.claims',json_build_object('sub',current_setting('test.admin'),'role','authenticated')::text,true);
update public.business_applications set status='approved';
do $$begin if (select count(*) from public.business_directory)<>1 then raise exception 'publication failed';end if;end$$;
set local role anon;
do $$begin
 if (select count(*) from public.business_directory)<>1 then raise exception 'public directory unavailable';end if;
 begin perform * from public.business_applications;raise exception 'anon accessed private table';exception when insufficient_privilege then null;end;
end$$;
reset role;
select 'PASS: owner isolation, metadata escalation blocked, admin approval, public directory, anonymous access restrictions' as test_result;
rollback;
