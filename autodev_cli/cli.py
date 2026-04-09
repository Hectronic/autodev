import click
import os

from .developer_orchestrator import AutoDevOrchestrator
from .history_manager import HistoryManager

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'], ignore_unknown_options=True)

@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    """autodev: una herramienta para planificar, desarrollar, testear y validar funcionalidades."""
    pass

@click.command(name="-dev", short_help="Desarrolla una funcionalidad a partir de instrucciones.")
@click.option('--path', '-p', type=click.Path(exists=True, file_okay=False, dir_okay=True), default=None, help="Ruta del proyecto a modificar. Por defecto, el directorio actual.")
@click.option('--instructions', '-i', required=True, help="Instrucciones sobre qué desarrollar.")
@click.option('--agent', '-a', default='codex', type=click.Choice(['gemini', 'codex'], case_sensitive=False), help="Agente de IA a utilizar.")
@click.option('--no-commit', is_flag=True, default=False, help="No realiza commit de los cambios al finalizar, los deja preparados para revisión.")
def dev_command(path, instructions, agent, no_commit):
    """Ejecuta el flujo completo de desarrollo sobre el proyecto indicado."""
    project_path = path if path else os.getcwd()
    orchestrator = AutoDevOrchestrator(project_path, agent=agent)
    orchestrator.run(instructions=instructions, no_commit=no_commit)


@click.command(name="history", short_help="Muestra el historial de ejecuciones.")
@click.option('--limit', '-l', default=10, help="Número máximo de sesiones a mostrar.")
@click.option('--session-id', '-s', help="Muestra los detalles de una sesión específica.")
def history_command(limit, session_id):
    """Consulta el historial de sesiones almacenado en SQLite."""
    manager = HistoryManager()
    
    if session_id:
        steps = manager.get_session_steps(session_id)
        if not steps:
            click.echo(f"No se encontró información para la sesión {session_id}")
            return
        
        click.echo(f"\n--- Detalle de Sesión: {session_id} ---\n")
        for step in steps:
            click.echo(f"Fase: {step['step_label']} ({step['timestamp']})")
            click.echo("-" * 40)
            click.echo(f"Respuesta:\n{step['response']}\n")
    else:
        sessions = manager.get_sessions(limit=limit)
        if not sessions:
            click.echo("No hay sesiones en el historial.")
            return
        
        click.echo("\n--- Historial de Ejecuciones (últimas {0}) ---\n".format(len(sessions)))
        for s in sessions:
            click.echo(f"ID: {s['id'][:8]}... | Fecha: {s['timestamp']} | Agente: {s['agent']}")
            click.echo(f"Ruta: {s['project_path']}")
            click.echo(f"Instrucciones: {s['instructions'][:100]}...")
            click.echo("-" * 60)
        click.echo("\nUsa 'autodev history -s <id_completo>' para ver detalles.")


cli.add_command(dev_command)
cli.add_command(history_command)

if __name__ == "__main__":
    cli()
