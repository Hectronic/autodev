import datetime
import os
import uuid

from .codex_client import CodexClient
from .gemini_client import GeminiClient
from .git_manager import GitManager
from .project_detector import ProjectDetector
from .history_manager import HistoryManager


class AutoDevOrchestrator:
    def __init__(self, project_path, agent="codex"):
        self.project_path = os.path.abspath(project_path)
        self.agent_name = agent.lower()

        tool_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results_dir = os.path.join(tool_root, "results", f"autodev_results_{timestamp}")
        os.makedirs(self.results_dir, exist_ok=True)

        self.log_file = os.path.join(self.results_dir, "execution.log")

        if self.agent_name == "gemini":
            self.ai = GeminiClient(self.project_path, self.log_file)
        else:
            self.ai = CodexClient(self.project_path, self.log_file)

        self.git = GitManager(self.project_path)
        self.detector = ProjectDetector(self.project_path)
        self.history = HistoryManager()
        self.project_info = None
        self.session_id = str(uuid.uuid4())

    def run(self, instructions, no_commit=False):
        instructions = (instructions or "").strip()
        if not instructions:
            print("ERROR: Debes proporcionar instrucciones de desarrollo con --instructions.")
            return

        print("--- Project identification phase ---")
        self.project_info = self.detector.detect()

        if not self.project_info["is_git"]:
            print(f"ERROR: {self.project_path} no es un repositorio Git válido.")
            print("autodev solo puede ejecutarse dentro de repositorios Git para aislar los cambios.")
            return

        # Registrar el inicio de la sesión en BD
        self.history.create_session(
            self.session_id, 
            self.project_path, 
            self.agent_name, 
            instructions, 
            self.results_dir
        )

        print(f"Project Type: {self.project_info['project_type']}")
        print(f"Test Runner: {self.project_info['test_runner']}")
        print(f"Git Repository: {self.project_info['is_git']}")

        branch_id = str(uuid.uuid4())[:8]
        branch_name = f"autodev/{branch_id}"
        self.git.create_branch(branch_name)

        print(f"--- Results will be saved in: {self.results_dir} ---")
        print("--- Starting development flow ---")

        prompts = [
            (
                "--- Planning phase ---",
                self._build_plan_prompt(instructions),
            ),
            (
                "--- Development phase ---",
                self._build_develop_prompt(instructions),
            ),
            (
                "--- Testing phase ---",
                self._build_test_prompt(),
            ),
            (
                "--- Validation phase ---",
                self._build_validation_prompt(instructions),
            ),
        ]

        validation_report = None
        for index, (label, prompt) in enumerate(prompts):
            print(label)
            response = self.ai.run_prompt(prompt, resume=(index > 0))
            
            # Guardar cada paso en el historial
            self.history.save_step(self.session_id, label.strip("- "), prompt, response)
            
            if index == len(prompts) - 1:
                validation_report = response

        report_path = os.path.join(self.results_dir, "final_report.md")
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(validation_report or "")

        print("\n" + "=" * 40)
        print("RESUMEN FINAL:")
        print("=" * 40)
        print(validation_report or "")
        print("=" * 40 + "\n")

        if not no_commit:
            commit_message = f"autodev: {self._shorten_commit_message(instructions)}"
            self.git.commit_changes(commit_message)
            print(f"Development flow finished for branch {branch_name}")
        else:
            print(f"Development flow finished. Changes are ready for review in branch {branch_name} (NO COMMIT MADE).")
        
        print(f"Log and report saved in: {self.results_dir}")

    def _build_plan_prompt(self, instructions):
        return (
            "Actua como un desarrollador senior y planificador tecnico.\n"
            f"Contexto del proyecto: {self.project_info['project_type']} usando {self.project_info['test_runner']}.\n"
            f"Instrucciones del usuario: {instructions}\n"
            "PASO 1: Analiza el repositorio y redacta un plan de trabajo ordenado por prioridades.\n"
            "PASO 2: Identifica archivos, modulos y pruebas que probablemente deban tocarse.\n"
            "PASO 3: Define criterios de aceptacion y riesgos.\n"
            "No implementes cambios aun. Devuelve un plan accionable y concreto."
        )

    def _build_develop_prompt(self, instructions):
        return (
            "Implementa la funcionalidad solicitada siguiendo el plan anterior.\n"
            f"Instrucciones del usuario: {instructions}\n"
            f"Stack detectado: {self.project_info['project_type']} con {self.project_info['test_runner']}.\n"
            "Puedes modificar codigo de aplicacion, tests y documentacion si es necesario.\n"
            "Mantén los cambios enfocados, coherentes con el estilo existente y explica brevemente los archivos alterados."
        )

    def _build_test_prompt(self):
        return (
            "Ejecuta la estrategia de pruebas para verificar la implementacion.\n"
            f"Usa el test runner detectado: {self.project_info['test_runner']}.\n"
            "Primero valida los cambios relevantes de forma focalizada y despues ejecuta la suite necesaria para detectar regresiones.\n"
            "Si encuentras fallos, corrige el codigo o las pruebas hasta dejar la funcionalidad estable."
        )

    def _build_validation_prompt(self, instructions):
        return (
            "Valida el resultado final y entrega un informe tecnico en Markdown.\n"
            f"Instrucciones originales: {instructions}\n"
            "Incluye: resumen de lo desarrollado, archivos modificados, pruebas ejecutadas, resultado de validacion y riesgos residuales.\n"
            "Cierra indicando de forma explicita si la funcionalidad cumple los requisitos."
        )

    def _shorten_commit_message(self, instructions, limit=72):
        cleaned = " ".join(instructions.split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 3].rstrip() + "..."
