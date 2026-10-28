# Seguridad

iaLogs es una primera versión de autohospedaje. Usa versiones actualizadas de Docker/PHP, conserva las claves en archivos privados y revisa los datos antes de enviarlos al modelo.

El arranque local publica servicios en `127.0.0.1`. MySQL, PostgreSQL y el Ollama en contenedor no publican puertos. Para acceso remoto hacen falta HTTPS, autenticación, restricciones de red y una revisión del despliegue. No publiques Ollama directamente en Internet.

El portal PHP es un espacio administrativo compartido, sin aislamiento de clientes. No hay anonimización automática, MFA, auditoría completa ni garantías de exactitud del diagnóstico. No se deben considerar sus recomendaciones como acciones ejecutadas o hechos comprobados.

Si encuentras una vulnerabilidad, utiliza la comunicación privada de vulnerabilidades de GitHub cuando esté habilitada. Si no lo está, abre un issue solicitando un canal privado, sin incluir la explotación, credenciales, información personal ni datos de clientes. No publiques secretos para demostrar un problema.

Si has compartido una clave o contraseña, sustitúyela y actualiza la configuración correspondiente. Ignorar un archivo en Git no elimina secretos que ya se hayan publicado en el historial.
