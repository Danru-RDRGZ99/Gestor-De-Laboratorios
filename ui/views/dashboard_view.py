# ui/views/dashboard_view.py
from __future__ import annotations

import flet as ft
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

from core.db import SessionLocal

# Modelos
try:
    from core.models import Prestamo as SolicitudModel  # type: ignore
    HAVE_SOLICITUD = True
except Exception:
    SolicitudModel = None  # type: ignore
    HAVE_SOLICITUD = False

try:
    from core.models import Recurso  # type: ignore
    HAVE_RECURSO = True
except Exception:
    Recurso = None  # type: ignore
    HAVE_RECURSO = False

try:
    from core.models import Reserva, Laboratorio  # type: ignore
    HAVE_RESERVA = True
except Exception:
    Reserva = None  # type: ignore
    Laboratorio = None  # type: ignore
    HAVE_RESERVA = False


def DashboardView(page: ft.Page):
    db = SessionLocal()

    # ---------------- Tema / paleta ----------------
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

    # ---------------- Helpers UI ----------------
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

    def chip_estado(txt: str):
        return ft.Container(
            content=ft.Text((txt or "-").capitalize(), size=12, color=PAL["chip_text"]),
            padding=ft.padding.symmetric(4, 8),
            border_radius=20,
            border=ft.border.all(1, PAL["border"]),
        )

    # ---------------- Helpers datos ----------------
    def _safe(dt):
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d %H:%M")
        return ""

    def _tipo_de(s) -> str:
        try:
            if hasattr(s, "recurso") and s.recurso and hasattr(s.recurso, "tipo"):
                return str(s.recurso.tipo or "")
        except Exception:
            pass
        rid = getattr(s, "recurso_id", None)
        return f"Recurso #{rid}" if rid else "Recurso"

    def _lab_name(lab_id) -> str:
        if not HAVE_RESERVA or not lab_id:
            return "-"
        try:
            lab = db.get(Laboratorio, int(lab_id))  # type: ignore
            return getattr(lab, "nombre", "-") or "-"
        except Exception:
            return "-"

    def _mis_prestamos(limit: int = 8):
        if not HAVE_SOLICITUD:
            return []
        u = page.session.get("user") or {}
        uid = u.get("id")
        if uid is None:
            return []
        try:
            q = db.query(SolicitudModel).filter(SolicitudModel.usuario_id == int(uid))  # type: ignore
            if hasattr(SolicitudModel, "created_at"):
                q = q.order_by(SolicitudModel.created_at.desc())  # type: ignore
            else:
                q = q.order_by(SolicitudModel.id.desc())  # type: ignore
            return q.limit(limit).all()
        except SQLAlchemyError:
            return []

    def _mis_reservas(limit: int = 8):
        if not HAVE_RESERVA:
            return []
        u = page.session.get("user") or {}
        uid = u.get("id")
        if uid is None:
            return []
        try:
            q = db.query(Reserva).filter(Reserva.usuario_id == int(uid))  # type: ignore
            q = q.order_by(Reserva.inicio.desc())  # type: ignore
            return q.limit(limit).all()
        except SQLAlchemyError:
            return []

    # ---------------- Secciones ----------------
    titulo = ft.Text("Dashboard", size=20, weight=ft.FontWeight.BOLD, color=PAL["text_primary"])
    saludo = ft.Text("", size=14, color=PAL["text_secondary"])
    user = page.session.get("user") or {}
    nombre = user.get("nombre") or user.get("user") or ""
    if nombre:
        saludo.value = f"Hola, {nombre}."

    # --- Mis préstamos ---
    mis_prestamos_list = ft.Column(spacing=10)

    def row_prestamo(s):
        sid = getattr(s, "id", "-")
        estado = getattr(s, "estado", "-")
        tipo_txt = _tipo_de(s)

        creado = getattr(s, "created_at", None)
        ini = getattr(s, "inicio", None)
        fin = getattr(s, "fin", None)

        time_lines = [
            ft.Text(f"Pedido: {_safe(creado)}", size=11, color=PAL["muted_text"]),
        ]
        if str(estado).lower() == "devuelto":
            time_lines.append(ft.Text(f"Devuelto: {_safe(fin)}", size=11, color=PAL["muted_text"]))
        else:
            time_lines.append(ft.Text(f"Entrega plan: {_safe(fin)}", size=11, color=PAL["muted_text"]))

        left = ft.Column(
            [
                ft.Text(f"Préstamo #{sid} · {tipo_txt}", size=15, weight=ft.FontWeight.W_600, color=PAL["text_primary"]),
                ft.Text(f"Inicio: {_safe(ini)}", size=12, color=PAL["text_secondary"]),
                *time_lines,
            ],
            spacing=2,
            expand=True,
        )
        right = chip_estado(estado or "-")
        return ItemCard(ft.Row([left, right], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER))

    def render_mis_prestamos():
        mis_prestamos_list.controls.clear()
        rows = _mis_prestamos()
        mis_prestamos_list.controls.append(
            SectionHeader(ft.Icons.SWIPE_RIGHT, f"Mis préstamos ({len(rows)})")
        )
        if not HAVE_SOLICITUD:
            mis_prestamos_list.controls.append(ft.Text("El módulo de préstamos no está disponible.", color=PAL["muted_text"]))
        elif not rows:
            mis_prestamos_list.controls.append(ft.Text("Aún no tienes préstamos.", color=PAL["muted_text"]))
        else:
            mis_prestamos_list.controls.append(ft.Column([row_prestamo(s) for s in rows], spacing=10))

    btn_prestamos = ft.OutlinedButton(
        "Ver todos los préstamos",
        icon=ft.Icons.OPEN_IN_NEW,
        on_click=lambda e: page.go("/recursos"),
    )

    # --- Mis reservas (solo docente) ---
    mis_reservas_list = ft.Column(spacing=10)

    def row_reserva(r):
        rid = getattr(r, "id", "-")
        estado = getattr(r, "estado", "-")
        lab_id = getattr(r, "laboratorio_id", None)
        lab = _lab_name(lab_id)
        ini = getattr(r, "inicio", None)
        fin = getattr(r, "fin", None)

        left = ft.Column(
            [
                ft.Text(f"Reserva #{rid} · {lab}", size=15, weight=ft.FontWeight.W_600, color=PAL["text_primary"]),
                ft.Text(f"Inicio: {_safe(ini)} · Fin: {_safe(fin)}", size=12, color=PAL["text_secondary"]),
            ],
            spacing=2,
            expand=True,
        )
        right = chip_estado(estado or "-")
        return ItemCard(ft.Row([left, right], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER))

    def render_mis_reservas():
        mis_reservas_list.controls.clear()
        rows = _mis_reservas()
        mis_reservas_list.controls.append(
            SectionHeader(ft.Icons.BOOKMARK_ADD, f"Mis reservas de laboratorio ({len(rows)})")
        )
        if not HAVE_RESERVA:
            mis_reservas_list.controls.append(ft.Text("El módulo de reservas no está disponible.", color=PAL["muted_text"]))
        elif not rows:
            mis_reservas_list.controls.append(ft.Text("Aún no tienes reservas.", color=PAL["muted_text"]))
        else:
            mis_reservas_list.controls.append(ft.Column([row_reserva(r) for r in rows], spacing=10))

    btn_reservas = ft.OutlinedButton(
        "Ir a reservas",
        icon=ft.Icons.OPEN_IN_NEW,
        on_click=lambda e: page.go("/reservas"),
    )

    # Construcción del layout según rol
    body = ft.Column(spacing=16, expand=True)

    role = (user.get("rol") or "").lower()
    if role == "estudiante":
        render_mis_prestamos()
        body.controls.append(SectionCard([saludo, mis_prestamos_list, ft.Row([btn_prestamos], alignment=ft.MainAxisAlignment.END)]))
    elif role == "docente":
        render_mis_prestamos()
        render_mis_reservas()
        body.controls.append(
            SectionCard([saludo, mis_prestamos_list, ft.Row([btn_prestamos], alignment=ft.MainAxisAlignment.END)])
        )
        body.controls.append(
            SectionCard([mis_reservas_list, ft.Row([btn_reservas], alignment=ft.MainAxisAlignment.END)])
        )
    else:
        # Admin u otros roles
        body.controls.append(
            SectionCard([
                saludo or ft.Text(""),
                ft.Text("Bienvenido. Usa el menú de la izquierda para navegar.", color=PAL["text_secondary"]),
            ])
        )

    # ---------------- Tema reactivo ----------------
    def refresh_theme():
        nonlocal PAL
        PAL = palette()
        titulo.color = PAL["text_primary"]; titulo.update()

        # Reconstruimos el body para refrescar colores y datos
        body.controls.clear()
        if role == "estudiante":
            render_mis_prestamos()
            body.controls.append(SectionCard([saludo, mis_prestamos_list, ft.Row([btn_prestamos], alignment=ft.MainAxisAlignment.END)]))
        elif role == "docente":
            render_mis_prestamos()
            render_mis_reservas()
            body.controls.append(
                SectionCard([saludo, mis_prestamos_list, ft.Row([btn_prestamos], alignment=ft.MainAxisAlignment.END)])
            )
            body.controls.append(
                SectionCard([mis_reservas_list, ft.Row([btn_reservas], alignment=ft.MainAxisAlignment.END)])
            )
        else:
            body.controls.append(
                SectionCard([
                    saludo or ft.Text(""),
                    ft.Text("Bienvenido. Usa el menú de la izquierda para navegar.", color=PAL["text_secondary"]),
                ])
            )
        body.update()

    def _on_theme_msg(msg):
        if isinstance(msg, dict) and msg.get("type") == "theme_changed":
            refresh_theme()

    page.pubsub.subscribe(_on_theme_msg)
    page.on_platform_brightness_change = lambda e: refresh_theme()

    # ---------------- Render raíz ----------------
    root = ft.Column(
        [
            titulo,
            body,
        ],
        expand=True,
        spacing=18,
        alignment=ft.MainAxisAlignment.START,
        scroll=ft.ScrollMode.AUTO,
    )
    return root
