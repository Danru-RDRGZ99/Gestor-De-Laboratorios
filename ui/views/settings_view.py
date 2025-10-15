# ui/views/settings_view.py
from __future__ import annotations

import re
import flet as ft
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_

from core.db import SessionLocal
from core.models import Usuario
from core.auth_service import verify_password, hash_password


EMAIL_RX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def SettingsView(page: ft.Page):
    db = SessionLocal()
    me = page.session.get("user")

    if not me:
        return ft.Container(
            content=ft.Text("Inicia sesión para ver esta página.", color="red"),
            padding=20,
        )

    # -------- Paleta segura (oscuro / claro) ----------
    def palette():
        dark = page.theme_mode == ft.ThemeMode.DARK
        return {
            "section_bg": "#111827" if dark else "#F3F4F6",
            "card_bg":    "#1F2937" if dark else "#FFFFFF",
            "border":     "#374151" if dark else "#E5E7EB",
            "text_sub":   "#CBD5E1" if dark else "#475569",
        }
    PAL = palette()

    # -------- Cargar desde BD para tener valores frescos ----------
    uobj: Usuario | None = db.get(Usuario, int(me["id"]))
    if not uobj:
        return ft.Container(
            content=ft.Text("Usuario no encontrado en la base de datos.", color="red"),
            padding=20,
        )

    # -------- Controles: Perfil ----------
    tf_nombre = ft.TextField(label="Nombre", value=uobj.nombre or "", width=360)
    tf_user   = ft.TextField(label="Usuario", value=uobj.user or "", width=240)
    tf_correo = ft.TextField(label="Correo",  value=uobj.correo or "", width=300)

    # El rol se muestra (solo lectura para no-admin)
    tf_rol = ft.TextField(label="Rol", value=uobj.rol or "", width=160, read_only=True)

    # -------- Controles: Contraseña ----------
    tf_pwd_actual = ft.TextField(label="Contraseña actual", password=True, can_reveal_password=True, width=280)
    tf_pwd_nueva  = ft.TextField(label="Nueva contraseña", password=True, can_reveal_password=True, width=280)
    tf_pwd_conf   = ft.TextField(label="Confirmar nueva", password=True, can_reveal_password=True, width=280)

    info = ft.Text("", color=PAL["text_sub"])

    # -------- Helpers ----------
    def snack(msg: str):
        page.snack_bar = ft.SnackBar(ft.Text(msg), open=True)
        page.update()

    def validate_profile_fields() -> str | None:
        nombre = (tf_nombre.value or "").strip()
        user   = (tf_user.value or "").strip()
        correo = (tf_correo.value or "").strip().lower()

        if not nombre or not user or not correo:
            return "Completa nombre, usuario y correo."
        if not EMAIL_RX.match(correo):
            return "Correo no válido."
        return None

    def save_profile(_=None):
        err = validate_profile_fields()
        if err:
            snack(err); return

        nombre = tf_nombre.value.strip()
        user   = tf_user.value.strip()
        correo = tf_correo.value.strip().lower()

        # Unicidad de user/correo (excepto yo)
        exists = (
            db.query(Usuario)
              .filter(
                  Usuario.id != uobj.id,
                  or_(Usuario.user == user, Usuario.correo == correo),
              )
              .first()
        )
        if exists:
            snack("Usuario o correo ya están registrados por otra cuenta.")
            return

        try:
            u = db.get(Usuario, uobj.id)
            if not u:
                snack("Usuario no encontrado."); return
            u.nombre = nombre
            u.user   = user
            u.correo = correo
            db.commit()

            # Actualizamos sesión para que la app muestre el nuevo nombre/correo/usuario
            session_user = page.session.get("user") or {}
            session_user["nombre"] = nombre
            session_user["user"]   = user
            session_user["correo"] = correo
            page.session.set("user", session_user)

            snack("Perfil actualizado.")
        except SQLAlchemyError as ex:
            db.rollback()
            snack(f"Error al guardar: {ex.__class__.__name__}")

    def change_password(_=None):
        cur = (tf_pwd_actual.value or "")
        new = (tf_pwd_nueva.value or "")
        cfm = (tf_pwd_conf.value or "")

        if not cur or not new or not cfm:
            snack("Completa todas las contraseñas (actual, nueva, confirmar).")
            return
        if new != cfm:
            snack("La confirmación no coincide.")
            return
        if len(new) < 6:
            snack("La nueva contraseña debe tener al menos 6 caracteres.")
            return

        # Verificación contra hash actual
        if not verify_password(cur, uobj.password_hash):
            snack("La contraseña actual no es correcta.")
            return

        try:
            u = db.get(Usuario, uobj.id)
            if not u:
                snack("Usuario no encontrado."); return
            u.password_hash = hash_password(new)
            db.commit()

            # Limpiamos campos
            tf_pwd_actual.value = ""
            tf_pwd_nueva.value  = ""
            tf_pwd_conf.value   = ""
            page.update()

            snack("Contraseña actualizada.")
        except SQLAlchemyError as ex:
            db.rollback()
            snack(f"Error al actualizar contraseña: {ex.__class__.__name__}")

    # -------- Tarjetas / Layout ----------
    perfil_card = ft.Container(
        content=ft.Column(
            [
                ft.Text("Perfil", size=16, weight=ft.FontWeight.W_600),
                ft.Row([tf_nombre, tf_user, tf_correo, tf_rol], spacing=12, wrap=True),
                ft.Row([ft.FilledButton("Guardar perfil", on_click=save_profile)], alignment=ft.MainAxisAlignment.END),
            ],
            spacing=12,
            tight=True,
        ),
        padding=16,
        border_radius=12,
        bgcolor=PAL["section_bg"],
    )

    pass_card = ft.Container(
        content=ft.Column(
            [
                ft.Text("Cambiar contraseña", size=16, weight=ft.FontWeight.W_600),
                ft.Row([tf_pwd_actual, tf_pwd_nueva, tf_pwd_conf], spacing=12, wrap=True),
                ft.Row([ft.FilledButton("Actualizar contraseña", on_click=change_password)], alignment=ft.MainAxisAlignment.END),
            ],
            spacing=12,
            tight=True,
        ),
        padding=16,
        border_radius=12,
        bgcolor=PAL["section_bg"],
    )

    root = ft.Column(
        [
            ft.Text("Ajustes", size=22, weight=ft.FontWeight.BOLD),
            perfil_card,
            pass_card,
            info,
        ],
        expand=True,
        spacing=16,
        scroll=ft.ScrollMode.AUTO,
    )
    return root
