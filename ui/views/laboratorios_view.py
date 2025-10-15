import flet as ft
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from core.db import SessionLocal
from core.models import Laboratorio, Plantel, Reserva
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
# Recurso es opcional: lo usamos si existe en tu modelo
try:
    from core.models import Recurso  # type: ignore
    HAVE_RECURSO = True
except Exception:
    HAVE_RECURSO = False

from ui.components.cards import Card
from ui.components.inputs import TextField  # 👈 OJO: quitamos el Dropdown envuelto
from ui.components.buttons import Primary, Ghost, Danger, Icon


def LaboratoriosView(page: ft.Page):
    db = SessionLocal()
    u = page.session.get("user")

    # --- Estado inline ---
    state = {
        "edit_for": None,            # id de lab en edición
        "delete_for": None,          # id de lab en gestión de eliminación
        "confirm_recurso": None,     # id de recurso a eliminar (confirmación inline)
        "confirm_reserva": None,     # id de reserva a cancelar (confirmación inline)
        "confirm_reservas_all": None # id de lab si se confirma "cancelar todas"
    }

    # --- Helpers de datos de plantel ---
    SUPPORT_PLANTEL = hasattr(Laboratorio, "plantel_id")

    def get_planteles():
        return db.query(Plantel).order_by(Plantel.nombre.asc()).all()

    def plantel_options():
        # Devuelve opciones nativas para ft.Dropdown
        return [ft.dropdown.Option(key=str(p.id), text=p.nombre) for p in get_planteles()]

    def make_plantel_dd(initial_value: int | None = None, width: int = 260) -> ft.Dropdown:
        return ft.Dropdown(
            label="Plantel",
            options=plantel_options(),
            width=width,
            value=(str(initial_value) if initial_value else None)
        )

    # --- Controles de creación ---
    nombre = TextField("Nombre", expand=True)
    ubicacion = TextField("Ubicación", expand=True)
    capacidad = TextField("Capacidad", expand=True)
    dd_plantel_add: ft.Dropdown | None = make_plantel_dd() if SUPPORT_PLANTEL else None

    info = ft.Text("")
    list_panel = ft.Column(spacing=12)

    def reload_info(msg: str | None = None):
        if msg is not None:
            info.value = msg
        # Refresca opciones del combo de alta si hay cambios en planteles
        if SUPPORT_PLANTEL and dd_plantel_add is not None:
            dd_plantel_add.options = plantel_options()
        render_list()

    # ---------------- Helpers de datos ----------------
    def get_labs():
        return db.query(Laboratorio).order_by(Laboratorio.id.desc()).all()

    def get_recursos(lid: int):
        if not HAVE_RECURSO:
            return []
        return db.query(Recurso).filter(Recurso.laboratorio_id == lid).order_by(Recurso.id.asc()).all()

    def get_future_reservas(lid: int):
        now = datetime.now()
        return (
            db.query(Reserva)
            .filter(
                Reserva.laboratorio_id == lid,
                Reserva.estado != "cancelada",
                Reserva.fin >= now,
            )
            .order_by(Reserva.inicio.asc())
            .all()
        )

    def set_if_exists(obj, attr: str, value):
        if hasattr(obj, attr):
            setattr(obj, attr, value)

    # ---------------- Acciones: crear / editar ----------------
    def add_lab(e):
        if u["rol"] != "admin":
            reload_info("Solo el administrador puede crear laboratorios"); return
        if not nombre.value:
            reload_info("Escribe el nombre"); return

        if SUPPORT_PLANTEL and (dd_plantel_add is None or not dd_plantel_add.value):
            reload_info("Selecciona un plantel"); return

        lab = Laboratorio(nombre=nombre.value.strip())
        set_if_exists(lab, "ubicacion", (ubicacion.value or "").strip())
        # capacidad numérica si existe el campo
        if hasattr(lab, "capacidad"):
            try:
                set_if_exists(lab, "capacidad", int(capacidad.value))  # type: ignore
            except Exception:
                set_if_exists(lab, "capacidad", None)

        # Asignar plantel si corresponde
        if SUPPORT_PLANTEL and dd_plantel_add is not None and dd_plantel_add.value:
            try:
                lab.plantel_id = int(dd_plantel_add.value)  # type: ignore
            except Exception:
                pass

        db.add(lab)
        db.commit()
        nombre.value = ""; ubicacion.value = ""; capacidad.value = ""
        if SUPPORT_PLANTEL and dd_plantel_add is not None:
            dd_plantel_add.value = None
        reload_info("Laboratorio creado")

    def save_edit(lid: int, vals: dict):
        if u["rol"] != "admin":
            reload_info("No autorizado"); return
        lab = db.get(Laboratorio, lid)
        if not lab:
            reload_info("Laboratorio no encontrado"); return
        set_if_exists(lab, "nombre", (vals.get("nombre") or "").strip())
        set_if_exists(lab, "ubicacion", (vals.get("ubicacion") or "").strip())
        if "capacidad" in vals and hasattr(lab, "capacidad"):
            try:
                set_if_exists(lab, "capacidad", int(vals["capacidad"]))  # type: ignore
            except Exception:
                set_if_exists(lab, "capacidad", None)
        # cambio de plantel (si columna existe)
        if "plantel_id" in vals and hasattr(lab, "plantel_id") and vals["plantel_id"]:
            try:
                set_if_exists(lab, "plantel_id", int(vals["plantel_id"]))  # type: ignore
            except Exception:
                pass
        db.commit()
        state["edit_for"] = None
        reload_info("Laboratorio actualizado")

    def open_edit(lid: int):
        state["edit_for"] = None if state["edit_for"] == lid else lid
        state["delete_for"] = None
        reload_info(None)

    # ---------------- Acciones: recursos ----------------
    def move_recurso(rid: int, dest_lid: int):
        if u["rol"] != "admin":
            reload_info("No autorizado"); return
        if not HAVE_RECURSO:
            reload_info("Modelo Recurso no disponible"); return
        r = db.get(Recurso, rid)  # type: ignore
        if not r:
            reload_info("Recurso no encontrado"); return
        r.laboratorio_id = dest_lid
        db.commit()
        reload_info("Recurso reubicado")

    def ask_delete_recurso(rid: int):
        state["confirm_recurso"] = None if state["confirm_recurso"] == rid else rid
        render_list()

    def do_delete_recurso(rid: int):
        if u["rol"] != "admin":
            reload_info("No autorizado"); return
        if not HAVE_RECURSO:
            reload_info("Modelo Recurso no disponible"); return
        r = db.get(Recurso, rid)  # type: ignore
        if not r:
            reload_info("Recurso no encontrado"); return
        try:
            db.delete(r)
            db.commit()
            state["confirm_recurso"] = None
            reload_info("Recurso eliminado")
        except SQLAlchemyError as ex:
            db.rollback()
            reload_info(f"Error al eliminar recurso: {ex.__class__.__name__}")

    # ---------------- Acciones: reservas ----------------
    def ask_cancel_reserva(rid: int):
        state["confirm_reserva"] = None if state["confirm_reserva"] == rid else rid
        render_list()

    def cancel_reserva(rid: int):
        if u["rol"] != "admin":
            reload_info("No autorizado"); return
        r = db.get(Reserva, rid)
        if not r:
            reload_info("Reserva no encontrada"); return
        r.estado = "cancelada"
        db.commit()
        state["confirm_reserva"] = None
        reload_info("Reserva cancelada")

    def ask_cancel_all(lid: int):
        state["confirm_reservas_all"] = None if state["confirm_reservas_all"] == lid else lid
        render_list()

    def cancel_all(lid: int):
        if u["rol"] != "admin":
            reload_info("No autorizado"); return
        rows = get_future_reservas(lid)
        for r in rows:
            r.estado = "cancelada"
        db.commit()
        state["confirm_reservas_all"] = None
        reload_info("Todas las reservas futuras fueron canceladas")

    # ---------------- Acciones: eliminación de laboratorio ----------------
    def toggle_delete_panel(lid: int):
        state["delete_for"] = None if state["delete_for"] == lid else lid
        state["edit_for"] = None
        state["confirm_recurso"] = None
        state["confirm_reserva"] = None
        state["confirm_reservas_all"] = None
        reload_info(None)

    def try_delete_lab(lid: int):
        if u["rol"] != "admin":
            reload_info("No autorizado"); return

        lab = db.get(Laboratorio, lid)
        if not lab:
            reload_info("Laboratorio no encontrado"); return

        try:
            # 1) limpiar hijos (todas las reservas y recursos, no solo futuras)
            if HAVE_RECURSO:
                db.execute(delete(Recurso).where(Recurso.laboratorio_id == lid))
            db.execute(delete(Reserva).where(Reserva.laboratorio_id == lid))
            db.commit()

            # 2) borrar el laboratorio
            db.delete(lab)
            db.commit()
            state["delete_for"] = None
            reload_info("Laboratorio eliminado")
        except IntegrityError:
            db.rollback()
            # mensaje claro: todavía hay algo referenciando
            total_reservas = db.query(Reserva).filter(Reserva.laboratorio_id == lid).count()
            total_recursos = db.query(Recurso).filter(Recurso.laboratorio_id == lid).count() if HAVE_RECURSO else 0
            reload_info(
                f"No se puede eliminar: quedan referencias (reservas={total_reservas}, recursos={total_recursos})."
            )
        except Exception as ex:
            db.rollback()
            reload_info(f"Error al eliminar: {ex.__class__.__name__}")

    # ---------------- Render por laboratorio ----------------
    def lab_card(l: Laboratorio) -> ft.Control:
        # Plantel
        plantel_name = "-"
        if hasattr(l, "plantel_id") and l.plantel_id:
            pl = db.get(Plantel, int(l.plantel_id))
            if pl: plantel_name = pl.nombre

        # Header
        title = ft.Text(l.nombre, size=16, weight=ft.FontWeight.W_600)
        subtitle_bits = []
        if hasattr(l, "ubicacion") and l.ubicacion: subtitle_bits.append(f"Ubicación: {l.ubicacion}")
        if hasattr(l, "capacidad") and getattr(l, "capacidad", None) is not None: subtitle_bits.append(f"Capacidad: {getattr(l,'capacidad')}")
        if hasattr(l, "plantel_id"): subtitle_bits.append(f"Plantel: {plantel_name}")
        subtitle = ft.Text(" · ".join(subtitle_bits) or "-", size=12, opacity=0.85)

        btns = ft.Row(spacing=6)
        if u["rol"] == "admin":
            btns.controls = [
                Icon(ft.Icons.EDIT, "Editar", on_click=lambda e, lid=l.id: open_edit(lid)),
                Icon(ft.Icons.DELETE, "Eliminar", on_click=lambda e, lid=l.id: toggle_delete_panel(lid)),
            ]

        header = ft.Row([ft.Column([title, subtitle], spacing=2, expand=True), btns],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER)

        content = ft.Column(spacing=12)

        # --- Edición inline ---
        if state["edit_for"] == l.id and u["rol"] == "admin":
            n = TextField("Nombre", value=l.nombre, expand=True)
            uib = TextField("Ubicación", value=(getattr(l, "ubicacion", "") or ""), expand=True)
            cap = TextField("Capacidad", value=str(getattr(l, "capacidad", "") or ""), expand=True)

            dd_plantel = None
            if SUPPORT_PLANTEL:
                dd_plantel = make_plantel_dd(l.plantel_id, width=260)

            def save(_):
                vals = {"nombre": n.value, "ubicacion": uib.value, "capacidad": cap.value}
                if dd_plantel:
                    vals["plantel_id"] = dd_plantel.value
                save_edit(l.id, vals)

            content.controls.append(
                ft.Column(
                    [n, uib, cap] + ([dd_plantel] if dd_plantel else []) + [
                        ft.Row([
                            Primary("Guardar", on_click=save, width=130, height=40),
                            Ghost("Cancelar", on_click=lambda e: open_edit(l.id), width=120, height=40),
                        ], spacing=8)
                    ],
                    spacing=8, tight=True
                )
            )

        # --- Panel de eliminación (recursos y reservas) ---
        if state["delete_for"] == l.id and u["rol"] == "admin":
            # Recursos
            recursos = get_recursos(l.id)
            content.controls.append(ft.Text("Recursos asociados", weight=ft.FontWeight.W_600))
            if not HAVE_RECURSO:
                content.controls.append(ft.Text("El modelo 'Recurso' no está disponible en este proyecto.", size=12, italic=True))
            elif not recursos:
                content.controls.append(ft.Text("No hay recursos asociados.", size=12))
            else:
                otros_opts = [ft.dropdown.Option(str(x.id), x.nombre) for x in get_labs() if x.id != l.id]

                def make_move_handler(_rid: int, _dd: ft.Dropdown):
                    def _handler(e):
                        if _dd.value:
                            move_recurso(_rid, int(_dd.value))
                    return _handler

                for r in recursos:
                    dd = ft.Dropdown(label="Mover a", options=otros_opts, width=240)
                    move_btn = Primary("Reubicar", on_click=make_move_handler(r.id, dd), width=120, height=36)
                    if state["confirm_recurso"] == r.id:
                        actions = ft.Row([
                            Danger("Confirmar eliminación", on_click=lambda e, _rid=r.id: do_delete_recurso(_rid), width=200, height=36),
                            Ghost("Volver", on_click=lambda e: ask_delete_recurso(r.id), width=100, height=36),
                        ], spacing=8)
                    else:
                        actions = ft.Row([move_btn,
                                          Danger("Eliminar", on_click=lambda e, _rid=r.id: ask_delete_recurso(_rid), width=120, height=36)], spacing=8)

                    content.controls.append(
                        ft.Column([
                            ft.Text(f"#{r.id} · {getattr(r,'nombre','Recurso')}", weight=ft.FontWeight.W_600),
                            ft.Row([dd, actions], spacing=8),
                            ft.Divider(opacity=0.1),
                        ], spacing=6, tight=True)
                    )

            # Reservas futuras
            content.controls.append(ft.Text("Reservas futuras", weight=ft.FontWeight.W_600))
            reservas = get_future_reservas(l.id)
            if not reservas:
                content.controls.append(ft.Text("No hay reservas futuras.", size=12))
            else:
                # cancelar todas
                if state["confirm_reservas_all"] == l.id:
                    content.controls.append(
                        ft.Row([
                            Danger("Confirmar cancelar todas", on_click=lambda e, _lid=l.id: cancel_all(_lid), width=220, height=36),
                            Ghost("Volver", on_click=lambda e: ask_cancel_all(l.id), width=100, height=36),
                        ], spacing=8)
                    )
                else:
                    content.controls.append(
                        ft.Row([Danger("Cancelar todas", on_click=lambda e: ask_cancel_all(l.id), width=160, height=36)])
                    )
                # listar individuales
                for r in reservas:
                    label = f"{r.inicio.strftime('%Y-%m-%d %H:%M')}–{r.fin.strftime('%H:%M')} (#{r.id})"
                    if state["confirm_reserva"] == r.id:
                        row = ft.Row([
                            ft.Text(label),
                            Danger("Confirmar", on_click=lambda e, _rid=r.id: cancel_reserva(_rid), width=120, height=32),
                            Ghost("Volver", on_click=lambda e: ask_cancel_reserva(r.id), width=90, height=32),
                        ], spacing=8)
                    else:
                        row = ft.Row([
                            ft.Text(label),
                            Danger("Cancelar", on_click=lambda e, _rid=r.id: ask_cancel_reserva(_rid), width=120, height=32),
                        ], spacing=8)
                    content.controls.append(row)

            # Footer: eliminar laboratorio
            can_delete = (not get_recursos(l.id)) and (not get_future_reservas(l.id))
            content.controls.append(
                ft.Row([
                    Primary("Eliminar laboratorio ahora", on_click=lambda e, _lid=l.id: try_delete_lab(_lid), width=240, height=42, disabled=not can_delete),
                    Ghost("Cerrar gestión", on_click=lambda e: toggle_delete_panel(l.id), width=150, height=40),
                ], spacing=10)
            )

        body = ft.Column([header, content], spacing=10)
        return Card(body, padding=14)

    # ---------------- Render general ----------------
    def render_list():
        list_panel.controls.clear()
        for l in get_labs():
            list_panel.controls.append(lab_card(l))
        page.update()

    # Header crear (solo admin)
    actions = [nombre, ubicacion, capacidad]
    if SUPPORT_PLANTEL and dd_plantel_add is not None:
        actions.append(dd_plantel_add)  # 👈 ft.Dropdown nativo, NO el wrapper
    if u["rol"] == "admin":
        actions.append(Primary("Agregar", on_click=add_lab, width=160, height=44))

    render_list()
    return ft.Column(
        [
            ft.Text("Laboratorios", size=20, weight=ft.FontWeight.BOLD),
            Card(ft.Row(actions, wrap=False, alignment=ft.MainAxisAlignment.START), padding=14),
            info,
            ft.Divider(),
            list_panel,
        ],
        expand=True,
        alignment=ft.MainAxisAlignment.START,
        scroll=ft.ScrollMode.AUTO,
        spacing=10,
    )
