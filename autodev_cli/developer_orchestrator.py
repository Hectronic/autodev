import datetime
import os
import uuid

from .codex_client import CodexClient
from .gemini_client import GeminiClient
from .git_manager import GitManager
from .history_manager import HistoryManager
from .project_detector import ProjectDetector
from .reporting import open_html_report, write_html_report
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
        self.workflow_name = "development"
        self.resume_mode = False
        self.session_dir = None
        self.summary_md_path = None
        self.summary_html_path = None

    def run(self, instructions, no_commit=False):
        instructions = (instructions or "").strip()
        if not instructions:
            print("ERROR: Debes proporcionar instrucciones de desarrollo con --instructions.")
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

            if not no_commit:
                commit_message = f"autodev: {self._shorten_commit_message(instructions)}"
                self.git.commit_changes(commit_message)
                print(f"Development flow finished for branch {self.branch_name}")
            else:
                print(
                    f"Development flow finished. Changes are ready for review in branch {self.branch_name} (NO COMMIT MADE)."
                )

            print(f"Session ID: {self.session_id}")
            print(f"Branch: {self.branch_name}")
            print(f"Log and report saved in: {self.results_dir}")
        except Exception:
            session_status = "failed"
            raise
        finally:
            self._finalize_session(session_status)

    def run_unit_test(self, base_branch=None, instructions=None, no_commit=False):
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

            if not no_commit:
                commit_message = f"autodev-ut: {self._shorten_commit_message(self.base_branch_name or self.branch_name)}"
                self.git.commit_changes(commit_message)
                print(f"Unit test review finished for branch {self.branch_name}")
            else:
                print(
                    f"Unit test review finished. Changes are ready for review in branch {self.branch_name} (NO COMMIT MADE)."
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
        self._sync_client_log_file()
        if hasattr(self.ai, "has_started"):
            self.ai.has_started = True
        if hasattr(self.ai, "session_id") and session_row.get("agent_session_id"):
            self.ai.session_id = session_row["agent_session_id"]

    def _slugify_label(self, label):
        return "".join(ch.lower() if ch.isalnum() else "_" for ch in label).strip("_")

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
            f"{self.diff_stat or 'Sin diff disponible'}\n\n"
            "## Archivos revisados\n\n"
            f"{chr(10).join(f'- {path}' for path in self.changed_files) if self.changed_files else '- Sin archivos cambiados'}\n\n"
            "## Pasos registrados\n\n"
            f"{steps_section}\n\n"
            "## Informe final\n\n"
            f"{report}\n"
        )

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
