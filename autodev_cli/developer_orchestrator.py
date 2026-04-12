import datetime
import os
from pathlib import Path
import unicodedata
import uuid

from .codex_client import CodexClient
from .gemini_client import GeminiClient
from .git_manager import GitManager
from .history_manager import HistoryManager
from .project_detector import ProjectDetector
from .reporting import open_html_report, write_html_report, write_sectioned_html_report
from .runtime_store import RuntimeStore


class AutoDevOrchestrator:
    def __init__(self, project_path, agent="codex"):
        self.project_path = os.path.abspath(project_path)
        self.agent_name = agent.lower()
        self.storage = RuntimeStore()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        bootstrap_dir = self.storage.base_dir / "runs" / f"bootstrap_{timestamp}_{uuid.uuid4().hex[:8]}"
        self.results_dir = str(bootstrap_dir)
        self.log_file = str(bootstrap_dir / "execution.log")

        if self.agent_name == "gemini":
            self.ai = GeminiClient(self.project_path, self.log_file)
        else:
            self.ai = CodexClient(self.project_path, self.log_file)

        self.git = GitManager(self.project_path)
        self.detector = ProjectDetector(self.project_path)
        self.history = HistoryManager(self.storage)
        self.project_info = None
        self.session_id = None
        self.branch_name = None
        self.base_branch_name = None
        self.merge_base_sha = None
        self.diff_stat = None
        self.diff_name_status = None
        self.changed_files = []
        self.commit_summary = None
        self.diff_patch = None
        self.pending_status_lines = []
        self.pending_staged_files = []
        self.pending_unstaged_files = []
        self.pending_untracked_files = []
        self.pending_staged_diff_stat = ""
        self.pending_unstaged_diff_stat = ""
        self.pending_staged_diff_name_status = ""
        self.pending_unstaged_diff_name_status = ""
        self.pending_staged_diff_patch = ""
        self.pending_unstaged_diff_patch = ""
        self.workflow_name = "development"
        self.resume_mode = False
        self.session_dir = None
        self.summary_md_path = None
        self.summary_html_path = None
        self.reference_docs = []
        self.reference_docs_context = ""

    def run(self, instructions, push=False):
        instructions = (instructions or "").strip()
        if not instructions:
            print("ERROR: Debes proporcionar instrucciones de desarrollo como argumento de -dev.")
            return

        session_status = "completed"

        try:
            print("--- Project identification phase ---")
            self.project_info = self.detector.detect()
            if not self.project_info["is_git"]:
                print(f"ERROR: {self.project_path} no es un repositorio Git válido.")
                print("autodev solo puede ejecutarse dentro de repositorios Git para aislar los cambios.")
                return

            print(f"Project Type: {self.project_info['project_type']}")
            print(f"Test Runner: {self.project_info['test_runner']}")
            print(f"Git Repository: {self.project_info['is_git']}")

            current_branch = self.git.get_current_branch()
            recoverable_session = None
            if current_branch and current_branch.startswith("autodev/"):
                recoverable_session = self.history.get_running_session_for_branch(
                    self.project_path,
                    current_branch,
                    self.agent_name,
                    workflow=self.workflow_name,
                )

            if recoverable_session:
                self._load_session(recoverable_session)
                print(f"--- Reanudando sesion {self.session_id} en la rama {self.branch_name} ---")
            else:
                if current_branch and current_branch.startswith("autodev/"):
                    self.branch_name = current_branch
                else:
                    branch_id = str(uuid.uuid4())[:8]
                    self.branch_name = f"autodev/{branch_id}"
                    self.git.create_branch(self.branch_name)

                self.session_id = str(uuid.uuid4())
                self.resume_mode = False
                self._prepare_session_artifacts()
                self.history.create_session(
                    self.session_id,
                    self.project_path,
                    self.agent_name,
                    instructions,
                    self.results_dir,
                    branch_name=self.branch_name,
                    workflow=self.workflow_name,
                    status="running",
                    log_path=self.log_file,
                    summary_md_path=self.summary_md_path,
                    summary_html_path=self.summary_html_path,
                    agent_session_id=self._get_agent_session_id(),
                    head_sha=self.git.get_head_sha(),
                )
                self._load_reference_docs_into_session()
                print(f"--- Nueva sesion {self.session_id} creada en la rama {self.branch_name} ---")

            self._prepare_session_artifacts()
            self._sync_client_log_file()
            self.history.update_session(
                self.session_id,
                branch_name=self.branch_name,
                workflow=self.workflow_name,
                status="running",
                results_dir=self.results_dir,
                log_path=self.log_file,
                summary_md_path=self.summary_md_path,
                summary_html_path=self.summary_html_path,
                agent_session_id=self._get_agent_session_id(),
                head_sha=self.git.get_head_sha(),
            )
            self._write_session_manifest(status="running")

            existing_steps = self.history.get_session_steps(self.session_id)
            start_index = len(existing_steps)
            if existing_steps:
                self._restore_agent_session(existing_steps)

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
                    "--- Documentation phase ---",
                    self._build_documentation_prompt(instructions),
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
            if start_index >= len(prompts):
                validation_report = existing_steps[-1]["response"] if existing_steps else ""
            else:
                for index, (label, prompt) in enumerate(prompts[start_index:], start=start_index):
                    print(label)
                    resume_flag = self.resume_mode or index > 0
                    response = self.ai.run_prompt(prompt, resume=resume_flag)

                    step_slug = self._slugify_label(label)
                    input_path = self.storage.session_file(
                        self.session_id,
                        f"inputs/{index + 1:02d}_{step_slug}.md",
                    )
                    output_path = self.storage.session_file(
                        self.session_id,
                        f"outputs/{index + 1:02d}_{step_slug}.md",
                    )
                    self.storage.write_text(input_path, prompt)
                    self.storage.write_text(output_path, response)

                    self.history.save_step(
                        self.session_id,
                        label.strip("- "),
                        prompt,
                        response,
                        step_order=index + 1,
                        input_path=str(input_path),
                        output_path=str(output_path),
                    )
                    self.history.update_session(
                        self.session_id,
                        agent_session_id=self._get_agent_session_id(),
                        head_sha=self.git.get_head_sha(),
                    )

                    if index == len(prompts) - 1:
                        validation_report = response

            all_steps = self.history.get_session_steps(self.session_id)
            final_markdown = self._compose_final_report(
                validation_report or "",
                instructions,
                all_steps,
                self.branch_name,
            )

            report_path = self.storage.session_file(self.session_id, "final_report.md")
            summary_md_path = self.storage.session_file(self.session_id, "summary.md")
            summary_html_path = self.storage.session_file(self.session_id, "summary.html")
            self.summary_md_path = str(summary_md_path)
            self.summary_html_path = str(summary_html_path)
            self.storage.write_text(report_path, final_markdown)
            self.storage.write_text(summary_md_path, final_markdown)
            write_html_report(
                summary_html_path,
                final_markdown,
                {
                    "title": "autodev summary",
                    "session_id": self.session_id,
                    "branch_name": self.branch_name,
                    "agent": self.agent_name,
                    "project_path": self.project_path,
                    "status": "completed",
                    "results_dir": self.results_dir,
                },
            )

            if not open_html_report(summary_html_path):
                print(f"No se pudo abrir automaticamente el HTML. Ruta: {summary_html_path}")

            print("\n" + "=" * 40)
            print("RESUMEN FINAL:")
            print("=" * 40)
            print(final_markdown)
            print("=" * 40 + "\n")

            commit_message = f"autodev: {self._shorten_commit_message(instructions)}"
            self._finalize_branch_changes(
                commit_message=commit_message,
                push=push,
                workflow_label="Development flow",
            )

            print(f"Session ID: {self.session_id}")
            print(f"Branch: {self.branch_name}")
            print(f"Log and report saved in: {self.results_dir}")
        except Exception:
            session_status = "failed"
            raise
        finally:
            self._finalize_session(session_status)

    def run_unit_test(self, base_branch=None, instructions=None, push=False):
        extra_instructions = (instructions or "").strip()
        session_status = "completed"

        try:
            print("--- Project identification phase ---")
            self.workflow_name = "unit-test"
            self.project_info = self.detector.detect()
            if not self.project_info["is_git"]:
                print(f"ERROR: {self.project_path} no es un repositorio Git válido.")
                print("autodev solo puede ejecutarse dentro de repositorios Git para aislar los cambios.")
                return

            print(f"Project Type: {self.project_info['project_type']}")
            print(f"Test Runner: {self.project_info['test_runner']}")
            print(f"Git Repository: {self.project_info['is_git']}")

            current_branch = self.git.get_current_branch()
            if not current_branch:
                print("ERROR: No se pudo determinar la rama actual. Ejecuta el comando sobre una rama real.")
                return

            self.branch_name = current_branch
            self.base_branch_name = base_branch or self.git.get_branch_origin(current_branch)
            if not self.base_branch_name:
                print(
                    "ERROR: No se pudo determinar la rama base de referencia. "
                    "Pasa --base-branch o configura upstream en la rama."
                )
                return

            self.merge_base_sha = self.git.get_merge_base(self.base_branch_name, current_branch)
            if not self.merge_base_sha:
                print(
                    f"ERROR: No se pudo calcular el merge-base entre {self.branch_name} y {self.base_branch_name}."
                )
                return

            self.diff_stat = self.git.get_diff_stat(self.base_branch_name, current_branch)
            self.diff_name_status = self.git.get_diff_name_status(self.base_branch_name, current_branch)
            self.changed_files = self.git.get_changed_files(self.base_branch_name, current_branch)
            self.commit_summary = self.git.get_commit_summary(self.base_branch_name, current_branch)
            self.diff_patch = self.git.get_diff_patch(
                self.base_branch_name,
                current_branch,
                paths=self.changed_files,
            )
            self.pending_status_lines = self.git.get_status_porcelain()
            self.pending_staged_files = self.git.get_staged_changed_files()
            self.pending_unstaged_files = self.git.get_unstaged_changed_files()
            self.pending_untracked_files = self.git.get_untracked_files()
            self.pending_staged_diff_stat = self.git.get_staged_diff_stat()
            self.pending_unstaged_diff_stat = self.git.get_unstaged_diff_stat()
            self.pending_staged_diff_name_status = self.git.get_staged_diff_name_status()
            self.pending_unstaged_diff_name_status = self.git.get_unstaged_diff_name_status()
            self.pending_staged_diff_patch = self.git.get_staged_diff_patch(paths=self.pending_staged_files)
            self.pending_unstaged_diff_patch = self.git.get_unstaged_diff_patch(paths=self.pending_unstaged_files)

            resume_session = self.history.get_running_session_for_branch(
                self.project_path,
                self.branch_name,
                self.agent_name,
                workflow=self.workflow_name,
            )

            if resume_session:
                self._load_session(resume_session)
                print(f"--- Reanudando sesion {self.session_id} en la rama {self.branch_name} ---")
            else:
                review_context = self._build_unit_test_context(extra_instructions)
                self.session_id = str(uuid.uuid4())
                self.resume_mode = False
                self._prepare_session_artifacts()
                self.history.create_session(
                    self.session_id,
                    self.project_path,
                    self.agent_name,
                    review_context,
                    self.results_dir,
                    branch_name=self.branch_name,
                    workflow=self.workflow_name,
                    base_branch=self.base_branch_name,
                    merge_base_sha=self.merge_base_sha,
                    status="running",
                    log_path=self.log_file,
                    summary_md_path=self.summary_md_path,
                    summary_html_path=self.summary_html_path,
                    agent_session_id=self._get_agent_session_id(),
                    head_sha=self.git.get_head_sha(),
                )
                print(f"--- Nueva sesion {self.session_id} creada para revisar la rama {self.branch_name} ---")

            self._prepare_session_artifacts()
            self._sync_client_log_file()
            self.history.update_session(
                self.session_id,
                branch_name=self.branch_name,
                workflow=self.workflow_name,
                base_branch=self.base_branch_name,
                merge_base_sha=self.merge_base_sha,
                status="running",
                results_dir=self.results_dir,
                log_path=self.log_file,
                summary_md_path=self.summary_md_path,
                summary_html_path=self.summary_html_path,
                agent_session_id=self._get_agent_session_id(),
                head_sha=self.git.get_head_sha(),
            )
            self._write_session_manifest(status="running")

            existing_steps = self.history.get_session_steps(self.session_id)
            start_index = len(existing_steps)
            if existing_steps:
                self._restore_agent_session(existing_steps)

            print(f"--- Results will be saved in: {self.results_dir} ---")
            print("--- Starting unit test review flow ---")
            print(f"Branch under review: {self.branch_name}")
            print(f"Base branch: {self.base_branch_name}")
            print(f"Merge-base: {self.merge_base_sha}")

            prompts = [
                (
                    "--- Diff analysis phase ---",
                    self._build_unit_test_analysis_prompt(extra_instructions),
                ),
                (
                    "--- Coverage review phase ---",
                    self._build_coverage_review_prompt(extra_instructions),
                ),
                (
                    "--- Gap remediation phase ---",
                    self._build_gap_remediation_prompt(extra_instructions),
                ),
                (
                    "--- Final validation phase ---",
                    self._build_unit_test_validation_prompt(extra_instructions),
                ),
            ]

            validation_report = None
            if start_index >= len(prompts):
                validation_report = existing_steps[-1]["response"] if existing_steps else ""
            else:
                for index, (label, prompt) in enumerate(prompts[start_index:], start=start_index):
                    print(label)
                    resume_flag = self.resume_mode or index > 0
                    response = self.ai.run_prompt(prompt, resume=resume_flag)

                    step_slug = self._slugify_label(label)
                    input_path = self.storage.session_file(
                        self.session_id,
                        f"inputs/{index + 1:02d}_{step_slug}.md",
                    )
                    output_path = self.storage.session_file(
                        self.session_id,
                        f"outputs/{index + 1:02d}_{step_slug}.md",
                    )
                    self.storage.write_text(input_path, prompt)
                    self.storage.write_text(output_path, response)

                    self.history.save_step(
                        self.session_id,
                        label.strip("- "),
                        prompt,
                        response,
                        step_order=index + 1,
                        input_path=str(input_path),
                        output_path=str(output_path),
                    )
                    self.history.update_session(
                        self.session_id,
                        agent_session_id=self._get_agent_session_id(),
                        head_sha=self.git.get_head_sha(),
                    )

                    if index == len(prompts) - 1:
                        validation_report = response

            all_steps = self.history.get_session_steps(self.session_id)
            final_markdown = self._compose_unit_test_report(
                validation_report or "",
                self._build_unit_test_context(extra_instructions),
                all_steps,
            )

            report_path = self.storage.session_file(self.session_id, "final_report.md")
            summary_md_path = self.storage.session_file(self.session_id, "summary.md")
            summary_html_path = self.storage.session_file(self.session_id, "summary.html")
            self.summary_md_path = str(summary_md_path)
            self.summary_html_path = str(summary_html_path)
            self.storage.write_text(report_path, final_markdown)
            self.storage.write_text(summary_md_path, final_markdown)
            write_html_report(
                summary_html_path,
                final_markdown,
                {
                    "title": "autodev unit test summary",
                    "session_id": self.session_id,
                    "branch_name": self.branch_name,
                    "base_branch": self.base_branch_name,
                    "merge_base_sha": self.merge_base_sha,
                    "agent": self.agent_name,
                    "project_path": self.project_path,
                    "status": "completed",
                    "results_dir": self.results_dir,
                },
            )

            if not open_html_report(summary_html_path):
                print(f"No se pudo abrir automaticamente el HTML. Ruta: {summary_html_path}")

            print("\n" + "=" * 40)
            print("RESUMEN FINAL:")
            print("=" * 40)
            print(final_markdown)
            print("=" * 40 + "\n")

            commit_message = f"autodev-ut: {self._shorten_commit_message(self.base_branch_name or self.branch_name)}"
            self._finalize_branch_changes(
                commit_message=commit_message,
                push=push,
                workflow_label="Unit test review",
            )

            print(f"Session ID: {self.session_id}")
            print(f"Branch: {self.branch_name}")
            print(f"Base branch: {self.base_branch_name}")
            print(f"Log and report saved in: {self.results_dir}")
        except Exception:
            session_status = "failed"
            raise
        finally:
            self._finalize_session(session_status)

    def run_explain(self):
        session_status = "completed"

        try:
            print("--- Project identification phase ---")
            self.workflow_name = "explain"
            self.project_info = self.detector.detect()
            if not self.project_info["is_git"]:
                print(f"ERROR: {self.project_path} no es un repositorio Git válido.")
                print("autodev solo puede ejecutarse dentro de repositorios Git para analizar el proyecto.")
                return

            print(f"Project Type: {self.project_info['project_type']}")
            print(f"Test Runner: {self.project_info['test_runner']}")
            print(f"Git Repository: {self.project_info['is_git']}")

            self.branch_name = self.git.get_current_branch()
            self.base_branch_name = None
            self.merge_base_sha = None
            self.session_id = str(uuid.uuid4())
            self.resume_mode = False
            self._prepare_session_artifacts()

            instructions = "Analisis exploratorio del repositorio para generar un informe tecnico completo."
            self.history.create_session(
                self.session_id,
                self.project_path,
                self.agent_name,
                instructions,
                self.results_dir,
                branch_name=self.branch_name,
                workflow=self.workflow_name,
                status="running",
                log_path=self.log_file,
                summary_md_path=self.summary_md_path,
                summary_html_path=self.summary_html_path,
                agent_session_id=None,
                head_sha=self.git.get_head_sha(),
            )

            self.history.update_session(
                self.session_id,
                branch_name=self.branch_name,
                workflow=self.workflow_name,
                status="running",
                results_dir=self.results_dir,
                log_path=self.log_file,
                summary_md_path=self.summary_md_path,
                summary_html_path=self.summary_html_path,
                head_sha=self.git.get_head_sha(),
            )
            self._write_session_manifest(status="running")

            snapshot = self._collect_explain_snapshot()
            sections = self._build_explain_sections(snapshot)

            for index, section in enumerate(sections, start=1):
                step_slug = self._slugify_label(section["title"])
                print(f"--- {section['title']} phase ---")
                response = self.ai.run_prompt(section["prompt"], resume=self.resume_mode or index > 1)
                input_path = self.storage.session_file(
                    self.session_id,
                    f"inputs/{index:02d}_{step_slug}.md",
                )
                output_path = self.storage.session_file(
                    self.session_id,
                    f"outputs/{index:02d}_{step_slug}.md",
                )
                self.storage.write_text(input_path, section["prompt"])
                self.storage.write_text(output_path, response)
                section["markdown"] = response
                self.history.save_step(
                    self.session_id,
                    section["title"],
                    section["prompt"],
                    response,
                    step_order=index,
                    input_path=str(input_path),
                    output_path=str(output_path),
                )
                self.history.update_session(
                    self.session_id,
                    agent_session_id=self._get_agent_session_id(),
                    head_sha=self.git.get_head_sha(),
                )

            final_markdown = self._compose_explain_report(snapshot, sections)
            report_path = self.storage.session_file(self.session_id, "final_report.md")
            summary_md_path = self.storage.session_file(self.session_id, "summary.md")
            summary_html_path = self.storage.session_file(self.session_id, "summary.html")
            self.summary_md_path = str(summary_md_path)
            self.summary_html_path = str(summary_html_path)
            self.storage.write_text(report_path, final_markdown)
            self.storage.write_text(summary_md_path, final_markdown)
            write_sectioned_html_report(
                summary_html_path,
                sections,
                {
                    "title": "autodev explain summary",
                    "session_id": self.session_id,
                    "branch_name": self.branch_name,
                    "agent": self.agent_name,
                    "project_path": self.project_path,
                    "status": "completed",
                    "results_dir": self.results_dir,
                },
            )

            if not open_html_report(summary_html_path):
                print(f"No se pudo abrir automaticamente el HTML. Ruta: {summary_html_path}")

            print("\n" + "=" * 40)
            print("RESUMEN FINAL:")
            print("=" * 40)
            print(final_markdown)
            print("=" * 40 + "\n")

            print(f"Session ID: {self.session_id}")
            print(f"Branch: {self.branch_name or 'detached'}")
            print(f"Log and report saved in: {self.results_dir}")
        except Exception:
            session_status = "failed"
            raise
        finally:
            self._finalize_session(session_status)

    def _build_plan_prompt(self, instructions):
        return (
            "Actua como un desarrollador senior y planificador tecnico.\n"
            f"Contexto del proyecto: {self.project_info['project_type']} usando {self.project_info['test_runner']}.\n"
            f"{self._build_reference_docs_context()}\n"
            f"Instrucciones del usuario: {instructions}\n"
            "PASO 1: Analiza el repositorio y redacta un plan de trabajo ordenado por prioridades.\n"
            "PASO 2: Identifica archivos, modulos y pruebas que probablemente deban tocarse.\n"
            "PASO 3: Define criterios de aceptacion y riesgos.\n"
            "No implementes cambios aun. Devuelve un plan accionable y concreto."
        )

    def _build_develop_prompt(self, instructions):
        return (
            "Implementa la funcionalidad solicitada siguiendo el plan anterior.\n"
            f"{self._build_reference_docs_context()}\n"
            f"Instrucciones del usuario: {instructions}\n"
            f"Stack detectado: {self.project_info['project_type']} con {self.project_info['test_runner']}.\n"
            "Puedes modificar codigo de aplicacion, tests y documentacion si es necesario.\n"
            "Mantén los cambios enfocados, coherentes con el estilo existente y explica brevemente los archivos alterados."
        )

    def _build_documentation_prompt(self, instructions):
        return (
            "Documenta los cambios realizados y actualiza la documentacion existente del repositorio.\n"
            f"{self._build_reference_docs_context()}\n"
            f"Instrucciones del usuario: {instructions}\n"
            "Tareas:\n"
            "1. Revisa la documentacion cargada de la sesion y actualiza README, GEMINI, AGENTS o cualquier doc relevante que hayas encontrado.\n"
            "2. Añade o corrige secciones que describan el cambio, uso, configuracion o limitaciones.\n"
            "3. Si no existe documentacion util, crea la minima necesaria para reflejar el comportamiento nuevo.\n"
            "4. Explica brevemente que archivos de documentacion cambiaste y por que."
        )

    def _build_test_prompt(self):
        return (
            "Ejecuta la estrategia de pruebas para verificar la implementacion.\n"
            f"{self._build_reference_docs_context()}\n"
            f"Usa el test runner detectado: {self.project_info['test_runner']}.\n"
            "Primero valida los cambios relevantes de forma focalizada y despues ejecuta la suite necesaria para detectar regresiones.\n"
            "Si encuentras fallos, corrige el codigo o las pruebas hasta dejar la funcionalidad estable."
        )

    def _build_validation_prompt(self, instructions):
        return (
            "Valida el resultado final y entrega un informe tecnico en Markdown.\n"
            f"{self._build_reference_docs_context()}\n"
            f"Instrucciones originales: {instructions}\n"
            "Incluye: resumen de lo desarrollado, archivos modificados, pruebas ejecutadas, resultado de validacion y riesgos residuales.\n"
            "Cierra indicando de forma explicita si la funcionalidad cumple los requisitos."
        )

    def _finalize_branch_changes(self, commit_message, push, workflow_label):
        if push:
            self.git.commit_changes(commit_message)
            self.git.push_branch(self.branch_name)
            print(f"{workflow_label} finished for branch {self.branch_name} (commit and push made).")
            return

        print(
            f"{workflow_label} finished. Changes are ready for review in branch {self.branch_name} (NO COMMIT MADE, NO PUSH MADE)."
        )

    def _build_unit_test_context(self, instructions):
        context_lines = [
            f"Rama a revisar: {self.branch_name}",
            f"Rama base: {self.base_branch_name}",
            f"Merge-base: {self.merge_base_sha}",
            f"Stack detectado: {self.project_info['project_type']} con {self.project_info['test_runner']}",
        ]
        if self.diff_stat:
            context_lines.append("Diff stat:")
            context_lines.append(self.diff_stat)
        if self.diff_name_status:
            context_lines.append("Diff name-status:")
            context_lines.append(self.diff_name_status)
        if self.changed_files:
            context_lines.append("Archivos cambiados:")
            context_lines.extend(f"- {path}" for path in self.changed_files)
        if self.commit_summary:
            context_lines.append("Resumen de commits:")
            context_lines.append(self.commit_summary)
        if self.pending_status_lines:
            context_lines.append("Cambios pendientes en working tree:")
            context_lines.extend(self.pending_status_lines)
        if self.pending_untracked_files:
            context_lines.append("Archivos no trackeados:")
            context_lines.extend(f"- {path}" for path in self.pending_untracked_files)
        if self.pending_staged_files:
            context_lines.append("Archivos staged:")
            context_lines.extend(f"- {path}" for path in self.pending_staged_files)
        if self.pending_unstaged_files:
            context_lines.append("Archivos unstaged:")
            context_lines.extend(f"- {path}" for path in self.pending_unstaged_files)
        if instructions:
            context_lines.append(f"Indicaciones adicionales: {instructions}")
        return "\n".join(context_lines)

    def _build_unit_test_analysis_prompt(self, instructions):
        return (
            "Analiza la diferencia entre la rama actual y su rama base, sin modificar nada aun.\n"
            f"{self._build_unit_test_context(instructions)}\n"
            "Tareas:\n"
            "1. Resume el objetivo funcional de estos cambios.\n"
            "2. Explica que comportamiento nuevo o alterado introduce cada bloque relevante.\n"
            "3. Identifica las areas de riesgo para la cobertura.\n"
            "4. Devuelve una lista priorizada de escenarios que deberian tener pruebas."
        )

    def _build_coverage_review_prompt(self, instructions):
        return (
            "Revisa la cobertura existente para los cambios detectados.\n"
            f"{self._build_unit_test_context(instructions)}\n"
            "Tareas:\n"
            "1. Determina que tests actuales cubren cada cambio y donde faltan casos.\n"
            "2. Identifica gaps concretos por archivo, ruta de codigo y tipo de caso.\n"
            "3. Señala si faltan pruebas de regresion, bordes, errores o integracion.\n"
            "4. Deja claro que gaps deben arreglarse antes de dar por valida la rama.\n"
            "No escribas codigo aun."
        )

    def _build_gap_remediation_prompt(self, instructions):
        return (
            "Corrige los gaps de cobertura detectados en la revision anterior.\n"
            f"{self._build_unit_test_context(instructions)}\n"
            "Tareas:\n"
            "1. Añade o ajusta pruebas para cubrir los gaps identificados.\n"
            "2. Si hace falta, ajusta el codigo minimo para que los casos queden bien soportados.\n"
            "3. Mantén el cambio enfocado y coherente con el estilo del repositorio.\n"
            "4. Explica brevemente que gaps quedaron cerrados y que archivos cambiaste."
        )

    def _build_unit_test_validation_prompt(self, instructions):
        return (
            "Valida el cierre de la cobertura y entrega un informe tecnico en Markdown.\n"
            f"{self._build_unit_test_context(instructions)}\n"
            "Incluye: resumen de los gaps detectados, pruebas nuevas o actualizadas, validacion final, y riesgos residuales.\n"
            "Confirma de forma explicita si la rama ya tiene cobertura suficiente para los cambios introducidos."
        )

    def _shorten_commit_message(self, instructions, limit=72):
        cleaned = " ".join(instructions.split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 3].rstrip() + "..."

    def _prepare_session_artifacts(self):
        self.session_dir = self.storage.session_dir(self.session_id)
        self.results_dir = str(self.session_dir)
        self.log_file = str(self.session_dir / "execution.log")
        self.summary_md_path = str(self.session_dir / "summary.md")
        self.summary_html_path = str(self.session_dir / "summary.html")
        self._sync_client_log_file()

    def _sync_client_log_file(self):
        self.ai.log_file = self.log_file

    def _get_agent_session_id(self):
        return getattr(self.ai, "session_id", None)

    def _restore_agent_session(self, steps):
        if hasattr(self.ai, "has_started") and steps:
            self.ai.has_started = True
        agent_session_id = self.history.get_session(self.session_id).get("agent_session_id")
        if hasattr(self.ai, "session_id") and agent_session_id:
            self.ai.session_id = agent_session_id
            self.resume_mode = True
        elif steps:
            self.resume_mode = True

    def _load_session(self, session_row):
        self.session_id = session_row["id"]
        self.branch_name = session_row.get("branch_name")
        self.base_branch_name = session_row.get("base_branch")
        self.merge_base_sha = session_row.get("merge_base_sha")
        self.workflow_name = session_row.get("workflow") or self.workflow_name
        self.resume_mode = True
        self._prepare_session_artifacts()
        if session_row.get("results_dir"):
            self.results_dir = session_row["results_dir"]
            self.session_dir = self.storage.session_dir(self.session_id)
        if session_row.get("log_path"):
            self.log_file = session_row["log_path"]
        if session_row.get("summary_md_path"):
            self.summary_md_path = session_row["summary_md_path"]
        if session_row.get("summary_html_path"):
            self.summary_html_path = session_row["summary_html_path"]
        self._restore_reference_docs_from_session()
        self._sync_client_log_file()
        if hasattr(self.ai, "has_started"):
            self.ai.has_started = True
        if hasattr(self.ai, "session_id") and session_row.get("agent_session_id"):
            self.ai.session_id = session_row["agent_session_id"]

    def _slugify_label(self, label):
        normalized = unicodedata.normalize("NFKD", label or "").encode("ascii", "ignore").decode("ascii")
        return "".join(ch.lower() if ch.isalnum() else "_" for ch in normalized).strip("_") or "section"

    def _compose_final_report(self, validation_report, instructions, steps, branch_name):
        step_lines = []
        for step in steps or []:
            step_lines.append(f"- {step.get('step_label', '')}")
        steps_section = "\n".join(step_lines) if step_lines else "- Sin pasos previos registrados"
        report = validation_report.strip()
        return (
            "# Resumen de ejecución\n\n"
            f"- Session ID: {self.session_id}\n"
            f"- Branch: {branch_name}\n"
            f"- Agent: {self.agent_name}\n"
            f"- Project path: {self.project_path}\n"
            f"- Instructions: {instructions}\n\n"
            "## Pasos registrados\n\n"
            f"{steps_section}\n\n"
            "## Informe final\n\n"
            f"{report}\n"
        )

    def _compose_unit_test_report(self, validation_report, instructions, steps):
        step_lines = []
        for step in steps or []:
            step_lines.append(f"- {step.get('step_label', '')}")
        steps_section = "\n".join(step_lines) if step_lines else "- Sin pasos previos registrados"
        report = validation_report.strip()
        return (
            "# Resumen de revision de cobertura\n\n"
            f"- Session ID: {self.session_id}\n"
            f"- Branch: {self.branch_name}\n"
            f"- Base branch: {self.base_branch_name}\n"
            f"- Merge-base: {self.merge_base_sha}\n"
            f"- Agent: {self.agent_name}\n"
            f"- Project path: {self.project_path}\n"
            f"- Instructions: {instructions}\n\n"
            "## Cambios detectados\n\n"
            f"{self._render_markdown_block(self.diff_stat, language='text') if self.diff_stat else 'Sin diff disponible'}\n\n"
            "## Diff de la rama\n\n"
            f"{self._render_markdown_block(self.diff_patch, language='diff') if self.diff_patch else 'Sin diff disponible'}\n\n"
            "## Cambios pendientes\n\n"
            f"{self._render_pending_changes_section()}\n\n"
            "## Archivos revisados\n\n"
            f"{chr(10).join(f'- {path}' for path in self.changed_files) if self.changed_files else '- Sin archivos cambiados'}\n\n"
            "## Pasos registrados\n\n"
            f"{steps_section}\n\n"
            "## Informe final\n\n"
            f"{report}\n"
        )

    def _collect_explain_snapshot(self):
        root = Path(self.project_path)
        return {
            "project_path": self.project_path,
            "branch_name": self.branch_name,
            "head_sha": self.git.get_head_sha(),
            "project_info": self.project_info or {},
            "tree": self._build_repo_tree(root),
            "top_level_entries": self._collect_top_level_entries(root),
            "documentation_files": self._collect_documentation_files(root),
            "python_modules": self._collect_python_modules(root),
            "test_files": self._collect_test_files(root),
            "source_files": self._collect_source_files(root),
            "setup_files": self._collect_setup_files(root),
        }

    def _build_explain_sections(self, snapshot):
        return [
            {
                "id": "resumen-ejecutivo",
                "title": "Resumen ejecutivo",
                "prompt": self._build_explain_section_prompt(
                    snapshot,
                    "Resumen ejecutivo",
                    "Redacta una introduccion breve del repositorio, el alcance del informe y la lectura rapida del proyecto. "
                    "Destaca el objetivo general del codigo y evita inventar funcionalidades no observadas.",
                ),
                "markdown": "",
            },
            {
                "id": "stack",
                "title": "Stack",
                "prompt": self._build_explain_section_prompt(
                    snapshot,
                    "Stack",
                    "Describe el stack detectado y la evidencia concreta disponible en el arbol del repositorio. "
                    "Incluye tipo de proyecto, runner de pruebas, archivos de empaquetado o entrada y modulos principales.",
                ),
                "markdown": "",
            },
            {
                "id": "arquitectura",
                "title": "Arquitectura",
                "prompt": self._build_explain_section_prompt(
                    snapshot,
                    "Arquitectura",
                    "Analiza la estructura del repositorio y las responsabilidades principales de sus modulos. "
                    "Explica como cooperan CLI, orquestador, persistencia, Git, detector de proyecto y reporting.",
                ),
                "markdown": "",
            },
            {
                "id": "diseno",
                "title": "Diseno",
                "prompt": self._build_explain_section_prompt(
                    snapshot,
                    "Diseno",
                    "Analiza modularidad, separacion de responsabilidades, trazabilidad de sesiones y experiencia de uso. "
                    "Incluye observaciones sobre el HTML autocontenido y las limitaciones del enfoque heuristico.",
                ),
                "markdown": "",
            },
            {
                "id": "funcionalidad",
                "title": "Funcionalidad",
                "prompt": self._build_explain_section_prompt(
                    snapshot,
                    "Funcionalidad",
                    "Resume la funcionalidad observable del repositorio y los comandos o flujos expuestos por la CLI. "
                    "Incluye para que sirve el proyecto y que problemas resuelve.",
                ),
                "markdown": "",
            },
            {
                "id": "tests",
                "title": "Tests",
                "prompt": self._build_explain_section_prompt(
                    snapshot,
                    "Tests",
                    "Inventaria las pruebas detectadas y explica el enfoque de testing que se deduce del repositorio. "
                    "Separa el inventario del analisis del estilo de pruebas y de los huecos potenciales.",
                ),
                "markdown": "",
            },
            {
                "id": "riesgos",
                "title": "Riesgos y conclusiones",
                "prompt": self._build_explain_section_prompt(
                    snapshot,
                    "Riesgos y conclusiones",
                    "Cierra el informe con riesgos detectados, limitaciones del analisis y una conclusion ejecutiva. "
                    "Indica de forma explicita si el repositorio parece coherente con el flujo de autodev.",
                ),
                "markdown": "",
            },
        ]

    def _compose_explain_report(self, snapshot, sections):
        section_lines = []
        for section in sections or []:
            section_lines.append(f"## {section['title']}\n\n{section['markdown'].strip()}\n")
        sections_text = "\n".join(section_lines)
        project_info = snapshot.get("project_info", {})
        return (
            "# Informe de exploracion del repositorio\n\n"
            f"- Session ID: {self.session_id}\n"
            f"- Branch: {self.branch_name or 'detached'}\n"
            f"- Project path: {self.project_path}\n"
            f"- Stack: {project_info.get('project_type', 'desconocido')} con {project_info.get('test_runner', 'desconocido')}\n"
            f"- Head SHA: {snapshot.get('head_sha') or 'n/a'}\n\n"
            "## Secciones\n\n"
            + "\n".join(f"- [{section['title']}](#{self._slugify_label(section['title'])})" for section in sections)
            + "\n\n"
            + sections_text
        )

    def _build_explain_section_prompt(self, snapshot, section_title, focus):
        project_info = snapshot.get("project_info", {})
        tree = snapshot.get("tree", [])
        top_level_entries = snapshot.get("top_level_entries", [])
        documentation_files = snapshot.get("documentation_files", [])
        python_modules = snapshot.get("python_modules", [])
        test_files = snapshot.get("test_files", [])
        source_files = snapshot.get("source_files", [])
        setup_files = snapshot.get("setup_files", [])

        return (
            "Actua como un analista tecnico senior y genera una unica seccion de un informe Markdown.\n"
            f"Seccion a redactar: {section_title}\n"
            f"Foco de la seccion: {focus}\n"
            f"Contexto del proyecto: {project_info.get('project_type', 'desconocido')} usando {project_info.get('test_runner', 'desconocido')}.\n"
            f"Ruta del proyecto: {self.project_path}\n"
            f"Rama actual: {snapshot.get('branch_name') or 'detached'}\n"
            f"Head SHA: {snapshot.get('head_sha') or 'n/a'}\n\n"
            "Arbol resumido del repositorio:\n"
            f"{self._format_bullet_block(tree, fallback='Sin arbol disponible.')}\n\n"
            "Entradas de primer nivel:\n"
            f"{self._format_bullet_block(top_level_entries, fallback='Sin entradas detectadas.')}\n\n"
            "Documentacion detectada:\n"
            f"{self._format_bullet_block([doc['name'] for doc in documentation_files], fallback='No se detecto documentacion de referencia.')}\n\n"
            "Modulos Python principales:\n"
            f"{self._format_bullet_block(python_modules, fallback='No se detectaron modulos Python.')}\n\n"
            "Archivos de test:\n"
            f"{self._format_bullet_block(test_files, fallback='No se detectaron pruebas.')}\n\n"
            "Archivos fuente o de empaquetado relevantes:\n"
            f"{self._format_bullet_block(source_files, fallback='No se detectaron archivos fuente o de empaquetado.')}\n\n"
            "Archivos de setup detectados:\n"
            f"{self._format_bullet_block(setup_files, fallback='No se detectaron archivos de setup.')}\n\n"
            "Instrucciones de salida:\n"
            "- Devuelve solo Markdown.\n"
            "- No repitas el titulo principal de la seccion.\n"
            "- Usa subtitulos, listas o notas solo si aportan claridad.\n"
            "- No afirmes detalles no respaldados por el contexto proporcionado.\n"
            "- Mantén el tono de un informe tecnico conciso y riguroso."
        )

    def _build_explain_overview_section(self, snapshot):
        project_info = snapshot.get("project_info", {})
        docs = snapshot.get("documentation_files", [])
        tests = snapshot.get("test_files", [])
        return (
            "### Alcance\n"
            "Este informe describe el estado actual del repositorio sin modificar archivos.\n\n"
            "### Datos clave\n"
            f"- Tipo de proyecto: {project_info.get('project_type', 'desconocido')}\n"
            f"- Test runner: {project_info.get('test_runner', 'desconocido')}\n"
            f"- Rama actual: {snapshot.get('branch_name') or 'detached'}\n"
            f"- Archivos de documentacion detectados: {len(docs)}\n"
            f"- Archivos de test detectados: {len(tests)}\n\n"
            "### Lectura rapida\n"
            "El repositorio esta organizado alrededor de una CLI, un orquestador central, adaptadores de IA, persistencia local y utilidades de reporte."
        )

    def _build_explain_stack_section(self, snapshot):
        project_info = snapshot.get("project_info", {})
        setup_files = snapshot.get("setup_files", [])
        python_modules = snapshot.get("python_modules", [])
        return (
            "### Stack detectado\n"
            f"- Proyecto: {project_info.get('project_type', 'desconocido')}\n"
            f"- Runner de pruebas: {project_info.get('test_runner', 'desconocido')}\n"
            f"- Archivos de empaquetado o entrada: {', '.join(setup_files) if setup_files else 'No detectados'}\n\n"
            "### Evidencias relevantes\n"
            f"- Modulos principales del paquete: {', '.join(python_modules) if python_modules else 'No detectados'}\n"
            f"- Documentacion base: {', '.join(doc['name'] for doc in snapshot.get('documentation_files', [])) or 'No detectada'}"
        )

    def _build_explain_architecture_section(self, snapshot):
        tree = snapshot.get("tree", [])
        return (
            "### Estructura observada\n"
            f"{self._format_bullet_block(tree, fallback='No se pudo construir un arbol del repositorio.')}\n\n"
            "### Componentes principales\n"
            "- `autodev_cli/cli.py`: entrada de comandos y despacho de flujos.\n"
            "- `autodev_cli/developer_orchestrator.py`: coordinacion de sesiones, prompts y persistencia.\n"
            "- `autodev_cli/project_detector.py`: deteccion del stack y del runner.\n"
            "- `autodev_cli/git_manager.py`: aislamiento Git y operaciones de commit/push.\n"
            "- `autodev_cli/history_manager.py`: almacenamiento en SQLite de sesiones y pasos.\n"
            "- `autodev_cli/reporting.py`: renderizado Markdown/HTML de los reportes.\n"
            "- `autodev_cli/codex_client.py` y `autodev_cli/gemini_client.py`: adaptadores de agentes.\n\n"
            "### Lectura arquitectonica\n"
            "La base es modular y orientada a responsabilidades claras, aunque el orquestador concentra bastante logica de alto nivel."
        )

    def _build_explain_design_section(self, snapshot):
        docs = snapshot.get("documentation_files", [])
        return (
            "### Principios que se observan\n"
            "- Separacion entre orquestacion, persistencia, Git, deteccion de stack y renderizado.\n"
            "- Trazabilidad de cada ejecucion mediante carpeta de sesion y base SQLite.\n"
            "- Flujo controlado por fases para mantener el contexto de trabajo.\n\n"
            "### Observaciones de diseno\n"
            "- El sistema favorece extensibilidad por comandos y flujos.\n"
            "- La documentacion se integra como parte del contexto operativo cuando existe.\n"
            "- El HTML de salida debe ser autocontenido para no depender de recursos externos.\n\n"
            "### Documentacion presente\n"
            f"{self._format_bullet_block([doc['name'] for doc in docs], fallback='No se detecto documentacion de referencia.')}"
        )

    def _build_explain_functionality_section(self, snapshot):
        test_files = snapshot.get("test_files", [])
        return (
            "### Funcionalidad observable\n"
            "- `-dev`: planifica, desarrolla, documenta, prueba y valida cambios.\n"
            "- `-ut`: revisa cobertura sobre una rama frente a su base y remedia gaps.\n"
            "- `push`: genera commit y push de cambios locales.\n"
            "- `history`: consulta sesiones y pasos guardados.\n"
            "- `--explain/-e`: explora el repositorio y produce un informe tecnico completo.\n\n"
            "### Alcance funcional del repositorio\n"
            "El proyecto se centra en automatizar trabajo asistido por IA sobre repositorios Git con trazabilidad local.\n\n"
            "### Areas relacionadas con pruebas\n"
            f"{self._format_bullet_block(test_files, fallback='No se detectaron archivos de prueba.')}"
        )

    def _build_explain_tests_section(self, snapshot):
        test_files = snapshot.get("test_files", [])
        frameworks = self._infer_test_frameworks(test_files)
        return (
            "### Inventario de pruebas\n"
            f"{self._format_bullet_block(test_files, fallback='No se detectaron pruebas en el arbol del proyecto.')}\n\n"
            "### Enfoque de testing\n"
            f"{self._format_bullet_block(frameworks, fallback='No se pudo inferir un framework de pruebas.')}\n\n"
            "### Lectura de calidad\n"
            "La suite parece mezclar estilos de prueba orientados a pytest y unittest, por lo que conviene mantener la compatibilidad entre ambos."
        )

    def _build_explain_risks_section(self, snapshot):
        return (
            "### Riesgos\n"
            "- El analisis es heuristico y puede subestimar proyectos grandes o muy heterogeneos.\n"
            "- El HTML depende de un renderizador propio; si crece el alcance del Markdown, habra que reforzarlo.\n"
            "- La presencia de tests en varios estilos puede exigir cuidado en futuras ampliaciones.\n\n"
            "### Conclusion\n"
            "El repositorio muestra una arquitectura util y trazable para automatizar tareas de desarrollo asistido, con un nuevo flujo de exploracion que encaja sin migraciones de datos."
        )

    def _collect_top_level_entries(self, root):
        entries = []
        for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
            if self._should_skip_path(path):
                continue
            entries.append(path.name + ("/" if path.is_dir() else ""))
        return entries

    def _build_repo_tree(self, root, max_depth=2):
        lines = []

        def walk(current, depth):
            if depth > max_depth:
                return
            try:
                children = sorted(current.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
            except OSError:
                return
            for child in children:
                if self._should_skip_path(child):
                    continue
                prefix = "  " * depth + "- "
                lines.append(f"{prefix}{child.name}{'/' if child.is_dir() else ''}")
                if child.is_dir():
                    walk(child, depth + 1)

        walk(root, 0)
        return lines[:120]

    def _collect_documentation_files(self, root):
        docs = []
        for name in ["README.md", "ARCHITECTURE.md", "GEMINI.md", "AGENTS.md"]:
            path = root / name
            if path.exists():
                docs.append({"name": name, "path": str(path)})
        return docs

    def _collect_python_modules(self, root):
        modules_dir = root / "autodev_cli"
        if not modules_dir.exists():
            return []
        modules = []
        for path in sorted(modules_dir.glob("*.py")):
            if path.name == "__init__.py":
                continue
            modules.append(f"autodev_cli/{path.name}")
        return modules

    def _collect_test_files(self, root):
        tests_dir = root / "tests"
        if not tests_dir.exists():
            return []
        files = []
        for path in sorted(tests_dir.rglob("test_*.py")):
            files.append(str(path.relative_to(root)))
        return files

    def _collect_source_files(self, root):
        source_files = []
        for name in ["setup.py", "pyproject.toml", "setup.cfg"]:
            path = root / name
            if path.exists():
                source_files.append(name)
        return source_files

    def _collect_setup_files(self, root):
        setup_files = []
        for name in ["setup.py", "pyproject.toml", "setup.cfg", "requirements.txt"]:
            if (root / name).exists():
                setup_files.append(name)
        return setup_files

    def _infer_test_frameworks(self, test_files):
        frameworks = []
        if any("pytest" in file for file in test_files):
            frameworks.append("pytest-style tests detected by file discovery")
        if test_files:
            frameworks.append("unittest-compatible suite detected")
        return frameworks

    def _should_skip_path(self, path):
        skip_names = {
            ".git",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".tox",
            ".venv",
            "venv",
            "env",
            "build",
            "dist",
            ".eggs",
            "node_modules",
            "results",
        }
        return path.name in skip_names or path.name.startswith(".") and path.name not in {".", ".."}

    def _format_bullet_block(self, items, fallback="Sin elementos disponibles."):
        if not items:
            return fallback
        return "\n".join(f"- {item}" for item in items)

    def _write_session_manifest(self, status):
        payload = {
            "session_id": self.session_id,
            "branch_name": self.branch_name,
            "workflow": self.workflow_name,
            "base_branch": self.base_branch_name,
            "merge_base_sha": self.merge_base_sha,
            "project_path": self.project_path,
            "agent": self.agent_name,
            "status": status,
            "results_dir": self.results_dir,
            "log_path": self.log_file,
            "summary_md_path": self.summary_md_path,
            "summary_html_path": self.summary_html_path,
            "agent_session_id": self._get_agent_session_id(),
            "head_sha": self.git.get_head_sha(),
            "reference_docs": [doc["name"] for doc in self.reference_docs],
        }
        self.storage.write_json(self.storage.session_file(self.session_id, "session.json"), payload)

    def _finalize_session(self, status):
        if not self.session_id:
            return
        try:
            self.history.close_session(self.session_id, status=status)
            self.history.update_session(
                self.session_id,
                status=status,
                summary_md_path=self.summary_md_path,
                summary_html_path=self.summary_html_path,
                results_dir=self.results_dir,
                branch_name=self.branch_name,
                workflow=self.workflow_name,
                base_branch=self.base_branch_name,
                merge_base_sha=self.merge_base_sha,
                agent_session_id=self._get_agent_session_id(),
                head_sha=self.git.get_head_sha(),
            )
            self._write_session_manifest(status=status)
        except Exception as exc:
            print(f"WARNING: No se pudo finalizar la sesion {self.session_id}: {exc}")

    def _reference_doc_candidates(self):
        return [
            "README.md",
            "README",
            "GEMINI.md",
            "gemini.md",
            "AGENTS.md",
            "agents.md",
        ]

    def _load_reference_docs_into_session(self):
        self.reference_docs = []
        self.reference_docs_context = ""

        blocks = []
        for filename in self._reference_doc_candidates():
            source_path = os.path.join(self.project_path, filename)
            if not os.path.isfile(source_path):
                continue

            try:
                with open(source_path, "r", encoding="utf-8") as handle:
                    content = handle.read()
            except OSError as exc:
                print(f"WARNING: No se pudo leer {source_path}: {exc}")
                continue

            session_path = self.storage.session_file(self.session_id, f"reference_docs/{filename}")
            self.storage.write_text(session_path, content)
            self.reference_docs.append(
                {
                    "name": filename,
                    "source_path": source_path,
                    "session_path": str(session_path),
                }
            )
            blocks.append(f"## {filename}\n{content}")

        self.reference_docs_context = "\n\n".join(blocks)
        if self.reference_docs:
            self.history.update_session(
                self.session_id,
                status="running",
            )

    def _restore_reference_docs_from_session(self):
        self.reference_docs = []
        self.reference_docs_context = ""

        session_reference_dir = self.storage.session_file(self.session_id, "reference_docs")
        if not session_reference_dir.exists():
            return

        blocks = []
        for filename in self._reference_doc_candidates():
            session_path = session_reference_dir / filename
            if not session_path.exists():
                continue
            try:
                content = session_path.read_text(encoding="utf-8")
            except OSError:
                continue

            self.reference_docs.append(
                {
                    "name": filename,
                    "source_path": os.path.join(self.project_path, filename),
                    "session_path": str(session_path),
                }
            )
            blocks.append(f"## {filename}\n{content}")

        self.reference_docs_context = "\n\n".join(blocks)

    def _build_reference_docs_context(self):
        if not self.reference_docs_context:
            return "Documentacion de referencia cargada: ninguna."
        return "Documentacion de referencia cargada en la sesion:\n" + self.reference_docs_context

    def _render_markdown_block(self, content, language=""):
        content = (content or "").strip()
        if not content:
            return ""
        fence = f"```{language}".rstrip()
        return f"{fence}\n{content}\n```"

    def _render_pending_changes_section(self):
        sections = []
        if self.pending_status_lines:
            sections.append("### Estado\n" + self._render_markdown_block("\n".join(self.pending_status_lines), language="text"))
        if self.pending_staged_diff_stat:
            sections.append("### Staged stat\n" + self._render_markdown_block(self.pending_staged_diff_stat, language="text"))
        if self.pending_staged_diff_name_status:
            sections.append(
                "### Staged name-status\n"
                + self._render_markdown_block(self.pending_staged_diff_name_status, language="text")
            )
        if self.pending_staged_diff_patch:
            sections.append("### Staged diff\n" + self._render_markdown_block(self.pending_staged_diff_patch, language="diff"))
        if self.pending_unstaged_diff_stat:
            sections.append("### Unstaged stat\n" + self._render_markdown_block(self.pending_unstaged_diff_stat, language="text"))
        if self.pending_unstaged_diff_name_status:
            sections.append(
                "### Unstaged name-status\n"
                + self._render_markdown_block(self.pending_unstaged_diff_name_status, language="text")
            )
        if self.pending_unstaged_diff_patch:
            sections.append(
                "### Unstaged diff\n" + self._render_markdown_block(self.pending_unstaged_diff_patch, language="diff")
            )
        if self.pending_untracked_files:
            sections.append(
                "### Untracked\n"
                + self._render_markdown_block("\n".join(f"- {path}" for path in self.pending_untracked_files), language="text")
            )
        if not sections:
            return "Sin cambios pendientes."
        return "\n\n".join(sections)
