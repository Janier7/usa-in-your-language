create table private.admin_devices(session_id uuid primary key,user_id uuid not null references auth.users,device_key uuid not null,label text not null check(length(label)<=200),created_at timestamptz not null default now(),expires_at timestamptz not null default now()+interval '30 days',revoked_at timestamptz);
alter table private.admin_devices enable row level security;
revoke all on private.admin_devices from public,anon,authenticated;
create policy device_deny on private.admin_devices for all to authenticated using(false) with check(false);
create or replace function private.has_permission(permission text) returns boolean language sql stable security definer set search_path='' as $$
 select auth.uid() is not null and auth.jwt()->>'aal'='aal2' and exists(select 1 from private.admin_devices d join auth.sessions s on s.id=d.session_id and s.user_id=d.user_id where d.session_id::text=auth.jwt()->>'session_id' and d.user_id=auth.uid() and d.revoked_at is null and d.expires_at>now()) and exists(
 select 1 from private.account_roles r join auth.users u on u.id=r.user_id where r.user_id=auth.uid() and r.active and u.email_confirmed_at is not null and (r.role='primary' or (r.role='moderator' and permission in ('summary','listings','audit','verification')) or (r.role='support' and permission in ('summary','users')) or (r.role='finance' and permission in ('summary','finance'))));
$$;
create function private.account_security() returns jsonb language sql stable security definer set search_path='' as $$ select jsonb_build_object('role',r.role,'trusted',private.has_permission('summary'),'permissions',case r.role when 'primary' then '["summary","listings","users","finance","team","audit","verification"]'::jsonb when 'moderator' then '["summary","listings","audit","verification"]'::jsonb when 'support' then '["summary","users"]'::jsonb when 'finance' then '["summary","finance"]'::jsonb else '[]'::jsonb end) from private.account_roles r join auth.users u on u.id=r.user_id where r.user_id=auth.uid() and r.active and u.email_confirmed_at is not null $$;
create function public.account_security() returns jsonb language sql stable security invoker set search_path='' as $$select private.account_security()$$;
create function private.register_admin_device(device_key uuid,device_label text) returns void language plpgsql security definer set search_path='' as $$ declare sid uuid;begin
 if auth.uid() is null or (auth.jwt()->>'aal') is distinct from 'aal2' or not exists(select 1 from private.account_roles r join auth.users u on u.id=r.user_id where r.user_id=auth.uid() and r.active and u.email_confirmed_at is not null) then raise exception 'Se requiere autenticación de dos factores';end if;
 sid=(auth.jwt()->>'session_id')::uuid;
 if not exists(select 1 from auth.sessions where id=sid and user_id=auth.uid()) then raise exception 'Sesión no válida';end if;
 if exists(select 1 from private.admin_devices where session_id=sid and revoked_at is not null) then raise exception 'Esta sesión fue revocada. Cierra sesión y vuelve a entrar.';end if;
 insert into private.admin_devices(session_id,user_id,device_key,label) values(sid,auth.uid(),device_key,left(device_label,200)) on conflict(session_id) do update set expires_at=now()+interval '30 days',label=excluded.label;
 insert into public.platform_events(actor_id,id_target,action,details) values(auth.uid(),sid::text,'device:verified',left(device_label,200));
 end $$;
create function public.register_admin_device(device_key uuid,device_label text) returns void language sql security invoker set search_path='' as $$select private.register_admin_device(device_key,device_label)$$;
create function private.read_admin_devices() returns table(session_id uuid,label text,created_at timestamptz,expires_at timestamptz,revoked_at timestamptz,current_session boolean) language sql stable security definer set search_path='' as $$ select d.session_id,d.label,d.created_at,d.expires_at,d.revoked_at,d.session_id::text=auth.jwt()->>'session_id' from private.admin_devices d where d.user_id=auth.uid() and private.has_permission('summary') order by d.created_at desc $$;
create function public.read_admin_devices() returns table(session_id uuid,label text,created_at timestamptz,expires_at timestamptz,revoked_at timestamptz,current_session boolean) language sql stable security invoker set search_path='' as $$select * from private.read_admin_devices()$$;
create function private.revoke_admin_device(target_session uuid) returns void language plpgsql security definer set search_path='' as $$begin
 if not private.has_permission('summary') then raise exception 'Sin permiso';end if;
 update private.admin_devices set revoked_at=now() where session_id=target_session and user_id=auth.uid();
 insert into public.platform_events(actor_id,id_target,action,details) values(auth.uid(),target_session::text,'device:revoked','Acceso administrativo revocado');
 end $$;
create function public.revoke_admin_device(target_session uuid) returns void language sql security invoker set search_path='' as $$select private.revoke_admin_device(target_session)$$;
revoke all on function private.account_security(),public.account_security(),private.register_admin_device(uuid,text),public.register_admin_device(uuid,text),private.read_admin_devices(),public.read_admin_devices(),private.revoke_admin_device(uuid),public.revoke_admin_device(uuid) from public,anon;
grant execute on function private.account_security(),public.account_security(),private.register_admin_device(uuid,text),public.register_admin_device(uuid,text),private.read_admin_devices(),public.read_admin_devices(),private.revoke_admin_device(uuid),public.revoke_admin_device(uuid) to authenticated;
