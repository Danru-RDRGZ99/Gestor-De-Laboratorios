# ui/theme.py
import flet as ft

def apply_theme(page: ft.Page, preferred: ft.ThemeMode | None = None):
    """
    Aplica el tema leyendo de la sesión si existe, o usando `preferred` si se pasa.
    Si no hay nada guardado, usa oscuro por defecto.
    """
    # Lee preferencia guardada
    saved = (page.session.get("theme_mode") or "").lower()

    # Decide el modo final
    if preferred is not None:
        page.theme_mode = preferred
        page.session.set("theme_mode", "light" if preferred == ft.ThemeMode.LIGHT else "dark")
    elif saved in ("light", "dark"):
        page.theme_mode = ft.ThemeMode.LIGHT if saved == "light" else ft.ThemeMode.DARK
    else:
        # por defecto: oscuro
        page.theme_mode = ft.ThemeMode.DARK
        page.session.set("theme_mode", "dark")

    # Tema base (Material 3); puedes cambiar el seed si quieres otro acento
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE)
