import click
import os

from .developer_orchestrator import AutoDevOrchestrator
from .history_manager import HistoryManager

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'], ignore_unknown_options=True)

@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    """autodev: una herramienta para planificar, desarrollar, testear y validar funcionalidades."""
    pass


def _render_sessions_list(manager, limit):
    sessions = manager.get_sessions(limit=limit)
    if not sessions:
        click.echo("No hay sesiones en el historial.")
        return

    click.echo("\n--- Historial de Ejecuciones (últimas {0}) ---\n".format(len(sessions)))
    for s in sessions:
        click.echo(
            f"ID: {s['id'][:8]}... | Fecha: {s['timestamp']} | Estado: {s.get('status')} | Agente: {s['agent']}"
        )
        click.echo(f"Modo: {s.get('workflow') or 'development'}")
        click.echo(f"Rama: {s.get('branch_name')}")
        if s.get("base_branch"):
            click.echo(f"Rama base: {s.get('base_branch')}")
        click.echo(f"Ruta: {s['project_path']}")
        click.echo(f"Instrucciones: {s['instructions'][:100]}...")
        click.echo("-" * 60)
    click.echo("\nUsa 'autodev history -s <id_completo>' para ver detalles.")


@click.command(name="-dev", short_help="Desarrolla una funcionalidad a partir de instrucciones.")
@click.option('--path', '-p', type=click.Path(exists=True, file_okay=False, dir_okay=True), default=None, help="Ruta del proyecto a modificar. Por defecto, el directorio actual.")
@click.option('--instructions', '-i', required=True, help="Instrucciones sobre qué desarrollar.")
@click.option('--agent', '-a', default='codex', type=click.Choice(['gemini', 'codex'], case_sensitive=False), help="Agente de IA a utilizar.")
@click.option('--no-commit', is_flag=True, default=False, help="No realiza commit de los cambios al finalizar, los deja preparados para revisión.")
def dev_command(path, instructions, agent, no_commit):
    """Ejecuta el flujo completo de desarrollo sobre el proyecto indicado."""
    project_path = path if path else os.getcwd()
    orchestrator = AutoDevOrchestrator(project_path, agent=agent)
    if no_commit:
        orchestrator.run(instructions=instructions, no_commit=True)
    else:
        orchestrator.run(instructions=instructions)


@click.command(name="-ut", short_help="Revisa cobertura de cambios en una rama frente a su base.")
@click.option('--path', '-p', type=click.Path(exists=True, file_okay=False, dir_okay=True), default=None, help="Ruta del proyecto a revisar. Por defecto, el directorio actual.")
@click.option('--base-branch', '-b', default=None, help="Rama base contra la que comparar. Si no se indica, se detecta la upstream o la rama remota por defecto.")
@click.option('--instructions', '-i', default="", help="Contexto adicional para enfocar la revisión de cobertura.")
@click.option('--agent', '-a', default='codex', type=click.Choice(['gemini', 'codex'], case_sensitive=False), help="Agente de IA a utilizar.")
@click.option('--no-commit', is_flag=True, default=False, help="No realiza commit de los cambios al finalizar, los deja preparados para revisión.")
def unit_test_command(path, base_branch, instructions, agent, no_commit):
    """Revisa la cobertura de una rama respecto a su rama base y remedia gaps detectados."""
    project_path = path if path else os.getcwd()
    orchestrator = AutoDevOrchestrator(project_path, agent=agent)
    orchestrator.run_unit_test(
        base_branch=base_branch,
        instructions=instructions,
        no_commit=no_commit,
    )


@click.command(name="history", short_help="Muestra las 10 últimas sesiones.")
@click.option('--limit', '-l', default=10, type=click.IntRange(min=1), show_default=True, help="Número máximo de sesiones a mostrar.")
@click.option('--session-id', '-s', help="Muestra los detalles de una sesión específica.")
def history_command(limit, session_id):
    """Muestra las últimas sesiones o el detalle de una sesión concreta."""
    manager = HistoryManager()

    if session_id:
        session = manager.get_session(session_id)
        steps = manager.get_session_steps(session_id)
        if not session and not steps:
            click.echo(f"No se encontró información para la sesión {session_id}")
            return
        
        click.echo(f"\n--- Detalle de Sesión: {session_id} ---\n")
        if session:
            click.echo(f"Rama: {session.get('branch_name')}")
            click.echo(f"Modo: {session.get('workflow') or 'development'}")
            click.echo(f"Rama base: {session.get('base_branch')}")
            click.echo(f"Merge-base: {session.get('merge_base_sha')}")
            click.echo(f"Estado: {session.get('status')}")
            click.echo(f"Ruta de resultados: {session.get('results_dir')}")
            click.echo(f"Resumen MD: {session.get('summary_md_path')}")
            click.echo(f"Resumen HTML: {session.get('summary_html_path')}")
            click.echo("")
        for step in steps:
            click.echo(f"Fase: {step['step_label']} ({step['timestamp']})")
            click.echo("-" * 40)
            click.echo(f"Input:\n{step['prompt']}\n")
            click.echo(f"Respuesta:\n{step['response']}\n")
    else:
        _render_sessions_list(manager, limit)


cli.add_command(dev_command)
cli.add_command(unit_test_command)
cli.add_command(unit_test_command, name="unit-test")
cli.add_command(history_command)

if __name__ == "__main__":
    cli()
