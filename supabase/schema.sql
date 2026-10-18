create schema if not exists private;
revoke all on schema private from public, anon;
grant usage on schema private to authenticated;
create table private.account_roles (
 user_id uuid primary key references auth.users(id) on delete cascade,
 role text not null check(role in ('primary','moderator','support','finance')),
 active boolean not null default true,
 created_at timestamptz not null default now()
);
alter table private.account_roles enable row level security;
revoke all on private.account_roles from public,anon,authenticated;
create function private.has_permission(permission text) returns boolean
language sql stable security definer set search_path='' as $$
 select auth.uid() is not null and exists(
 select 1 from private.account_roles r join auth.users u on u.id=r.user_id
 where r.user_id=auth.uid() and r.active and u.email_confirmed_at is not null
 and (r.role='primary' or (r.role='moderator' and permission in ('summary','listings','audit','verification'))
 or (r.role='support' and permission in ('summary','users')) or (r.role='finance' and permission in ('summary','finance'))));
$$;
revoke all on function private.has_permission(text) from public,anon;
grant execute on function private.has_permission(text) to authenticated;
create table public.profiles(
 id uuid primary key references auth.users(id) on delete cascade,
 name text not null check(length(name) between 1 and 120),
 email text not null,
 language text not null default 'es' check(language ~ '^[A-Za-z]{2,8}(-[A-Za-z0-9]{2,8})*$'),
 created_at timestamptz not null default now()
);
alter table public.profiles enable row level security;
revoke all on public.profiles from public,anon,authenticated;
grant select on public.profiles to authenticated;
grant update(name,language) on public.profiles to authenticated;
create policy profiles_read on public.profiles for select to authenticated using(id=(select auth.uid()) or private.has_permission('users'));
create policy profiles_edit on public.profiles for update to authenticated using(id=(select auth.uid())) with check(id=(select auth.uid()));
create function private.create_profile() returns trigger language plpgsql security definer set search_path='' as $$
begin
 insert into public.profiles(id,name,email,language) values(new.id,left(coalesce(nullif(new.raw_user_meta_data->>'name',''),split_part(new.email,'@',1),'Usuario'),120),new.email,case when coalesce(new.raw_user_meta_data->>'language','') ~ '^[A-Za-z]{2,8}(-[A-Za-z0-9]{2,8})*$' then new.raw_user_meta_data->>'language' else 'es' end);
 return new;
