# Especificación Técnica: autodev

Este documento describe la arquitectura interna de `autodev`, una herramienta de desarrollo asistido por IA que encadena planificación, implementación, pruebas y validación sobre un repositorio Git.

## Arquitectura

### 1. Capa de interfaz

- Implementada con `click`.
- Expone el comando `-dev`.
- Expone el comando `-ut` para revisar cobertura de una rama respecto a su base.
- Expone `history` para listar las 10 sesiones más recientes y, opcionalmente, inspeccionar el detalle de una sesión concreta.
- Recibe instrucciones de desarrollo, ruta del proyecto y agente externo.

### 2. Orquestador

- `AutoDevOrchestrator` coordina el flujo completo.
- Valida que el proyecto esté dentro de Git.
- Detecta el stack del proyecto.
- Crea una rama aislada para la ejecución o reanuda una sesión previa si la rama `autodev/*` ya tiene una sesión activa.
- En el modo `-ut`, resuelve la rama base, calcula el `merge-base`, analiza el diff y guía la revisión de cobertura por fases.
- Genera logs, Markdown, HTML y metadatos en la carpeta de datos del usuario.

### 3. Clientes de IA

- `GeminiClient` ejecuta prompts con la CLI de Gemini.
- `CodexClient` ejecuta prompts con la CLI de Codex.
- Ambos preservan la continuidad de la sesión entre fases.

### 4. Git

- `GitManager` encapsula la validación de repositorio, creación de rama y commit final.

### 5. Persistencia local

- `HistoryManager` guarda sesiones, pasos, rama, estado y rutas de artefactos en SQLite.
- `RuntimeStore` resuelve la carpeta de datos, las rutas por sesión y el almacenamiento de artefactos.
- El resumen final se produce en Markdown y se convierte a HTML para apertura automática en navegador.

## Flujo de trabajo

Flujo `-dev`:
1. Identificación del proyecto.
2. Planificación de la solución.
3. Desarrollo de la funcionalidad.
4. Ejecución de pruebas.
5. Validación final y generación del reporte.

Flujo `-ut`:
1. Identificación del proyecto y de la rama actual.
2. Resolución de la rama base y del `merge-base`.
3. Análisis del diff y de los casos afectados.
4. Revisión de cobertura y detección de gaps.
5. Remediación de gaps.
6. Validación final y generación del reporte.

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
