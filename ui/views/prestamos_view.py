# ui/views/prestamos_view.py
from __future__ import annotations

import os
import json
import flet as ft
from math import floor
from datetime import datetime, timedelta, time
from sqlalchemy.exc import SQLAlchemyError

from core.db import SessionLocal
from core.models import Plantel, Laboratorio

# ================================
#  Modelos disponibles (Recurso y Prestamo)
# ================================
try:
    from core.models import Recurso  # type: ignore
    HAVE_RECURSO = True
except Exception:
    HAVE_RECURSO = False

try:
    from core.models import Prestamo as SolicitudModel  # type: ignore
    HAVE_SOLICITUD = True
except Exception:
    SolicitudModel = None  # type: ignore
    HAVE_SOLICITUD = False

# ================================
#  Reglas de préstamo (por horas)
# ================================
CLASS_START = time(7, 0)      # 07:00
CLASS_END   = time(14, 30)    # 14:30
MAX_LOAN_HOURS = 7            # máximo 7 horas


def PrestamosView(page: ft.Page):
    db = SessionLocal()

    # ---------------------------------
    # Paleta adaptativa claro/oscuro
    # ---------------------------------
    def palette():
        dark = page.theme_mode == ft.ThemeMode.DARK
        return {
            "section_bg": "#111827" if dark else "#F3F4F6",
            "card_bg":    "#1F2937" if dark else "#FFFFFF",
            "border":     "#374151" if dark else "#E5E7EB",
            "text_primary":   "#F3F4F6" if dark else "#111827",
            "text_secondary": "#CBD5E1" if dark else "#374151",
            "muted_text":     "#9CA3AF" if dark else "#6B7280",
            "chip_text":      "#E5E7EB" if dark else "#1F2937",
        }

    PAL = palette()

    # ---------------------------------
    # Estado UI
    # ---------------------------------
    state = {
        "filter_plantel_id": None,   # int | None
        "filter_lab_id": None,       # int | None
        "filter_estado": "",         # "", "disponible", "prestado", "mantenimiento"
        "filter_tipo": "",           # "", o valor de tipo
        "active_tab": 0,             # 0 = disponibles, 1 = mis solicitudes, 2 = admin
    }

    # ---------------------------------
    # Catálogo de Tipos (persistente: archivo + DB)
    # ---------------------------------
    TIPOS_FILE = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "core", "tipos_catalog.json")
    )
    DEFAULT_TIPOS = {"equipo", "herramienta", "accesorio"}

    def load_tipo_catalog_from_db() -> set[str]:
        vals: set[str] = set()
        if not HAVE_RECURSO:
            return vals
        try:
            if hasattr(Recurso, "tipo"):
                rows = db.query(Recurso.tipo).distinct().all()  # type: ignore
                for (t,) in rows:
                    if t and isinstance(t, str) and t.strip():
                        vals.add(t.strip().lower())
        except Exception:
            pass
        return vals

    def load_tipo_catalog_from_file() -> set[str]:
        try:
            if os.path.exists(TIPOS_FILE):
                with open(TIPOS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return {str(x).strip().lower() for x in data if str(x).strip()}
        except Exception:
            pass
        return set()

    def save_tipo_catalog_to_file(catalog_set: set[str]):
        try:
            os.makedirs(os.path.dirname(TIPOS_FILE), exist_ok=True)
            with open(TIPOS_FILE, "w", encoding="utf-8") as f:
                json.dump(sorted(list(catalog_set)), f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    tipo_catalog = (load_tipo_catalog_from_db() | load_tipo_catalog_from_file()) or set(DEFAULT_TIPOS)

    # ---------------------------------
    # Helpers UI
    # ---------------------------------
    def SectionHeader(icon, title):
        return ft.Row(
            [
                ft.Icon(icon, size=20, color=PAL["text_primary"]),
                ft.Text(title, size=16, weight=ft.FontWeight.W_600, color=PAL["text_primary"]),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def SectionCard(children):
        return ft.Container(
            content=ft.Column(children, spacing=14),
            padding=16,
            border_radius=12,
            bgcolor=PAL["section_bg"],
            shadow=ft.BoxShadow(
                blur_radius=20,
                spread_radius=1,
                color="black",
                blur_style=ft.ShadowBlurStyle.OUTER,
            ),
        )

    def ItemCard(child: ft.Control):
        return ft.Container(
            content=child,
            padding=12,
            border_radius=10,
            border=ft.border.all(1, PAL["border"]),
            bgcolor=PAL["card_bg"],
        )

    # ---------------------------------
    # Helpers de datos
    # ---------------------------------
    def plantel_opts_all():
        rows = db.query(Plantel).order_by(Plantel.nombre.asc()).all()
        return [ft.dropdown.Option("", "Todos los planteles")] + [
            ft.dropdown.Option(str(p.id), p.nombre) for p in rows
        ]

    def labs_opts_for(plantel_id: int | None, include_all=True):
        q = db.query(Laboratorio).order_by(Laboratorio.nombre.asc())
        if plantel_id:
            q = q.filter(Laboratorio.plantel_id == plantel_id)
        labs = q.all()
        opts = [ft.dropdown.Option(str(l.id), l.nombre) for l in labs]
        if include_all:
            return [ft.dropdown.Option("", "Todos los laboratorios")] + opts
        return opts

    def lab_name_for(lid: int | None):
        if not lid:
            return "-"
        lab = db.get(Laboratorio, lid)
        return lab.nombre if lab else "-"

    def plantel_name_for(lab_id: int | None):
        if not lab_id:
            return "-"
        lab = db.get(Laboratorio, lab_id)
        if not lab or not getattr(lab, "plantel_id", None):
            return "-"
        pl = db.get(Plantel, lab.plantel_id)
        return pl.nombre if pl else "-"

    def get_recursos_filtrados():
        if not HAVE_RECURSO:
            return []
        q = db.query(Recurso)
        if state["filter_lab_id"]:
            q = q.filter(Recurso.laboratorio_id == state["filter_lab_id"])
        elif state["filter_plantel_id"]:
            lab_ids = [
                lid for (lid,) in db.query(Laboratorio.id)
                .filter(Laboratorio.plantel_id == state["filter_plantel_id"]).all()
            ]
            if not lab_ids:
                return []
            q = q.filter(Recurso.laboratorio_id.in_(lab_ids))
        if state["filter_estado"]:
            q = q.filter(Recurso.estado == state["filter_estado"])
        if state["filter_tipo"]:
            q = q.filter(Recurso.tipo == state["filter_tipo"])
        return q.order_by(Recurso.id.desc()).all()

    # ---------------------------------
    # Tipos dinámicos
    # ---------------------------------
    def build_tipo_options():
        base = [ft.dropdown.Option(v, v.capitalize()) for v in sorted(tipo_catalog)]
        base.append(ft.dropdown.Option("otro", "Otro…"))
        return base

    def build_tipo_filter_options():
        return [ft.dropdown.Option("", "Todos los tipos")] + [
            ft.dropdown.Option(v, v.capitalize()) for v in sorted(tipo_catalog)
        ]

    def add_tipo_to_catalog(nombre: str):
        """Agrega un tipo nuevo y refresca combos (con try por si el control aún no existe)."""
        v = (nombre or "").strip().lower()
        if not v:
            return False
        if v not in tipo_catalog:
            tipo_catalog.add(v)
            save_tipo_catalog_to_file(tipo_catalog)
        # refrescar opciones
        try:
            dd_tipo.options = build_tipo_options()
        except Exception:
            pass
        try:
            dd_tipo_filter.options = build_tipo_filter_options()
        except Exception:
            pass
        try:
            dd_edit_tipo.options = build_tipo_options()  # puede no existir aún
        except Exception:
            pass
        return True

    # ---------------------------------
    # Filtros (listado)
    # ---------------------------------
    dd_plantel = ft.Dropdown(label="Plantel", options=plantel_opts_all(), width=220, value="")
    dd_lab = ft.Dropdown(label="Laboratorio", options=labs_opts_for(None, include_all=True), width=220, value="")
    dd_estado = ft.Dropdown(
        label="Disponibilidad",
        options=[
            ft.dropdown.Option("", "Todos los estados"),
            ft.dropdown.Option("disponible", "disponible"),
            ft.dropdown.Option("prestado", "prestado"),
            ft.dropdown.Option("mantenimiento", "mantenimiento"),
        ],
        width=200,
        value=""
    )
    dd_tipo_filter = ft.Dropdown(label="Tipo", options=build_tipo_filter_options(), width=200, value="")

    def on_change_plantel(e: ft.ControlEvent):
        pid = dd_plantel.value or ""
        state["filter_plantel_id"] = int(pid) if pid.isdigit() else None
        dd_lab.options = labs_opts_for(state["filter_plantel_id"], include_all=True)
        dd_lab.value = ""
        render_lists()

    def on_change_lab(e: ft.ControlEvent):
        v = dd_lab.value or ""
        state["filter_lab_id"] = int(v) if v.isdigit() else None
        render_lists()

    def on_change_estado(e: ft.ControlEvent):
        state["filter_estado"] = dd_estado.value or ""
        render_lists()

    def on_change_tipo_filter(e: ft.ControlEvent):
        state["filter_tipo"] = dd_tipo_filter.value or ""
        render_lists()

    def clear_filtros(_=None):
        state["filter_plantel_id"] = None
        state["filter_lab_id"] = None
        state["filter_estado"] = ""
        state["filter_tipo"] = ""
        dd_plantel.options = plantel_opts_all()
        dd_plantel.value = ""
        dd_lab.options = labs_opts_for(None, include_all=True)
        dd_lab.value = ""
        dd_estado.value = ""
        dd_tipo_filter.options = build_tipo_filter_options()
        dd_tipo_filter.value = ""
        render_lists()

    dd_plantel.on_change = on_change_plantel
    dd_lab.on_change = on_change_lab
    dd_estado.on_change = on_change_estado
    dd_tipo_filter.on_change = on_change_tipo_filter

    def build_filtros_card():
        return SectionCard([
            SectionHeader(ft.Icons.FILTER_ALT, "Filtros"),
            ft.Row([dd_plantel, dd_lab, dd_estado, dd_tipo_filter, ft.OutlinedButton("Limpiar", on_click=clear_filtros)], spacing=12, wrap=True),
        ])

    title_lbl = ft.Text("Préstamos / Recursos", size=20, weight=ft.FontWeight.BOLD, color=PAL["text_primary"])
    filtros_card = build_filtros_card()

    # ---------------------------------
    # Listas por pestaña
    # ---------------------------------
    list_user = ft.Column(spacing=12)
    list_admin = ft.Column(spacing=12)
    list_solicitudes = ft.Column(spacing=12)

    # ---------------------------------
    # Alta (Admin)
    # ---------------------------------
    dd_add_plantel = ft.Dropdown(label="Plantel", width=280, options=plantel_opts_all(), value="")
    dd_add_lab = ft.Dropdown(label="Laboratorio", width=280, options=labs_opts_for(None, include_all=False))
    dd_tipo = ft.Dropdown(label="Tipo", width=240, options=build_tipo_options(), value="equipo")
    tf_tipo_otro = ft.TextField(label="Tipo (otro)", visible=False, width=260)
    btn_add_tipo = ft.ElevatedButton("Agregar tipo", disabled=True)
    tf_specs = ft.TextField(label="Especificaciones / descripción", multiline=True, min_lines=2, expand=True)
    dd_estado_add = ft.Dropdown(
        label="Estado",
        width=240,
        options=[
            ft.dropdown.Option("disponible", "disponible"),
            ft.dropdown.Option("prestado", "prestado"),
            ft.dropdown.Option("mantenimiento", "mantenimiento"),
        ],
        value="disponible",
    )

    def on_change_add_plantel(e: ft.ControlEvent):
        pid = dd_add_plantel.value or ""
        pid_int = int(pid) if pid.isdigit() else None
        dd_add_lab.options = labs_opts_for(pid_int, include_all=False)
        dd_add_lab.value = None
        dd_add_lab.update()
        page.update()

    def on_change_tipo(e: ft.ControlEvent):
        show = (dd_tipo.value == "otro")
        tf_tipo_otro.visible = show
        btn_add_tipo.disabled = not (show and (tf_tipo_otro.value or "").strip())
        tf_tipo_otro.update()
        btn_add_tipo.update()
        page.update()

    def on_change_tipo_otro(e: ft.ControlEvent):
        btn_add_tipo.disabled = not (tf_tipo_otro.visible and (tf_tipo_otro.value or "").strip())
        btn_add_tipo.update()
        page.update()

    def try_add_tipo_from_text():
        nombre = (tf_tipo_otro.value or "").strip()
        if not nombre:
            return
        if add_tipo_to_catalog(nombre):
            dd_tipo.value = nombre.lower()
        tf_tipo_otro.value = ""
        tf_tipo_otro.visible = False
        btn_add_tipo.disabled = True
        dd_tipo.update()
        tf_tipo_otro.update()
        btn_add_tipo.update()
        dd_tipo_filter.update()
        page.update()

    tf_tipo_otro.on_change = on_change_tipo_otro
    tf_tipo_otro.on_submit = lambda e: try_add_tipo_from_text()
    btn_add_tipo.on_click = lambda e: try_add_tipo_from_text()
    dd_add_plantel.on_change = on_change_add_plantel
    dd_tipo.on_change = on_change_tipo

    def clear_add(_=None):
        dd_add_plantel.value = ""
        dd_add_lab.value = None
        dd_add_lab.options = labs_opts_for(None, include_all=False)
        tf_tipo_otro.value = ""
        tf_tipo_otro.visible = (dd_tipo.value == "otro")
        btn_add_tipo.disabled = not tf_tipo_otro.visible
        tf_specs.value = ""
        dd_estado_add.value = "disponible"
        dd_add_plantel.update()
        dd_add_lab.update()
        dd_tipo.update()
        tf_tipo_otro.update()
        btn_add_tipo.update()
        tf_specs.update()
        dd_estado_add.update()
        page.update()

    # Utils internos para atributos variables
    def _attr(obj, name_list):
        for n in name_list:
            if hasattr(obj, n):
                return n
        return None

    def _set_if_has(obj, name_list, value):
        n = _attr(obj, name_list)
        if n:
            setattr(obj, n, value)

    def _get_if_has(obj, name_list, default=None):
        n = _attr(obj, name_list)
        if n:
            return getattr(obj, n)
        return default

    # Agregar Recurso
    def add_recurso(_=None):
        cur = page.session.get("user") or {}
        if cur.get("rol") != "admin":
            page.snack_bar = ft.SnackBar(ft.Text("Solo admin puede agregar recursos"), open=True); page.update(); return
        if not HAVE_RECURSO:
            page.snack_bar = ft.SnackBar(ft.Text("Modelo 'Recurso' no disponible"), open=True); page.update(); return
        if not dd_add_lab.value:
            page.snack_bar = ft.SnackBar(ft.Text("Selecciona laboratorio"), open=True); page.update(); return

        # Tipo obligatorio (si es "otro", lo añadimos al catálogo)
        tipo_val = (tf_tipo_otro.value.strip() if dd_tipo.value == "otro" else (dd_tipo.value or "")).strip()
        if not tipo_val:
            page.snack_bar = ft.SnackBar(ft.Text("El tipo es obligatorio"), open=True); page.update(); return
        if dd_tipo.value == "otro" and tipo_val:
            if add_tipo_to_catalog(tipo_val):
                dd_tipo.value = tipo_val.lower()
                dd_tipo.update()
                dd_tipo_filter.update()

        try:
            r = Recurso()  # type: ignore
            if hasattr(r, "laboratorio_id"): r.laboratorio_id = int(dd_add_lab.value)
            if hasattr(r, "tipo"):           r.tipo = tipo_val
            if hasattr(r, "estado"):         r.estado = dd_estado_add.value or "disponible"
            if hasattr(r, "specs"):          r.specs = (tf_specs.value or "").strip()

            db.add(r)  # type: ignore
            db.commit()
            new_id = getattr(r, "id", None)

            # Ajustar filtros para ver el nuevo recurso
            lab_id = int(dd_add_lab.value)
            lab = db.get(Laboratorio, lab_id)
            plantel_id = getattr(lab, "plantel_id", None) if lab else None

            state["filter_plantel_id"] = plantel_id if isinstance(plantel_id, int) else None
            state["filter_lab_id"] = lab_id
            state["filter_tipo"] = tipo_val
            state["filter_estado"] = ""

            dd_plantel.value = str(plantel_id) if plantel_id else ""
            dd_lab.options = labs_opts_for(plantel_id, include_all=True)
            dd_lab.value = str(lab_id)
            dd_estado.value = ""
            dd_tipo_filter.options = build_tipo_filter_options()
            dd_tipo_filter.value = tipo_val

            dd_plantel.update(); dd_lab.update(); dd_estado.update(); dd_tipo_filter.update()

            # Cambiar a pestaña Admin
            state["active_tab"] = 2
            try:
                tabs.selected_index = 2
                tabs.update()
            except Exception:
                pass

            # Limpiar formulario
            clear_add()

            # Refrescar listas
            render_lists()

            if new_id is not None:
                page.snack_bar = ft.SnackBar(ft.Text(f"Recurso #{new_id} agregado"), open=True)
                page.update()

        except SQLAlchemyError as ex:
            db.rollback()
            page.snack_bar = ft.SnackBar(ft.Text(f"Error al crear recurso: {ex.__class__.__name__}"), open=True); page.update()

    # ---------------------------------
    # BottomSheet de SOLICITUD (por horas)
    # ---------------------------------
    tf_motivo = ft.TextField(label="Motivo (opcional)", multiline=True, min_lines=2)
    txt_horas_info = ft.Text("", size=12, color=PAL["text_secondary"])
    slider_horas = ft.Slider(min=1, max=MAX_LOAN_HOURS, divisions=MAX_LOAN_HOURS - 1, value=2, label="{value} h")

    _solicitar_recurso_id: int | None = None
    _inicio_preview: datetime | None = None

    bs_body = ft.Container(
        content=ft.Column(
            [
                ft.Text("Solicitud de préstamo", size=16, weight=ft.FontWeight.W_600, color=PAL["text_primary"]),
                tf_motivo,
                ft.Text("Duración (horas)", size=12, color=PAL["text_secondary"]),
                slider_horas,
                txt_horas_info,
                ft.Row(
                    [ft.TextButton("Cancelar", on_click=lambda e: close_sheet()),
                     ft.FilledButton("Enviar solicitud", on_click=lambda e: crear_solicitud())],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=12, tight=True,
        ),
        padding=16, width=480,
        bgcolor=PAL["card_bg"], border=ft.border.all(1, PAL["border"]), border_radius=12,
    )
    bs_solicitud = ft.BottomSheet(bs_body, is_scroll_controlled=True)
    if not hasattr(page, "overlay") or bs_solicitud not in getattr(page, "overlay", []):
        page.overlay.append(bs_solicitud)

    def _normalize_inicio(now: datetime) -> datetime:
        if now.time() < CLASS_START:
            return datetime.combine(now.date(), CLASS_START)
        if now.time() > CLASS_END:
            return datetime.combine(now.date() + timedelta(days=1), CLASS_START)
        return now

    def _allowed_hours_for(start_dt: datetime) -> int:
        end_day = datetime.combine(start_dt.date(), CLASS_END)
        seconds = (end_day - start_dt).total_seconds()
        return max(0, floor(seconds / 3600))

    def open_solicitar_sheet(rid: int):
        nonlocal _solicitar_recurso_id, _inicio_preview
        _solicitar_recurso_id = rid
        tf_motivo.value = ""

        now = datetime.now()
        _inicio_preview = _normalize_inicio(now)

        allowed_today = min(MAX_LOAN_HOURS, _allowed_hours_for(_inicio_preview))
        if allowed_today < 1:
            allowed_today = 1

        slider_horas.max = max(1, allowed_today)
        slider_horas.divisions = int(slider_horas.max - 1) if slider_horas.max > 1 else 1
        slider_horas.value = 2 if slider_horas.max >= 2 else 1

        txt_horas_info.value = (
            f"Inicio: {_inicio_preview.strftime('%Y-%m-%d %H:%M')} · "
            f"Hoy disponibles: {allowed_today} h (hasta {CLASS_END.strftime('%H:%M')})"
        )

        bs_body.bgcolor = PAL["card_bg"]
        bs_body.border = ft.border.all(1, PAL["border"])
        txt_horas_info.color = PAL["text_secondary"]

        bs_solicitud.open = True
        bs_body.update(); txt_horas_info.update(); slider_horas.update()
        page.update()

    def close_sheet():
        bs_solicitud.open = False
        page.update()

    def crear_solicitud():
        """Crea una solicitud (Prestamo) usando nombre como solicitante."""
        if not HAVE_SOLICITUD:
            page.snack_bar = ft.SnackBar(ft.Text("Modelo de solicitudes no disponible."), open=True); page.update(); return
        if _solicitar_recurso_id is None:
            page.snack_bar = ft.SnackBar(ft.Text("ID de recurso no definido."), open=True); page.update(); return

        su = page.session.get("user") or {}
        user_id = su.get("id")
        if user_id is None:
            page.snack_bar = ft.SnackBar(ft.Text("No hay usuario en sesión (usuario_id requerido)."), open=True); page.update(); return

        # validar recurso
        if HAVE_RECURSO:
            rec = db.get(Recurso, int(_solicitar_recurso_id))  # type: ignore
            if rec is None:
                page.snack_bar = ft.SnackBar(ft.Text("Recurso no encontrado."), open=True); page.update(); return
            if getattr(rec, "estado", "disponible") != "disponible":
                page.snack_bar = ft.SnackBar(ft.Text("El recurso no está disponible."), open=True); page.update(); return

        try:
            s = SolicitudModel()  # type: ignore
            s.recurso_id = int(_solicitar_recurso_id)
            s.usuario_id = int(user_id)
            # usar NOMBRE de solicitante
            s.solicitante = str(su.get("nombre") or su.get("user") or su.get("correo") or su.get("email") or "desconocido")
            s.cantidad = 1
            s.estado = "pendiente"

            start_dt = _inicio_preview or _normalize_inicio(datetime.now())
            hours = int(slider_horas.value or 1)

            allowed_today = min(MAX_LOAN_HOURS, _allowed_hours_for(start_dt))
            if hours < 1:
                page.snack_bar = ft.SnackBar(ft.Text("La duración mínima es 1 hora."), open=True); page.update(); return
            if hours > allowed_today:
                page.snack_bar = ft.SnackBar(ft.Text(f"Solo quedan {allowed_today} hora(s) dentro del horario de clases."), open=True); page.update(); return

            end_dt = start_dt + timedelta(hours=hours)
            if end_dt.time() > CLASS_END or end_dt.date() != start_dt.date():
                page.snack_bar = ft.SnackBar(ft.Text("La duración excede el horario de clases del día."), open=True); page.update(); return

            s.inicio = start_dt
            s.fin = end_dt

            mot = (tf_motivo.value or "").strip()
            if mot:
                s.comentario = mot

            db.add(s)  # type: ignore
            db.commit()
            db.refresh(s)

            close_sheet()
            tf_motivo.value = ""
            page.update()

            try:
                tabs.selected_index = 1
                state["active_tab"] = 1
                tabs.update()
            except Exception:
                pass

            page.snack_bar = ft.SnackBar(ft.Text(f"Solicitud #{getattr(s, 'id', '')} creada"), open=True)
            render_lists()

        except Exception as ex:
            db.rollback()
            page.snack_bar = ft.SnackBar(ft.Text(f"Error al crear solicitud: {ex.__class__.__name__}: {ex}"), open=True)
            page.update()

    # ---------------------------------
    # EDITAR RECURSO (BottomSheet)
    # ---------------------------------
    dd_edit_plantel = ft.Dropdown(label="Plantel", width=280, options=plantel_opts_all(), value="")
    dd_edit_lab = ft.Dropdown(label="Laboratorio", width=280, options=labs_opts_for(None, include_all=False))
    dd_edit_tipo = ft.Dropdown(label="Tipo", width=240, options=build_tipo_options())
    tf_edit_tipo_otro = ft.TextField(label="Tipo (otro)", visible=False, width=260)
    dd_edit_estado = ft.Dropdown(
        label="Estado",
        width=240,
        options=[
            ft.dropdown.Option("disponible", "disponible"),
            ft.dropdown.Option("prestado", "prestado"),
            ft.dropdown.Option("mantenimiento", "mantenimiento"),
        ],
        value="disponible",
    )
    tf_edit_specs = ft.TextField(label="Especificaciones / descripción", multiline=True, min_lines=2, expand=True)

    _edit_recurso_id: int | None = None

    def on_change_edit_plantel(e: ft.ControlEvent):
        pid = dd_edit_plantel.value or ""
        pid_int = int(pid) if pid.isdigit() else None
        dd_edit_lab.options = labs_opts_for(pid_int, include_all=False)
        if dd_edit_lab.value and not any(opt.key == dd_edit_lab.value for opt in dd_edit_lab.options):
            dd_edit_lab.value = None
        dd_edit_lab.update(); page.update()

    def on_change_edit_tipo(e: ft.ControlEvent):
        show = (dd_edit_tipo.value == "otro")
        tf_edit_tipo_otro.visible = show
        tf_edit_tipo_otro.update(); page.update()

    dd_edit_plantel.on_change = on_change_edit_plantel
    dd_edit_tipo.on_change = on_change_edit_tipo

    edit_body = ft.Container(
        content=ft.Column(
            [
                ft.Text("Editar recurso", size=16, weight=ft.FontWeight.W_600, color=PAL["text_primary"]),
                ft.Row([dd_edit_plantel, dd_edit_lab], spacing=12, wrap=True),
                ft.Row([dd_edit_tipo, tf_edit_tipo_otro, dd_edit_estado], spacing=12, wrap=True),
                tf_edit_specs,
                ft.Row(
                    [ft.TextButton("Cancelar", on_click=lambda e: close_edit_sheet()),
                     ft.FilledButton("Guardar", on_click=lambda e: guardar_edicion())],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=12, tight=True,
        ),
        padding=16, width=560,
        bgcolor=PAL["card_bg"], border=ft.border.all(1, PAL["border"]), border_radius=12,
    )
    bs_edit = ft.BottomSheet(edit_body, is_scroll_controlled=True)
    if not hasattr(page, "overlay") or bs_edit not in getattr(page, "overlay", []):
        page.overlay.append(bs_edit)

    def open_editar_recurso(rid: int):
        nonlocal _edit_recurso_id
        if not HAVE_RECURSO:
            page.snack_bar = ft.SnackBar(ft.Text("Modelo 'Recurso' no disponible"), open=True); page.update(); return
        rec = db.get(Recurso, rid)  # type: ignore
        if not rec:
            page.snack_bar = ft.SnackBar(ft.Text("Recurso no encontrado"), open=True); page.update(); return

        _edit_recurso_id = rid

        # Plantel/Lab actuales
        lab_id = getattr(rec, "laboratorio_id", None)
        lab = db.get(Laboratorio, int(lab_id)) if lab_id else None
        plantel_id = getattr(lab, "plantel_id", None) if lab else None

        dd_edit_plantel.value = str(plantel_id) if plantel_id else ""
        dd_edit_lab.options = labs_opts_for(plantel_id, include_all=False)
        dd_edit_lab.value = str(lab_id) if lab_id else None

        # Tipo / Otro
        tipo_val = (getattr(rec, "tipo", "") or "").strip()
        if tipo_val and tipo_val.lower() in tipo_catalog:
            dd_edit_tipo.value = tipo_val
            tf_edit_tipo_otro.visible = False
            tf_edit_tipo_otro.value = ""
        else:
            dd_edit_tipo.value = "otro"
            tf_edit_tipo_otro.visible = True
            tf_edit_tipo_otro.value = tipo_val

        dd_edit_estado.value = getattr(rec, "estado", "disponible") or "disponible"
        tf_edit_specs.value = getattr(rec, "specs", "") or ""

        # Colores por tema
        edit_body.bgcolor = PAL["card_bg"]
        edit_body.border = ft.border.all(1, PAL["border"])

        for ctl in [dd_edit_plantel, dd_edit_lab, dd_edit_tipo, tf_edit_tipo_otro, dd_edit_estado, tf_edit_specs, edit_body]:
            ctl.update()

        bs_edit.open = True
        page.update()

    def close_edit_sheet():
        bs_edit.open = False
        page.update()

    def guardar_edicion():
        if _edit_recurso_id is None:
            return
        rec = db.get(Recurso, int(_edit_recurso_id))  # type: ignore
        if not rec:
            page.snack_bar = ft.SnackBar(ft.Text("Recurso no encontrado"), open=True); page.update(); return
        if not dd_edit_lab.value:
            page.snack_bar = ft.SnackBar(ft.Text("Selecciona un laboratorio"), open=True); page.update(); return

        tipo_val = (tf_edit_tipo_otro.value.strip() if dd_edit_tipo.value == "otro" else (dd_edit_tipo.value or "")).strip()
        if not tipo_val:
            page.snack_bar = ft.SnackBar(ft.Text("El tipo es obligatorio"), open=True); page.update(); return
        if dd_edit_tipo.value == "otro" and tipo_val:
            add_tipo_to_catalog(tipo_val)  # actualiza combos

        try:
            if hasattr(rec, "laboratorio_id"): rec.laboratorio_id = int(dd_edit_lab.value)
            if hasattr(rec, "tipo"):           rec.tipo = tipo_val
            if hasattr(rec, "estado"):         rec.estado = dd_edit_estado.value or "disponible"
            if hasattr(rec, "specs"):          rec.specs = (tf_edit_specs.value or "").strip()

            db.commit()

            # ajustar filtros para seguir viendo el recurso editado
            pid = int(dd_edit_plantel.value) if (dd_edit_plantel.value or "").isdigit() else None
            lid = int(dd_edit_lab.value) if (dd_edit_lab.value or "").isdigit() else None
            state["filter_plantel_id"] = pid
            state["filter_lab_id"] = lid
            state["filter_tipo"] = tipo_val
            dd_plantel.value = dd_edit_plantel.value or ""
            dd_lab.options = labs_opts_for(pid, include_all=True)
            dd_lab.value = dd_edit_lab.value or ""
            dd_tipo_filter.options = build_tipo_filter_options()
            dd_tipo_filter.value = tipo_val
            dd_plantel.update(); dd_lab.update(); dd_tipo_filter.update()

            close_edit_sheet()
            render_lists()
            page.snack_bar = ft.SnackBar(ft.Text("Recurso actualizado"), open=True)
            page.update()

        except SQLAlchemyError as ex:
            db.rollback()
            page.snack_bar = ft.SnackBar(ft.Text(f"Error al actualizar: {ex.__class__.__name__}"), open=True); page.update()

    # ---------------------------------
    # Acciones admin sobre solicitudes
    # ---------------------------------
    def admin_cambiar_estado(sol_id: int, nuevo_estado: str, cambiar_recurso: bool = False):
        if not HAVE_SOLICITUD:
            return
        s = db.get(SolicitudModel, sol_id)  # type: ignore
        if not s:
            return
        try:
            _set_if_has(s, ["estado", "status"], nuevo_estado)

            # si devuelto, sellamos hora real de devolución
            if nuevo_estado == "devuelto" and hasattr(s, "fin"):
                s.fin = datetime.now()

            # tocar recurso si aplica
            if cambiar_recurso:
                rec_id = _get_if_has(s, ["recurso_id", "id_recurso", "recurso"])
                if rec_id and HAVE_RECURSO:
                    r = db.get(Recurso, int(rec_id))  # type: ignore
                    if r and hasattr(r, "estado"):
                        if nuevo_estado in ("aprobado", "entregado"):
                            r.estado = "prestado"
                        elif nuevo_estado == "devuelto":
                            r.estado = "disponible"

            db.commit()
            render_lists()
            page.snack_bar = ft.SnackBar(ft.Text(f"Solicitud {nuevo_estado}"), open=True)
            page.update()
        except SQLAlchemyError as ex:
            db.rollback()
            page.snack_bar = ft.SnackBar(ft.Text(f"Error al actualizar: {ex.__class__.__name__}"), open=True)
            page.update()

    # ---------------------------------
    # Render de recursos
    # ---------------------------------
    def delete_recurso(rid: int):
        cur = page.session.get("user") or {}
        if cur.get("rol") != "admin":
            page.snack_bar = ft.SnackBar(ft.Text("No autorizado"), open=True); page.update(); return
        r = db.get(Recurso, rid)  # type: ignore
        if not r:
            return
        try:
            db.delete(r); db.commit()
            render_lists()
            page.snack_bar = ft.SnackBar(ft.Text("Recurso eliminado"), open=True); page.update()
        except SQLAlchemyError as ex:
            db.rollback()
            page.snack_bar = ft.SnackBar(ft.Text(f"Error al eliminar: {ex.__class__.__name__}"), open=True); page.update()

    def recurso_tile(r) -> ft.Control:
        title_bits = []
        if hasattr(r, "tipo") and r.tipo:
            title_bits.append(str(r.tipo).capitalize())
        title_bits.append(f"#{r.id}")
        title = ft.Text(" · ".join(title_bits), size=15, weight=ft.FontWeight.W_600, color=PAL["text_primary"])

        sub = []
        sub.append(f"Plantel: {plantel_name_for(getattr(r, 'laboratorio_id', None))}")
        sub.append(f"Laboratorio: {lab_name_for(getattr(r, 'laboratorio_id', None))}")
        if hasattr(r, "estado") and r.estado:
            sub.append(f"Estado: {r.estado}")
        if hasattr(r, "specs") and r.specs:
            sub.append(str(r.specs))
        subtitle = ft.Text(" · ".join(sub), size=12, color=PAL["text_secondary"])

        # Acciones
        if state["active_tab"] == 2 and (page.session.get("user") or {}).get("rol") == "admin":
            actions = ft.Row(
                [
                    ft.OutlinedButton("Editar", on_click=lambda e, rid=r.id: open_editar_recurso(rid)),
                    ft.TextButton("Eliminar", on_click=lambda e, rid=r.id: delete_recurso(rid)),
                ],
                spacing=8,
            )
            btns: ft.Control = actions
        else:
            if getattr(r, "estado", "disponible") == "disponible":
                btns = ft.ElevatedButton("Solicitar", on_click=lambda e, _rid=r.id: open_solicitar_sheet(_rid))
            else:
                btns = ft.OutlinedButton("No disponible", disabled=True)

        row = ft.Row(
            [ft.Column([title, subtitle], spacing=4, expand=True), btns],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )
        return ItemCard(row)

    # ---------------------------------
    # Render listas pestañas
    # ---------------------------------
    def render_user_list():
        list_user.controls.clear()
        rows = get_recursos_filtrados()
        list_user.controls.append(SectionHeader(ft.Icons.INVENTORY_2, f"Recursos disponibles ({len(rows)})"))
        if not rows:
            list_user.controls.append(ft.Text("No hay recursos para los filtros seleccionados.", color=PAL["muted_text"]))
        else:
            list_user.controls.append(ft.Column([recurso_tile(r) for r in rows], spacing=10))

    def _q_solicitudes_base():
        if not HAVE_SOLICITUD:
            return None
        return db.query(SolicitudModel).order_by(SolicitudModel.id.desc())  # type: ignore

    def _filter_my(q):
        """Filtra por el usuario actual: primero por usuario_id, si no, por solicitante."""
        if q is None:
            return None
        cur = page.session.get("user") or {}
        uid = cur.get("id")
        name = str(cur.get("nombre") or cur.get("user") or cur.get("correo") or cur.get("email") or "")
        if uid is not None and hasattr(SolicitudModel, "usuario_id"):
            return q.filter(getattr(SolicitudModel, "usuario_id") == uid)  # type: ignore
        if name and hasattr(SolicitudModel, "solicitante"):
            return q.filter(getattr(SolicitudModel, "solicitante") == name)  # type: ignore
        return q.filter(SolicitudModel.id == -1)  # type: ignore

    def solicitud_chip_estado(val: str):
        txt = str(val).capitalize()
        return ft.Container(
            content=ft.Text(txt, size=12, color=PAL["chip_text"]),
            padding=ft.padding.symmetric(4, 8),
            border_radius=20,
            border=ft.border.all(1, PAL["border"]),
        )

    def solicitud_row(s) -> ft.Control:
        """Fila en 'Mis solicitudes' con Pedido / Devuelto o Entrega plan."""
        sid = getattr(s, "id", "-")
        rid = _get_if_has(s, ["recurso_id", "id_recurso", "recurso"], "-")
        estado_val = (_get_if_has(s, ["estado", "status"], "-") or "").lower()
        comentario = _get_if_has(s, ["comentario", "motivo", "notas", "comentarios"], "")
        creado = _get_if_has(s, ["created_at", "fecha_solicitud"], None)
        fin = _get_if_has(s, ["fin"], None)

        def _fmt_dt(dt):
            if isinstance(dt, datetime):
                return dt.strftime("%Y-%m-%d %H:%M")
            try:
                return str(dt) if dt else ""
            except Exception:
                return ""

        time_lines = [ft.Text(f"Pedido: {_fmt_dt(creado)}", size=11, color=PAL["muted_text"])]
        if estado_val == "devuelto":
            time_lines.append(ft.Text(f"Devuelto: {_fmt_dt(fin)}", size=11, color=PAL["muted_text"]))
        else:
            time_lines.append(ft.Text(f"Entrega plan: {_fmt_dt(fin)}", size=11, color=PAL["muted_text"]))

        left = ft.Column(
            [
                ft.Text(f"Solicitud #{sid} · Recurso #{rid}", size=15, weight=ft.FontWeight.W_600, color=PAL["text_primary"]),
                ft.Text(comentario or "-", size=12, color=PAL["text_secondary"]),
                *time_lines,
            ],
            spacing=2,
            expand=True,
        )
        right = solicitud_chip_estado(estado_val or "-")
        row = ft.Row([left, right], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        return ItemCard(row)

    def render_my_requests():
        list_solicitudes.controls.clear()
        list_solicitudes.controls.append(SectionHeader(ft.Icons.PENDING_ACTIONS, "Mis solicitudes"))
        if not HAVE_SOLICITUD:
            list_solicitudes.controls.append(ft.Text("El modelo de solicitudes no está disponible.", color=PAL["muted_text"]))
            return
        q = _q_solicitudes_base()
        q = _filter_my(q)
        rows = q.all() if q is not None else []
        if not rows:
            list_solicitudes.controls.append(ft.Text("Aún no tienes solicitudes.", color=PAL["muted_text"]))
        else:
            list_solicitudes.controls.append(ft.Column([solicitud_row(s) for s in rows], spacing=10))

    def admin_solicitud_row(s) -> ft.Control:
        """Fila en 'Solicitudes (admin)': al devolver oculta botones y muestra Pedido/Devuelto."""
        sid = getattr(s, "id", "-")
        rid = _get_if_has(s, ["recurso_id", "id_recurso", "recurso"], "-")
        estado_val = (_get_if_has(s, ["estado", "status"], "-") or "").lower()
        solicitante = _get_if_has(s, ["solicitante", "usuario", "user", "email", "correo"], "-")
        creado = _get_if_has(s, ["created_at", "fecha_solicitud"], None)
        fin = _get_if_has(s, ["fin"], None)

        def _fmt_dt(dt):
            if isinstance(dt, datetime):
                return dt.strftime("%Y-%m-%d %H:%M")
            try:
                return str(dt) if dt else ""
            except Exception:
                return ""

        timeline = [ft.Text(f"Pedido: {_fmt_dt(creado)}", size=11, color=PAL["muted_text"])]
        if estado_val == "devuelto":
            timeline.append(ft.Text(f"Devuelto: {_fmt_dt(fin)}", size=11, color=PAL["muted_text"]))
        else:
            timeline.append(ft.Text(f"Entrega plan: {_fmt_dt(fin)}", size=11, color=PAL["muted_text"]))

        left = ft.Column(
            [
                ft.Text(f"Solicitud #{sid} · Recurso #{rid}", size=15, weight=ft.FontWeight.W_600, color=PAL["text_primary"]),
                ft.Text(f"Solicitante: {solicitante}", size=12, color=PAL["text_secondary"]),
                *timeline,
            ],
            spacing=2,
            expand=True,
        )

        if estado_val == "devuelto":
            right = solicitud_chip_estado("devuelto")
        else:
            actions = []
            if estado_val != "aprobado":
                actions.append(ft.ElevatedButton("Aprobar", on_click=lambda e, _sid=sid: admin_cambiar_estado(_sid, "aprobado", cambiar_recurso=True)))
            if estado_val != "rechazado":
                actions.append(ft.OutlinedButton("Rechazar", on_click=lambda e, _sid=sid: admin_cambiar_estado(_sid, "rechazado")))
            if estado_val != "entregado":
                actions.append(ft.FilledButton("Entregado", on_click=lambda e, _sid=sid: admin_cambiar_estado(_sid, "entregado", cambiar_recurso=True)))
            actions.append(ft.TextButton("Devuelto", on_click=lambda e, _sid=sid: admin_cambiar_estado(_sid, "devuelto", cambiar_recurso=True)))
            right = ft.Row(actions, spacing=8)

        row = ft.Row([left, right], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        return ItemCard(row)

    def render_admin_requests():
        if (page.session.get("user") or {}).get("rol") != "admin":
            return
        if not HAVE_SOLICITUD:
            list_admin.controls.append(SectionHeader(ft.Icons.ADMIN_PANEL_SETTINGS, "Solicitudes (admin)"))
            list_admin.controls.append(ft.Text("El modelo de solicitudes no está disponible.", color=PAL["muted_text"]))
            return
        q = _q_solicitudes_base()
        rows = q.all() if q is not None else []
        list_admin.controls.append(SectionHeader(ft.Icons.ADMIN_PANEL_SETTINGS, f"Solicitudes (admin) · {len(rows)}"))
        if not rows:
            list_admin.controls.append(ft.Text("No hay solicitudes registradas.", color=PAL["muted_text"]))
        else:
            list_admin.controls.append(ft.Column([admin_solicitud_row(s) for s in rows], spacing=10))

    def render_admin_list():
        list_admin.controls.clear()
        rows = get_recursos_filtrados()
        list_admin.controls.append(SectionHeader(ft.Icons.INVENTORY, f"Inventario (filtrado) · {len(rows)}"))
        if not rows:
            list_admin.controls.append(ft.Text("No hay recursos para los filtros seleccionados.", color=PAL["muted_text"]))
        else:
            list_admin.controls.append(ft.Column([recurso_tile(r) for r in rows], spacing=10))
        list_admin.controls.append(ft.Divider(opacity=0.2))
        render_admin_requests()

    def render_lists():
        nonlocal PAL
        PAL = palette()
        if state["active_tab"] == 0:
            render_user_list()
        elif state["active_tab"] == 1:
            render_my_requests()
        elif state["active_tab"] == 2 and (page.session.get("user") or {}).get("rol") == "admin":
            render_admin_list()
        page.update()

    # ---------------------------------
    # Sección “Alta de recurso” como builder (para tema en caliente)
    # ---------------------------------
    def build_admin_add_section():
        return SectionCard([
            SectionHeader(ft.Icons.ADD_BOX, "Alta de recurso (admin)"),
            ft.Row([dd_add_plantel, dd_add_lab, ft.OutlinedButton("Limpiar", on_click=clear_add)], spacing=12, wrap=True),
            ft.Row([dd_tipo, ft.Row([tf_tipo_otro, btn_add_tipo], spacing=8), dd_estado_add], spacing=12, wrap=True),
            tf_specs,
            ft.Row([ft.ElevatedButton("Agregar", on_click=lambda e: add_recurso())], alignment=ft.MainAxisAlignment.END),
        ])

    admin_add_section = None
    if (page.session.get("user") or {}).get("rol") == "admin":
        admin_add_section = build_admin_add_section()

    # ---------------------------------
    # Tabs
    # ---------------------------------
    tab_user = ft.Tab(text="Disponibles", icon=ft.Icons.CHECK_CIRCLE, content=ft.Column([list_user], spacing=16))
    tab_solic = ft.Tab(text="Mis solicitudes", icon=ft.Icons.PENDING_ACTIONS, content=ft.Column([list_solicitudes], spacing=16))

    tabs_arr = [tab_user, tab_solic]
    if admin_add_section is not None:
        tab_admin = ft.Tab(
            text="Recursos (Admin)",
            icon=ft.Icons.ADMIN_PANEL_SETTINGS,
            content=ft.Column([admin_add_section, ft.Divider(opacity=0.2), list_admin], spacing=16),
        )
        tabs_arr.append(tab_admin)

    def on_tabs_change(e: ft.ControlEvent):
        state["active_tab"] = e.control.selected_index
        render_lists()

    tabs = ft.Tabs(tabs=tabs_arr, selected_index=0, on_change=on_tabs_change)

    # ---------------------------------
    # THEME SYNC: refrescar en caliente
    # ---------------------------------
    def refresh_theme():
        nonlocal PAL, filtros_card, admin_add_section
        PAL = palette()

        # Título
        title_lbl.color = PAL["text_primary"]; title_lbl.update()

        # Reconstruir secciones dependientes de colores
        new_fc = build_filtros_card()
        filtros_card.content = new_fc.content
        filtros_card.bgcolor = PAL["section_bg"]; filtros_card.update()

        if admin_add_section is not None:
            new_admin = build_admin_add_section()
            admin_add_section.content = new_admin.content
            admin_add_section.bgcolor = PAL["section_bg"]; admin_add_section.update()

        # BottomSheets
        bs_body.bgcolor = PAL["card_bg"]; bs_body.border = ft.border.all(1, PAL["border"])
        edit_body.bgcolor = PAL["card_bg"]; edit_body.border = ft.border.all(1, PAL["border"])
        txt_horas_info.color = PAL["text_secondary"]
        bs_body.update(); edit_body.update(); txt_horas_info.update()

        # Re-render listas
        render_lists()

    def _on_theme_msg(msg):
        if isinstance(msg, dict) and msg.get("type") == "theme_changed":
            refresh_theme()

    page.pubsub.subscribe(_on_theme_msg)
    page.on_platform_brightness_change = lambda e: refresh_theme()

    # ---------------------------------
    # Render inicial
    # ---------------------------------
    render_lists()

    # ---------------------------------
    # Componente raíz
    # ---------------------------------
    return ft.Column(
        [
            ft.Row([
                ft.Container(
                    content=ft.Text(
                        "Modelo Prestamo: OK" if HAVE_SOLICITUD else "Modelo Prestamo: NO DISPONIBLE",
                        size=12, color="green" if HAVE_SOLICITUD else "red", weight=ft.FontWeight.W_600,
                    ),
                    padding=8, border_radius=6, bgcolor="#DCFCE7" if HAVE_SOLICITUD else "#FEE2E2",
                )
            ]),
            title_lbl,
            filtros_card,
            tabs,
        ],
        expand=True,
        spacing=18,
        alignment=ft.MainAxisAlignment.START,
        scroll=ft.ScrollMode.AUTO,
    )
