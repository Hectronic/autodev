# autodev

`autodev` es una CLI para desarrollar funcionalidades sobre un repositorio existente con ayuda de agentes de IA. La herramienta detecta el stack del proyecto, planifica la implementación, desarrolla el cambio, ejecuta la fase de pruebas y produce una validación final con trazabilidad local.

## Características

- Planificación guiada antes de tocar el código.
- Flujo encadenado de IA en cuatro fases: planificar, desarrollar, testear y validar.
- Soporte para `codex` y `gemini`.
- Detección automática de tipo de proyecto y test runner.
- Rama Git aislada para cada ejecución.
- Reporte final en `results/` con logs y resumen técnico.

## Instalación

```bash
git clone <repo-url>
cd autodev
./setup.sh
```

## Uso

La CLI expone el comando `-dev`.

```bash
# Ayuda
autodev -h

# Ejecutar el flujo de desarrollo en el directorio actual
autodev -dev --instructions "Añade un endpoint para exportar reportes en CSV"

# Especificar otra ruta de proyecto
autodev -dev --path /ruta/al/proyecto --instructions "Implementa autenticación por token"

# Elegir el agente
autodev -dev --instructions "Crea una vista de detalle" --agent gemini
```

## Resultados

Cada ejecución genera una carpeta propia dentro de `results/`:

```text
results/
└── autodev_results_YYYYMMDD_HHMMSS/
    ├── execution.log
    └── final_report.md
```

## Pruebas

```bash
pytest tests
```

## Arquitectura

- `autodev_cli/cli.py`: interfaz de línea de comandos.
- `autodev_cli/developer_orchestrator.py`: orquestador del flujo planificar -> desarrollar -> testear -> validar.
- `autodev_cli/gemini_client.py` y `autodev_cli/codex_client.py`: adaptadores para los agentes externos.
- `autodev_cli/project_detector.py`: detección del stack del proyecto.
- `autodev_cli/git_manager.py`: aislamiento en Git y commits finales.
