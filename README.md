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

La CLI expone los comandos `-dev` para el flujo principal, `-ut` para revisión de cobertura, `-e`/`--explain` para generar un informe técnico completo del repositorio, `push` para commitear y empujar cambios locales, y `history` para consultar las sesiones recientes.

```bash
# Ayuda
autodev -h

# Ejecutar el flujo de desarrollo en el directorio actual
autodev -dev "Añade un endpoint para exportar reportes en CSV"

# Hacer commit y push de la rama creada al finalizar
autodev -dev "Añade un endpoint para exportar reportes en CSV" --push

# Especificar otra ruta de proyecto
autodev -dev --path /ruta/al/proyecto "Implementa autenticación por token"

# Elegir el agente
autodev -dev "Crea una vista de detalle" --agent gemini

# Revisar cobertura de la rama actual frente a su base
autodev -ut --base-branch origin/main

# Generar un informe completo del repositorio
autodev -e

# La misma accion con el alias largo
autodev --explain

# Ver las 10 últimas sesiones
autodev history

# Generar un commit automático a partir de los cambios locales y pushear la rama actual
autodev push
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
La salida distingue entre el `AutoDev Session ID` interno y el `Agent Session ID` del CLI externo (`codex` o `gemini`). El primero identifica la ejecución de `autodev`; el segundo es el que debe usarse para reanudar el agente si hace falta.
En `-dev`, cuando la sesión es nueva, la herramienta carga `README.md`, `GEMINI.md` y `AGENTS.md` si existen, y añade una fase dedicada a documentar los cambios o actualizar la documentación del repositorio.
En el flujo `-ut`, la sesión guarda también la rama base y el `merge-base` usado para la revisión. Además, contempla tanto cambios ya commiteados como cambios pendientes en el working tree, y presenta la diff en bloques Markdown separados.
En el flujo `-e`/`--explain`, la sesión le pide al agente de IA que genere las secciones del reporte técnico del repositorio con cobertura de stack, arquitectura, diseño, funcionalidad, tests y riesgos, junto con un HTML standalone con navegación interna.
Cada sección del informe también se guarda como un `.md` independiente dentro de la carpeta de la sesión para facilitar trazabilidad y revisión puntual.

## Pruebas

```bash
pytest tests
```

## Arquitectura

- `autodev_cli/cli.py`: interfaz de línea de comandos.
- `autodev_cli/developer_orchestrator.py`: orquestador del flujo planificar -> desarrollar -> testear -> validar.
- `autodev_cli/gemini_client.py` y `autodev_cli/codex_client.py`: adaptadores para los agentes externos.
- `autodev_cli/project_detector.py`: detección del stack del proyecto.
- `autodev_cli/git_manager.py`: aislamiento en Git, generación de mensajes de commit y push finales opcionales.
