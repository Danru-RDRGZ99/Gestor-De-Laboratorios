# ui/views/usuarios_view.py
from __future__ import annotations

import flet as ft
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from core.db import SessionLocal
from core.models import Usuario, Reserva, Prestamo


def UsuariosView(page: ft.Page):
    db = SessionLocal()

    me = page.session.get("user") or {}
    if me.get("rol") != "admin":
        return ft.Container(
            content=ft.Text("No autorizado", size=16, color="red"),
            padding=20,
        )

    # ---------- Paleta segura (compatible con cualquier Flet) ----------
    def palette():
        dark = page.theme_mode == ft.ThemeMode.DARK
        return {
            "section_bg": "#111827" if dark else "#F3F4F6",  # fondo suave de sección
            "card_bg":    "#1F2937" if dark else "#FFFFFF",  # tarjeta
            "border":     "#374151" if dark else "#E5E7EB",  # borde
            "text_sub":   "#CBD5E1" if dark else "#475569",  # texto secundario
        }

    PAL = palette()

    # ---------- Estado de filtros ----------
    state = {
        "q": "",       # texto de búsqueda
        "rol": "",     # "", "admin", "docente", "estudiante"
    }

    # ---------- Controles de filtros ----------
    tf_q = ft.TextField(
        label="Buscar (nombre / usuario / correo)",
        width=320,
        on_change=lambda e: on_change_q(),
        prefix_icon=ft.Icons.SEARCH,
    )

    dd_rol = ft.Dropdown(
        label="Rol",
        width=200,
        value="",
        options=[
            ft.dropdown.Option("", "Todos"),
            ft.dropdown.Option("admin", "admin"),
            ft.dropdown.Option("docente", "docente"),
            ft.dropdown.Option("estudiante", "estudiante"),
        ],
        on_change=lambda e: on_change_rol(),
    )

    btn_clear = ft.OutlinedButton("Limpiar", on_click=lambda e: clear_filters())

    header_filters = ft.Container(
        content=ft.Row(
            [tf_q, dd_rol, btn_clear],
            spacing=12,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=12,
        border_radius=12,
        bgcolor=PAL["section_bg"],
    )

    # ---------- Lista ----------
    list_col = ft.Column(spacing=10)

    # ---------- Confirmación de borrado ----------
    confirm_dlg = ft.AlertDialog(modal=True)
    page.dialog = confirm_dlg

    def open_confirm(uid: int, display: str):
        confirm_dlg.title = ft.Text("Eliminar usuario")
        confirm_dlg.content = ft.Text(
            f"¿Eliminar definitivamente a \"{display}\"?\n"
            "Nota: solo se eliminará si no tiene reservas ni préstamos vinculados."
        )
        confirm_dlg.actions = [
            ft.TextButton("Cancelar", on_click=lambda e: close_confirm()),
            ft.FilledButton("Eliminar", on_click=lambda e, _uid=uid: do_delete(_uid)),
        ]
        confirm_dlg.open = True
        page.update()

    def close_confirm():
        confirm_dlg.open = False
        page.update()

    # ---------- Acciones ----------
    def on_change_q():
        state["q"] = tf_q.value.strip()
        render_list()

    def on_change_rol():
        state["rol"] = dd_rol.value or ""
        render_list()

    def clear_filters():
        state["q"] = ""
        state["rol"] = ""
        tf_q.value = ""
        dd_rol.value = ""
        page.update()
        render_list()

    def search_users():
        q = db.query(Usuario)
        if state["rol"]:
            q = q.filter(Usuario.rol == state["rol"])
        if state["q"]:
            s = f"%{state['q'].lower()}%"
            q = q.filter(
                func.lower(Usuario.nombre).like(s) |
                func.lower(Usuario.user).like(s) |
                func.lower(Usuario.correo).like(s)
            )
        return q.order_by(Usuario.nombre.asc()).all()

    def count_reservas(uid: int) -> int:
        return db.query(func.count(Reserva.id)).filter(Reserva.usuario_id == uid).scalar() or 0

    def count_prestamos(uid: int) -> int:
        return db.query(func.count(Prestamo.id)).filter(Prestamo.usuario_id == uid).scalar() or 0

    def do_delete(uid: int):
        # No permitir borrarte a ti mismo
        if uid == me.get("id"):
            page.snack_bar = ft.SnackBar(ft.Text("No puedes eliminar tu propio usuario."), open=True)
            page.update()
            close_confirm()
            return

        # Validar dependencias
        r_cnt = count_reservas(uid)
        p_cnt = count_prestamos(uid)
        if (r_cnt + p_cnt) > 0:
            page.snack_bar = ft.SnackBar(
                ft.Text(f"No se puede eliminar: tiene {r_cnt} reserva(s) y {p_cnt} préstamo(s)."), open=True
            )
            page.update()
            close_confirm()
            return

        # Eliminar
        try:
            u = db.get(Usuario, uid)
            if not u:
                page.snack_bar = ft.SnackBar(ft.Text("Usuario no encontrado."), open=True)
                page.update()
                close_confirm()
                return
            db.delete(u)
            db.commit()
            page.snack_bar = ft.SnackBar(ft.Text("Usuario eliminado."), open=True)
            page.update()
            close_confirm()
            render_list()
        except SQLAlchemyError as ex:
            db.rollback()
            page.snack_bar = ft.SnackBar(ft.Text(f"Error al eliminar: {ex.__class__.__name__}"), open=True)
            page.update()
            close_confirm()

    # ---------- UI helpers ----------
    def role_chip(rol: str) -> ft.Control:
        return ft.Container(
            content=ft.Text(rol, size=12),
            padding=ft.padding.symmetric(4, 8),
            border_radius=20,
            border=ft.border.all(1, PAL["border"]),
        )

    def user_row(u: Usuario) -> ft.Control:
        uid = u.id
        reservas = count_reservas(uid)
        prestamos = count_prestamos(uid)

        left = ft.Column(
            [
                ft.Text(f"{u.nombre} · @{u.user}", size=15, weight=ft.FontWeight.W_600),
                ft.Text(u.correo or "-", size=12, color=PAL["text_sub"]),
                ft.Text(f"Reservas: {reservas} · Préstamos: {prestamos}", size=12, color=PAL["text_sub"]),
            ],
            spacing=3,
            expand=True,
        )
        right_actions: list[ft.Control] = []

        # No permitir borrar el usuario en sesión
        if uid == me.get("id"):
            right_actions.append(
                ft.OutlinedButton("Tú mismo", disabled=True)
            )
        else:
            right_actions.append(
                ft.OutlinedButton("Eliminar", on_click=lambda e, _uid=uid: open_confirm(_uid, u.nombre or u.user))
            )

        row = ft.Row(
            [left, ft.Row([role_chip(u.rol or "-")] + right_actions, spacing=8)],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return ft.Container(
            content=row,
            padding=12,
            border_radius=10,
            border=ft.border.all(1, PAL["border"]),
            bgcolor=PAL["card_bg"],
        )

    def render_list():
        list_col.controls.clear()
        rows = search_users()
        list_col.controls.append(
            ft.Text(f"Usuarios encontrados: {len(rows)}", size=12, color=PAL["text_sub"])
        )
        if not rows:
            list_col.controls.append(ft.Text("No hay usuarios que coincidan con el filtro.", color=PAL["text_sub"]))
        else:
            list_col.controls.extend([user_row(u) for u in rows])
        page.update()

    # ---------- Render inicial ----------
    render_list()

    return ft.Column(
        [
            ft.Text("Usuarios (admin)", size=22, weight=ft.FontWeight.BOLD),
            header_filters,
            list_col,
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=16,
    )