end;$$;
revoke all on function private.create_profile() from public,anon,authenticated;
create trigger create_profile_after_signup after insert on auth.users for each row execute function private.create_profile();
create table public.business_applications(
 id bigint generated always as identity primary key,
 owner_id uuid not null default auth.uid() references auth.users(id),
 payload jsonb not null,
 status text not null default 'pending' check(status in ('pending','approved','rejected')),
 reason text not null default '' check(length(reason)<=4000),
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 activated_at timestamptz,
 check(jsonb_typeof(payload)='object'),
 check(length(payload->>'name') between 1 and 200),
 check(length(payload->>'description') between 1 and 4000),
 check(payload->>'entity' in ('individual','llc','corporation','partnership','lp','llp','nonprofit','cooperative','other')),
 check((payload->>'zip') ~ '^\d{5}(-\d{4})?$'),
 check(jsonb_typeof(payload->'additionalLanguages')='array'),
 check(status!='rejected' or length(trim(reason))>0)
);
create index business_applications_owner_idx on public.business_applications(owner_id);
create index business_applications_pending_idx on public.business_applications(status,created_at desc);
alter table public.business_applications enable row level security;
revoke all on public.business_applications from public,anon,authenticated;
grant select on public.business_applications to authenticated;
grant insert(payload) on public.business_applications to authenticated;
grant update(status,reason) on public.business_applications to authenticated;
grant usage,select on sequence public.business_applications_id_seq to authenticated;
create policy applications_read on public.business_applications for select to authenticated using(owner_id=(select auth.uid()) or private.has_permission('listings'));
create policy applications_create on public.business_applications for insert to authenticated with check(owner_id=(select auth.uid()) and status='pending' and reason='' and activated_at is null and coalesce((auth.jwt()->>'is_anonymous')::boolean,false)=false);
create policy applications_decide on public.business_applications for update to authenticated using(status='pending' and private.has_permission('listings')) with check(private.has_permission('listings') and status in ('approved','rejected'));
create table public.business_directory(
 id bigint primary key references public.business_applications(id) on delete cascade,
 name text not null,activity text not null,description text not null,
 city text not null,state text not null,zip text not null,phone text not null,
 primary_language text not null,additional_languages jsonb not null,
 activated_at timestamptz not null
);
alter table public.business_directory enable row level security;
revoke all on public.business_directory from public,anon,authenticated;
grant select on public.business_directory to anon,authenticated;
create policy directory_public on public.business_directory for select to anon,authenticated using(true);
create table public.application_history(
 id bigint generated always as identity primary key,
 listing_id bigint not null references public.business_applications(id),
 actor_id uuid references auth.users(id),
 action text not null,reason text not null default '',created_at timestamptz not null default now()
);
create index application_history_listing_idx on public.application_history(listing_id);
create index application_history_actor_idx on public.application_history(actor_id);
alter table public.application_history enable row level security;
revoke all on public.application_history from public,anon,authenticated;
grant select on public.application_history to authenticated;
create policy history_read on public.application_history for select to authenticated using(private.has_permission('audit') or exists(select 1 from public.business_applications b where b.id=listing_id and b.owner_id=(select auth.uid())));
create function private.validate_application() returns trigger language plpgsql set search_path='' as $$
declare field text;
begin
 foreach field in array array['name','activity','description','entity','phone','email','street','city','state','zip','primaryLanguage'] loop
  if new.payload->>field is null or length(trim(new.payload->>field))=0 or length(new.payload->>field)>4000 then raise exception 'Completa el campo: %',field using errcode='22023';end if;
 end loop;
 if new.payload->>'entity'!='individual' and coalesce(trim(new.payload->>'legalName'),'')='' then raise exception 'Indica el nombre legal';end if;
 if jsonb_array_length(new.payload->'additionalLanguages')>100 then raise exception 'Demasiados idiomas';end if;
 new.updated_at=now();
 if tg_op='UPDATE' and new.status='approved' then new.activated_at=coalesce(old.activated_at,now());end if;
 return new;
end;$$;
revoke all on function private.validate_application() from public,anon,authenticated;
create trigger validate_application before insert or update on public.business_applications for each row execute function private.validate_application();
create function private.publish_application() returns trigger language plpgsql security definer set search_path='' as $$
begin
 insert into public.application_history(listing_id,actor_id,action,reason) values(new.id,auth.uid(),case when tg_op='INSERT' then 'submitted' else new.status end,new.reason);
 if new.status='approved' then
 insert into public.business_directory(id,name,activity,description,city,state,zip,phone,primary_language,additional_languages,activated_at)
 values(new.id,new.payload->>'name',new.payload->>'activity',new.payload->>'description',new.payload->>'city',new.payload->>'state',new.payload->>'zip',new.payload->>'phone',new.payload->>'primaryLanguage',new.payload->'additionalLanguages',new.activated_at);
 end if;
 return new;
end;$$;
revoke all on function private.publish_application() from public,anon,authenticated;
create trigger publish_application after insert or update on public.business_applications for each row execute function private.publish_application();
create function public.my_permissions() returns text[] language sql stable security invoker set search_path='' as $$
 select coalesce(array_agg(p),array[]::text[]) from unnest(array['summary','listings','users','finance','team','audit','verification']) p where private.has_permission(p);
$$;
revoke all on function public.my_permissions() from public,anon;
grant execute on function public.my_permissions() to authenticated;
-- Subsequent hardening applied to the online project.
create policy roles_deny_direct_access on private.account_roles for all to authenticated using(false) with check(false);
alter table public.business_applications add constraint additional_languages_required check(payload ? 'additionalLanguages' and jsonb_typeof(payload->'additionalLanguages')='array');
alter table public.profiles add column verified boolean not null default false;
create function private.sync_email_verification() returns trigger language plpgsql security definer set search_path='' as $$ begin update public.profiles set verified=(new.email_confirmed_at is not null),email=new.email where id=new.id;return new;end;$$;
revoke all on function private.sync_email_verification() from public,anon,authenticated;
create trigger sync_email_verification after insert or update of email_confirmed_at,email on auth.users for each row execute function private.sync_email_verification();
update public.profiles p set verified=(u.email_confirmed_at is not null) from auth.users u where p.id=u.id;
alter table public.business_applications add constraint application_payload_size check(octet_length(payload::text)<=40000);
