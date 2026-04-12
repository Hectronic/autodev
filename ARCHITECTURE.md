# Especificación Técnica: autodev

Este documento describe la arquitectura interna de `autodev`, una herramienta de desarrollo asistido por IA que encadena planificación, implementación, pruebas y validación sobre un repositorio Git.

## Arquitectura

### 1. Capa de interfaz

- Implementada con `click`.
- Expone el comando `-dev`.
- Expone el comando `-ut` para revisar cobertura de una rama respecto a su base.
- Expone el comando `-e` y el alias `--explain` para inspeccionar el repositorio y generar un informe tecnico standalone.
- Expone `push` para generar un commit automático a partir de los cambios locales y empujar la rama actual.
- Expone `history` para listar las 10 sesiones más recientes y, opcionalmente, inspeccionar el detalle de una sesión concreta.
- Recibe instrucciones de desarrollo como argumento posicional, además de ruta del proyecto y agente externo.
- Puede dejar los cambios solo preparados para revisión o hacer `commit` y `push` explícitos con `--push`.

### 2. Orquestador

- `AutoDevOrchestrator` coordina el flujo completo.
- Valida que el proyecto esté dentro de Git.
- Detecta el stack del proyecto.
- Crea una rama aislada para la ejecución o reanuda una sesión previa si la rama `autodev/*` ya tiene una sesión activa.
- Cuando la sesión es nueva, carga `README.md`, `GEMINI.md` y `AGENTS.md` si existen, y reserva una fase específica para documentación.
- En el modo `-ut`, resuelve la rama base, calcula el `merge-base`, analiza el diff y guía la revisión de cobertura por fases.
- En el modo `-ut`, también incorpora el estado pendiente del working tree para que la revisión cubra cambios staged, unstaged y archivos no trackeados.
- En el modo `-e`/`--explain`, analiza el repositorio sin modificarlo, pide al agente de IA que genere una sección Markdown por tema y compone un HTML standalone con navegación.
- En el modo `-e`/`--explain`, cada sección generada se persiste como entrada/salida individual dentro de la sesión para conservar trazabilidad completa.
- Genera logs, Markdown, HTML y metadatos en la carpeta de datos del usuario.

### 3. Clientes de IA

- `GeminiClient` ejecuta prompts con la CLI de Gemini.
- `CodexClient` ejecuta prompts con la CLI de Codex.
- Ambos preservan la continuidad de la sesión entre fases.

### 4. Git

- `GitManager` encapsula la validación de repositorio, creación de rama, generación de mensajes de commit y commit/push finales opcionales.

### 5. Persistencia local

- `HistoryManager` guarda sesiones, pasos, rama, estado y rutas de artefactos en SQLite.
- `RuntimeStore` resuelve la carpeta de datos, las rutas por sesión y el almacenamiento de artefactos.
- El resumen final se produce en Markdown y se convierte a HTML para apertura automática en navegador.

## Flujo de trabajo

Flujo `-dev`:
1. Identificación del proyecto.
2. Planificación de la solución.
3. Desarrollo de la funcionalidad.
4. Documentación de cambios y actualización de la documentación relevante.
5. Ejecución de pruebas.
6. Validación final y generación del reporte.

Flujo `-ut`:
1. Identificación del proyecto y de la rama actual.
2. Resolución de la rama base y del `merge-base`.
3. Recolección del diff confirmado y del estado pendiente del working tree.
4. Análisis del diff y de los casos afectados.
5. Revisión de cobertura y detección de gaps.
6. Remediación de gaps.
7. Validación final y generación del reporte.

Flujo `-e`:
1. Identificación del proyecto y verificación de que el directorio sea Git.
2. Captura de la estructura del repositorio, módulos, documentación y tests.
3. Elaboración de secciones Markdown para stack, arquitectura, diseño, funcionalidad, tests y riesgos.
4. Ensamblado de un `summary.md` y un `summary.html` standalone con índice interno.
5. Persistencia de artefactos y cierre de sesión.

## Trazabilidad

Cada ejecución guarda artefactos propios en:

```text
~/.local/share/autodev/
├── history.db
└── sessions/
    └── <session_id>/
        ├── execution.log
        ├── final_report.md
        ├── summary.md
        ├── summary.html
        ├── session.json
        ├── inputs/
        └── outputs/
```

## Validación

- La CLI puede verificarse con `autodev -h`.
- La revisión de cobertura puede verificarse con `autodev -ut --base-branch origin/main`.
- La sintaxis se valida con `python3 -m py_compile`.
- La suite local se valida con `pytest`.
