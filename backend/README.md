# Prueba privada de cuentas y aprobación

Servidor Python 3.10+ sin dependencias externas. Esta es una implementación local para probar el flujo; no un servidor de producción. Solo escucha en 127.0.0.1. No utilizar datos ni documentos reales.

## Iniciar

Desde la raíz del repositorio:

```
python3 backend/server.py --create-admin
python3 backend/server.py --port 8000
```

El correo del administrador principal queda configurado como `janiermirabal@gmail.com`. El primer comando solicita nombre y contraseña sin mostrarla. Si la cuenta ya existe, requiere confirmación local antes de establecer sus credenciales administrativas y revoca sus sesiones anteriores. No existe una contraseña administrativa predeterminada ni un botón público que conceda permisos.

Abrir http://127.0.0.1:8000 y usar Menú > Crear cuenta. El servidor guarda el código de verificación de prueba en `.private-data/outbox/`; no envía un correo. Copiar el código en Verificar correo y entrar. Los códigos caducan en una hora y solo se usan una vez.

El propietario envía una solicitud en Publicar mi negocio. Administración entra con su propia cuenta, abre Administración > Solicitudes y aprueba o rechaza con motivo obligatorio. El propietario ve el estado y motivo en Mis negocios y solicitudes. El buscador consulta solo publicaciones aprobadas cuando hay servidor.

Las fotos y documentos, notificaciones por correo, recuperación de contraseña, edición y reenvío de solicitudes, membresías, traducción integral, clasificación exacta y geolocalización del catálogo aún no están conectados. La búsqueda real de esta prueba filtra texto e idiomas; no aplica todavía distancia, tamaño, seguro ni familia. Las promociones de portada siguen siendo ejemplos ficticios.

## Seguridad y datos

Contraseñas con scrypt y sal aleatoria; sesiones aleatorias con hash en SQLite; cookie HttpOnly y SameSite=Strict; protección CSRF; limitación de intentos; permisos administrativos comprobados en cada decisión; registro de auditoría. Datos de solicitudes no aprobadas solo visibles para propietario y administración. Dirección exacta, correo de contacto y campos legales no se exponen en el catálogo público.

La cookie local no usa Secure porque se sirve por HTTP en loopback. Una publicación real requiere HTTPS, cookies Secure, servidor de producción, base persistente administrada, limitación distribuida, correo real, copias de seguridad, monitoreo y revisión de seguridad. El estado de correo "verificado" en esta prueba no acredita propiedad del correo fuera de este entorno local.

Los datos se guardan en `.private-data/` (ignorados por Git). Para cambiar destino: variable USA_DATA_DIR. No servir esa carpeta mediante otro servidor web ni subirla al repositorio.

## Pruebas

```
python3 -m unittest discover -s tests -v
```

Cubre registro, bloqueo antes de verificar, código de un solo uso, sesión, CSRF, permisos de administración, privacidad de solicitudes, aprobación, rechazo con motivo, decisión duplicada, ocultación de dirección y correo públicos, bloqueo de archivos privados y cierre de sesión.


## Panel de Administración

Resumen de cuentas y negocios; solicitudes pendientes; listado de negocios con búsqueda y detalle; clientes con búsqueda; historial de solicitudes y decisiones; roles de equipo; registro manual de movimientos y estados de cuenta mensuales en USD con impresión y CSV. Los apartados de campañas, tickets, archivos y vencimientos se presentan explícitamente como pendientes; no simulan datos ni verificación.

Finanzas usa importes enteros en centavos y criterio de caja. Calcula saldo inicial, cobros de membresías por mes de activación del negocio (nuevo/anterior/desconocido), otros ingresos, salidas, ajustes y cierre. Un saldo inicial documentado se admite como primer movimiento. Los gastos admiten servidor, traducciones, comisiones, nómina, anuncios, seguros, legal, reembolsos, contracargos y otros. Los registros manuales no ejecutan pagos ni cobros. El estado interno no es un extracto bancario ni un cálculo de utilidad fiscal. No hay conciliación bancaria ni edición/anulación de movimientos todavía. Se requiere respaldar cada registro antes de utilizarlo fuera de pruebas.

El mes se agrupa por fechas ISO; las activaciones se interpretan en UTC. Los registros históricos sin fechas no reciben fechas inventadas. Los movimientos tienen claves idempotentes, registro de autor y eventos de auditoría.

Mi equipo admite cuentas existentes verificadas. Solo el correo principal configurado y autenticado como administrador puede asignar o retirar acceso. Roles: moderación (solicitudes, negocios, historial y verificación); soporte (resumen y clientes); finanzas (resumen y movimientos). Los permisos se comprueban en servidor en cada solicitud. Cambiar permisos revoca sesiones. El cargo laboral se guarda por separado del rol. No existen invitaciones por correo ni gestión de nómina todavía.

Las pruebas adicionales cubren permisos de cada rol, exclusividad del administrador principal, revocación de sesiones, clasificación de ingresos por mes de activación, arrastre de saldos, resultado mensual negativo con saldo final positivo, meses inválidos, precisión monetaria y movimientos duplicados.
