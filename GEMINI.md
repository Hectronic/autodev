# autodev - Guía de Funcionamiento

Este documento describe los mandatos de diseño de `autodev`.

## Mandatos principales

1. **Identificación del proyecto**: el primer paso de cualquier ejecución debe detectar si el directorio es un repositorio Git y cuál es el stack principal.
2. **Prompts contextualizados**: cada fase debe incluir el tipo de proyecto y el test runner detectado.
3. **Seguridad vía Git**: los cambios se ejecutan en una rama aislada para mantener trazabilidad.
4. **Alcance de desarrollo**: la herramienta puede modificar código, tests y documentación si la instrucción del usuario lo requiere.

## Flujo estándar

1. Planificar la solución.
2. Desarrollar la funcionalidad.
3. Testear los cambios.
4. Validar el resultado final.
5. Registrar un reporte técnico con el estado de la ejecución.
