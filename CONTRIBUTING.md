# Contribuir a iaLogs

Las mejoras, errores reproducibles y documentación son bienvenidos. El código se distribuye bajo MIT.

1. Haz un fork y crea una rama para el cambio.
2. Sigue el arranque del README. No añadas `.env`, `.local`, claves, datos ni logs reales al commit.
3. Ejecuta las pruebas pertinentes: backend con PostgreSQL real, frontend con TypeScript/Vite y PHP con MySQL real. Los comandos están en el README y en `.github/workflows/ci.yml`.
4. Ejecuta `python3 scripts/check_public.py` y `git diff --check`.
5. Abre una pull request que explique el problema, el comportamiento resultante y las comprobaciones ejecutadas.

Los cambios del esquema deben incluir una migración. No sustituyas PostgreSQL por SQLite en las pruebas de integración ni presentes respuestas simuladas como comprobación del modelo real. Los adaptadores de entrada deben incluir pruebas de límites, reintentos y checkpoint.

No publiques mensajes privados, credenciales o logs de terceros en issues. Para fallos de seguridad, consulta [SECURITY.md](SECURITY.md).
