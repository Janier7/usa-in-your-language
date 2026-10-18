# Conexión de cuentas y solicitudes a Supabase

Proyecto: usa-in-your-language. La web carga supabase-client.js con Supabase JS 2.118.0. La URL y la clave publishable son públicas por diseño; no hay claves secret ni service_role en el cliente. La versión exacta se conserva también en package.json y package-lock.json.

## Ya configurado

- Perfiles creados por trigger de Auth, idioma y verificación de correo sincronizados.
- Solicitudes privadas, decisión administrativa de solicitudes pendientes y catálogo público separado sin dirección exacta, correo ni campos legales.
- Historial y tabla privada de roles. Roles nunca se obtienen de user_metadata editable.
- RLS en todas las tablas; permisos explícitos y privilegios por columna para impedir que un usuario cambie su rol, propietario o estado.
- Pruebas SQL con usuarios ficticios y rollback; la base no conserva esos usuarios de prueba.

schema.sql es una instantánea reproducible del esquema inicial y sus cambios, no un archivo de migración CLI inventado. Los cambios remotos se aplicaron mediante migraciones de Supabase.

## Antes de probar el registro en línea

Publicar la web en HTTPS y configurar esa URL en Authentication > URL Configuration, Site URL y Redirect URLs. Configurar SMTP de prueba o autorizar destinatarios con el servicio de correo de Supabase; el correo predeterminado restringe destinatarios. Email/password está habilitado y la confirmación de correo es obligatoria. No se ha probado la entrega de un correo ni se ha enviado uno desde el agente.

La recuperación de contraseña necesita pantalla de retorno y está marcada como pendiente. No deshabilitar la confirmación de correo para probarla.

## Administrador principal

No se concede administración al registrarse con una dirección ni mediante un dato editable. Después de que el titular cree y confirme la cuenta janiermirabal@gmail.com, un operador de confianza comprobará su identidad en auth.users y asignará el rol primary a su UUID confirmado en private.account_roles. No se ha creado esa cuenta ni establecido una contraseña.

## Alcance y limitaciones

La web está conectada a Supabase para cuentas, solicitudes, aprobación, perfiles de clientes e historial. Finanzas y equipo todavía usan implementaciones locales y deben migrarse antes de habilitar esos apartados en línea. Si se abren en modo Supabase, el cliente indica que no están migrados y no recurre silenciosamente a datos locales.

La portada conserva promociones ficticias. El catálogo no tiene coordenadas verificadas ni filtros completos de distancia, seguro o familia. No hay archivos privados, membresías ni pagos conectados. No existe todavía una URL de hosting creada por este cambio.

Para conservar el piloto Python y SQLite, abrir http://127.0.0.1:8000/?backend=local. No se migran contraseñas o datos locales automáticamente a Supabase.

## Validación

Ejecutar supabase/test-rls.sql con una conexión administrativa de prueba. Se revierte la transacción completa. Cubre aislamiento de propietario, escalada vía metadata, publicación administrativa y prohibición de lectura privada por anon. Revisión de seguridad de Supabase sin lints al finalizar la configuración.
