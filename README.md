# Daeda_classification

## Ejecución local

Desde la raíz del proyecto, ejecuta `python server.py` y abre
`http://127.0.0.1:8000`. La interfaz debe servirse desde este backend para que
el inicio de sesión y los reportes usen la API; abrir el HTML como archivo no
activa la autenticación.

El registro público crea cuentas `user`. El rol `admin` no se puede elegir ni
obtener desde el formulario; los cambios de rol deben realizarlos operadores
con acceso confiable a la base de datos.

## Notas de seguridad

- Las cuentas existentes en `aquavigia.db` se conservan. Las contraseñas con el
  formato antiguo se actualizan a PBKDF2 con sal aleatoria después de un inicio
  de sesión válido, pero ese cambio no reemplaza la contraseña conocida: cada
  titular debe iniciar sesión y cambiarla desde **Cambiar contraseña**.
- El servidor se enlaza por defecto a `127.0.0.1` y solo publica las páginas de
  la aplicación y sus endpoints permitidos; no publiques este servidor HTTP
  directamente en Internet.
- Para un despliegue, usa un proxy HTTPS y configura
  `AQUAVIGIA_COOKIE_SECURE=1`. Protege también `aquavigia.db` y cualquier copia
  de respaldo con permisos de sistema operativo apropiados.