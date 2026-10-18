alter table public.business_directory add column family text not null default '';
create or replace function private.validate_application() returns trigger language plpgsql set search_path='' as $$
declare field text;begin
 if tg_op='INSERT' then
  if exists(select 1 from jsonb_object_keys(new.payload) k where k not in ('name','family','activity','customClassification','description','entity','legalName','registrationNumber','legalNotes','phone','email','street','city','state','zip','primaryLanguage','additionalLanguages')) then raise exception 'El formulario contiene campos no permitidos. No envíes datos de identidad personal.';end if;
  if not exists(select 1 from public.profiles where id=auth.uid() and verified) then raise exception 'Confirma tu correo antes de publicar';end if;
 end if;
 foreach field in array array['name','activity','description','entity','phone','email','street','city','state','zip','primaryLanguage'] loop
  if new.payload->>field is null or length(trim(new.payload->>field))=0 or length(new.payload->>field)>4000 then raise exception 'Completa el campo: %',field using errcode='22023';end if;
 end loop;
 if new.payload->>'entity'!='individual' and coalesce(trim(new.payload->>'legalName'),'')='' then raise exception 'Indica el nombre legal';end if;
 if new.payload->>'email' !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' then raise exception 'Correo de contacto inválido';end if;
 if new.payload->>'primaryLanguage' !~ '^[A-Za-z]{2,8}(-[A-Za-z0-9]{2,8})*$' then raise exception 'Idioma inválido';end if;
 if jsonb_array_length(new.payload->'additionalLanguages')>100 or exists(select 1 from jsonb_array_elements(new.payload->'additionalLanguages') v where jsonb_typeof(v)<>'string' or trim(v::text,'"') !~ '^[A-Za-z]{2,8}(-[A-Za-z0-9]{2,8})*$') then raise exception 'Idiomas adicionales inválidos';end if;
 new.updated_at=now();
 if tg_op='UPDATE' and new.status='approved' then new.activated_at=coalesce(old.activated_at,now());end if;
 return new;end $$;
create or replace function private.publish_application() returns trigger language plpgsql security definer set search_path='' as $$ begin
 insert into public.application_history(listing_id,actor_id,action,reason) values(new.id,auth.uid(),case when tg_op='INSERT' then 'submitted' else new.status end,new.reason);
 if new.status='approved' then insert into public.business_directory(id,name,family,activity,description,city,state,zip,phone,primary_language,additional_languages,activated_at)
 values(new.id,new.payload->>'name',coalesce(new.payload->>'family',''),new.payload->>'activity',new.payload->>'description',new.payload->>'city',new.payload->>'state',new.payload->>'zip',new.payload->>'phone',new.payload->>'primaryLanguage',new.payload->'additionalLanguages',new.activated_at);end if;return new;end $$;
update public.business_directory d set family=coalesce(b.payload->>'family','') from public.business_applications b where b.id=d.id;
alter table public.profiles add column last_name text not null default '' check(length(last_name)<=200),add column phone text not null default '' check(length(phone)<=40);
grant update(last_name,phone) on public.profiles to authenticated;
create function private.profile_contact_details() returns trigger language plpgsql security definer set search_path='' as $$begin update public.profiles set last_name=left(coalesce(new.raw_user_meta_data->>'last_name',''),200),phone=left(coalesce(new.raw_user_meta_data->>'phone',''),40) where id=new.id;return new;end $$;
revoke all on function private.profile_contact_details() from public,anon,authenticated;
create trigger signup_contact_details after insert on auth.users for each row execute function private.profile_contact_details();
