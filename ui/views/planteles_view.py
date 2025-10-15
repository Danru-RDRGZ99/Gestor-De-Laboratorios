import flet as ft
from sqlalchemy.exc import SQLAlchemyError
from core.db import SessionLocal
from core.models import Plantel, Laboratorio
from ui.components.cards import Card
from ui.components.inputs import TextField, Dropdown
from ui.components.buttons import Primary, Ghost, Danger, Icon

def PlantelesView(page: ft.Page):
    db = SessionLocal()
    u = page.session.get("user")

    # Estado inline (como calendarios)
    state = {
        "edit_for": None,        # id de plantel en edición
        "delete_for": None,      # id de plantel con panel de eliminación abierto
        "confirm_lab": None,     # id de laboratorio que pide confirmación de eliminación
    }

    # Controles de creación (arriba)
    nombre = TextField("Nombre", expand=True)
    direccion = TextField("Dirección", expand=True)
    info = ft.Text("")
    list_panel = ft.Column(spacing=12)  # 👈 sin expand, para que se ancle arriba

    def reload_info(msg: str | None = None):
        if msg is not None:
            info.value = msg
        render_list()

    # ------------------ Helpers de datos ------------------
    def get_planteles():
        return db.query(Plantel).order_by(Plantel.id.desc()).all()

    def get_labs(pid: int):
        return db.query(Laboratorio).filter(Laboratorio.plantel_id == pid).order_by(Laboratorio.id.asc()).all()

    def get_other_planteles(pid: int):
        return db.query(Plantel).filter(Plantel.id != pid).order_by(Plantel.nombre.asc()).all()

    # ------------------ Acciones CRUD ------------------
    def add_plantel(e):
        if u["rol"] != "admin":
            reload_info("Solo el administrador puede crear planteles"); return
        if not nombre.value or not direccion.value:
            reload_info("Completa los campos"); return
        db.add(Plantel(nombre=nombre.value.strip(), direccion=direccion.value.strip()))
        db.commit()
        nombre.value = ""; direccion.value = ""
        reload_info("Plantel guardado")

    def save_edit(pid: int, n_val: str, d_val: str):
        if u["rol"] != "admin":
            reload_info("No autorizado"); return
        p = db.get(Plantel, pid)
        if not p:
            reload_info("Plantel no encontrado"); return
        p.nombre = (n_val or "").strip()
        p.direccion = (d_val or "").strip()
        db.commit()
        state["edit_for"] = None
        reload_info("Plantel actualizado")

    def open_edit(pid: int):
        if state["edit_for"] == pid:
            state["edit_for"] = None
        else:
            state["edit_for"] = pid
            state["delete_for"] = None
        reload_info(None)

    def toggle_delete_panel(pid: int):
        if state["delete_for"] == pid:
            state["delete_for"] = None
        else:
            state["delete_for"] = pid
            state["edit_for"] = None
        state["confirm_lab"] = None
        reload_info(None)

    def reassign_lab(lid: int, dest_pid: int):
        if u["rol"] != "admin":
            reload_info("No autorizado"); return
        lab = db.get(Laboratorio, lid)
        if not lab:
            reload_info("Laboratorio no encontrado"); return
        lab.plantel_id = dest_pid
        db.commit()
        reload_info("Laboratorio reubicado")

    def move_all(pid_from: int, dest_pid: int):
        if u["rol"] != "admin":
            reload_info("No autorizado"); return
        labs = get_labs(pid_from)
        for lab in labs:
            lab.plantel_id = dest_pid
        db.commit()
        reload_info("Todos los laboratorios fueron reubicados")

    def ask_delete_lab(lid: int):
        state["confirm_lab"] = None if state["confirm_lab"] == lid else lid
        render_list()

    def do_delete_lab(lid: int):
        if u["rol"] != "admin":
            reload_info("No autorizado"); return
        lab = db.get(Laboratorio, lid)
        if not lab:
            reload_info("Laboratorio no encontrado"); return
        try:
            db.delete(lab)
            db.commit()
            state["confirm_lab"] = None
            reload_info("Laboratorio eliminado")
        except SQLAlchemyError as ex:
            db.rollback()
            reload_info(f"Error al eliminar laboratorio: {ex.__class__.__name__}")

    def try_delete_plantel(pid: int):
        if u["rol"] != "admin":
            reload_info("No autorizado"); return
        labs_count = db.query(Laboratorio).filter(Laboratorio.plantel_id == pid).count()
        if labs_count > 0:
            reload_info(f"No se puede eliminar: hay {labs_count} laboratorio(s) asociados.")
            return
        p = db.get(Plantel, pid)
        if not p:
            reload_info("Plantel no encontrado"); return
        try:
            db.delete(p)
            db.commit()
            state["delete_for"] = None
            reload_info("Plantel eliminado")
        except SQLAlchemyError as ex:
            db.rollback()
            reload_info(f"Error al eliminar: {ex.__class__.__name__}")

    # ------------------ Render por Plantel ------------------
    def plantel_card(p: Plantel) -> ft.Control:
        title = ft.Text(f"{p.nombre}", size=16, weight=ft.FontWeight.W_600)
        subtitle = ft.Text(p.direccion or "-", size=12, opacity=0.85)

        btns = ft.Row(spacing=6)
        if u["rol"] == "admin":
            btns.controls = [
                Icon(ft.Icons.EDIT, "Editar", on_click=lambda e, pid=p.id: open_edit(pid)),
                Icon(ft.Icons.DELETE, "Eliminar", on_click=lambda e, pid=p.id: toggle_delete_panel(pid)),
            ]

        header = ft.Row(
            [ft.Column([title, subtitle], spacing=2, expand=True), btns],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        content = ft.Column(spacing=12)

        # --- Modo edición inline ---
        if state["edit_for"] == p.id and u["rol"] == "admin":
            n = TextField("Nombre", value=p.nombre, expand=True)
            d = TextField("Dirección", value=p.direccion, expand=True)
            actions = ft.Row(
                [
                    Primary("Guardar", on_click=lambda e, pid=p.id, _n=n, _d=d: save_edit(pid, _n.value, _d.value), width=130, height=40),
                    Ghost("Cancelar", on_click=lambda e: open_edit(p.id), width=120, height=40),
                ],
                spacing=8,
            )
            content.controls.append(ft.Column([n, d, actions], spacing=8, tight=True))

        # --- Panel eliminación / gestión de labs inline ---
        if state["delete_for"] == p.id and u["rol"] == "admin":
            labs = get_labs(p.id)
            others = get_other_planteles(p.id)
            opts = [(str(op.id), op.nombre) for op in others]

            dd_all = Dropdown("Mover todos a", options=opts, width=260)
            btn_move_all = Primary(
                "Mover todos",
                on_click=lambda e, _pid=p.id, _dd=dd_all: (move_all(_pid, int(_dd.value)) if _dd.value else None),
                width=150, height=40
            )
            btn_delete_plantel = Primary("Eliminar plantel ahora",
                                         on_click=lambda e, _pid=p.id: try_delete_plantel(_pid),
                                         width=220, height=42)
            btn_delete_plantel.disabled = len(labs) > 0

            head = ft.Row(
                [
                    ft.Text("Gestión para eliminar plantel", weight=ft.FontWeight.W_600),
                    ft.Container(expand=True),
                    dd_all, btn_move_all,
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            content.controls.append(head)
            content.controls.append(ft.Divider(opacity=0.15))

            if not labs:
                content.controls.append(ft.Text("Sin laboratorios asociados. Ya puedes eliminar el plantel.", size=12))

            for lab in labs:
                dd = Dropdown("Mover a", options=opts, width=260)
                move_btn = Primary("Reubicar",
                                   on_click=lambda e, _lid=lab.id, _dd=dd: (reassign_lab(_lid, int(_dd.value)) if _dd.value else None),
                                   width=120, height=38)

                if state["confirm_lab"] == lab.id:
                    actions = ft.Row(
                        [
                            Danger("Confirmar eliminación", on_click=lambda e, _lid=lab.id: do_delete_lab(_lid), width=200, height=38),
                            Ghost("Volver", on_click=lambda e: (state.__setitem__("confirm_lab", None), render_list()), width=100, height=38),
                        ],
                        spacing=8,
                    )
                else:
                    actions = ft.Row(
                        [
                            move_btn,
                            Danger("Eliminar", on_click=lambda e, _lid=lab.id: ask_delete_lab(_lid), width=120, height=38),
                        ],
                        spacing=8,
                    )

                row = ft.Column(
                    [
                        ft.Text(f"#{lab.id} · {lab.nombre}", weight=ft.FontWeight.W_600),
                        ft.Row(
                            [
                                ft.Text(f"Ubicación: {lab.ubicacion or '-'}"),
                                ft.Text(f"Capacidad: {lab.capacidad or '-'}"),
                            ],
                            spacing=16,
                        ),
                        ft.Row([dd, actions], spacing=8),
                        ft.Divider(opacity=0.1),
                    ],
                    spacing=6,
                    tight=True,
                )
                content.controls.append(row)

            footer = ft.Row(
                [
                    btn_delete_plantel,
                    Ghost("Cerrar gestión", on_click=lambda e: toggle_delete_panel(p.id), width=150, height=40),
                ],
                spacing=10,
            )
            content.controls.append(footer)

        body = ft.Column([header, content], spacing=10)
        return Card(body, padding=14)

    # ------------------ Render general ------------------
    def render_list():
        list_panel.controls.clear()
        for p in get_planteles():
            list_panel.controls.append(plantel_card(p))
        page.update()

    # Header: creación (solo admin muestra botón "Agregar")
    actions = [nombre, direccion]
    if u["rol"] == "admin":
        actions.append(Primary("Agregar", on_click=add_plantel, width=160, height=44))

    # Vista principal anclada arriba
    render_list()
    return ft.Column(
        [
            ft.Text("Planteles", size=20, weight=ft.FontWeight.BOLD),
            Card(ft.Row(actions, wrap=False, alignment=ft.MainAxisAlignment.START), padding=14),
            info,
            ft.Divider(),
            list_panel,
        ],
        expand=True,
        alignment=ft.MainAxisAlignment.START,  # 👈 anclado arriba
        scroll=ft.ScrollMode.AUTO,
        spacing=10,
    )
