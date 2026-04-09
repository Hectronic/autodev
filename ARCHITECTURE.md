# Especificación Técnica: autodev

Este documento describe la arquitectura interna de `autodev`, una herramienta de desarrollo asistido por IA que encadena planificación, implementación, pruebas y validación sobre un repositorio Git.

## Arquitectura

### 1. Capa de interfaz

- Implementada con `click`.
- Expone el comando `-dev`.
- Recibe instrucciones de desarrollo, ruta del proyecto y agente externo.

### 2. Orquestador

- `AutoDevOrchestrator` coordina el flujo completo.
- Valida que el proyecto esté dentro de Git.
- Detecta el stack del proyecto.
- Crea una rama aislada para la ejecución.
- Genera logs y reporte final en `results/`.

### 3. Clientes de IA

- `GeminiClient` ejecuta prompts con la CLI de Gemini.
- `CodexClient` ejecuta prompts con la CLI de Codex.
- Ambos preservan la continuidad de la sesión entre fases.

### 4. Git

- `GitManager` encapsula la validación de repositorio, creación de rama y commit final.

## Flujo de trabajo

1. Identificación del proyecto.
2. Planificación de la solución.
3. Desarrollo de la funcionalidad.
4. Ejecución de pruebas.
5. Validación final y generación del reporte.

## Trazabilidad

Cada ejecución guarda artefactos propios en:

```text
autodev/
└── results/
    └── autodev_results_YYYYMMDD_HHMMSS/
        ├── execution.log
        └── final_report.md
```

## Validación

- La CLI puede verificarse con `autodev -h`.
- La sintaxis se valida con `python3 -m py_compile`.
- La suite local se valida con `pytest`.
