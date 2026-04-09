# autodev

`autodev` es una CLI para desarrollar funcionalidades sobre un repositorio existente con ayuda de agentes de IA. La herramienta detecta el stack del proyecto, planifica la implementación, desarrolla el cambio, ejecuta la fase de pruebas y produce una validación final con trazabilidad local. Además incluye un flujo `-ut` para revisar cobertura de una rama frente a su rama base, identificar gaps y remediarlos por fases.

## Características

- Planificación guiada antes de tocar el código.
- Flujo encadenado de IA en cuatro fases: planificar, desarrollar, testear y validar.
- Flujo de revisión de cobertura por rama: analiza diff, revisa cobertura, identifica gaps y propone/remedia correcciones.
- Soporte para `codex` y `gemini`.
- Detección automática de tipo de proyecto y test runner.
- Rama Git aislada para cada ejecución.
- Persistencia completa de inputs, outputs, metadatos, Markdown y HTML en la carpeta de datos del usuario.
- Recuperación automática de sesión cuando se relanza sobre una rama `autodev/*` con sesión activa.

## Instalación

```bash
git clone <repo-url>
cd autodev
./setup.sh
```

## Uso

La CLI expone los comandos `-dev` para el flujo principal, `-ut` para revisión de cobertura y `history` para consultar las sesiones recientes.

```bash
# Ayuda
autodev -h

# Ejecutar el flujo de desarrollo en el directorio actual
autodev -dev --instructions "Añade un endpoint para exportar reportes en CSV"

# Especificar otra ruta de proyecto
autodev -dev --path /ruta/al/proyecto --instructions "Implementa autenticación por token"

# Elegir el agente
autodev -dev --instructions "Crea una vista de detalle" --agent gemini

# Revisar cobertura de la rama actual frente a su base
autodev -ut --base-branch origin/main

# Revisar cobertura con contexto adicional
autodev -ut --base-branch origin/main --instructions "prioriza el módulo de pagos"

# Ver las 10 últimas sesiones
autodev history
```

## Resultados

Cada ejecución genera una carpeta propia dentro de la carpeta de datos:

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

La ruta puede ajustarse con `XDG_DATA_HOME`.

Si el comando se ejecuta de nuevo en una rama `autodev/*` que tenga una sesión `running`, la herramienta recupera esa sesión y continúa guardando en el mismo `session_id`.
En el flujo `-ut`, la sesión guarda también la rama base y el `merge-base` usado para la revisión.

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
