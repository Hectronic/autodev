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

## Flujo de exploracion

1. Verificar que el repositorio sea un proyecto Git y detectar el stack principal.
2. Inspeccionar la estructura, los módulos, la documentación y los tests disponibles.
3. Pedir al agente de IA que genere secciones Markdown separadas para resumen, stack, arquitectura, diseño, funcionalidad, tests y riesgos.
4. Ensamblar un `summary.md` y un `summary.html` standalone con navegación interna.
5. Mantener el flujo en modo de solo lectura: no crear ramas ni modificar archivos del proyecto.

## Reglas de reporte

- El HTML final debe ser autocontenido, legible y sin dependencias externas.
- Cada sección debe quedar persistida también como artefacto Markdown dentro de la sesión.
- El análisis de arquitectura y diseño es heurístico, por lo que debe dejar claras sus limitaciones cuando el repositorio sea grande o heterogéneo.
