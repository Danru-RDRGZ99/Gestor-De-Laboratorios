import flet as ft
from ui.theme import apply_theme
from ui.views.login_view import LoginView
from ui.views.dashboard_view import DashboardView
from ui.views.laboratorios_view import LaboratoriosView
from ui.views.reservas_view import ReservasView
from ui.views.planteles_view import PlantelesView
from ui.views.prestamos_view import PrestamosView
from ui.views.register_view import RegisterView
from ui.views.usuarios_view import UsuariosView
from ui.views.settings_view import SettingsView  # <-- NUEVO
from core.auth_service import init_db
from core.rbac import allowed_routes

ROUTE_META = {
    "dashboard": ("Dashboard", ft.Icons.DASHBOARD),
    "planteles": ("Planteles", ft.Icons.DOMAIN),
    "laboratorios": ("Laboratorios", ft.Icons.COMPUTER),
    "recursos": ("Préstamos", ft.Icons.INVENTORY),
    "reservas": ("Reservas", ft.Icons.BOOKMARK_ADD),
    "usuarios": ("Usuarios", ft.Icons.SUPERVISED_USER_CIRCLE),
    "ajustes": ("Ajustes", ft.Icons.SETTINGS),  # <-- NUEVO
}
ORDER = ["dashboard", "planteles", "laboratorios", "recursos", "reservas", "usuarios", "ajustes"]

NAV_WIDTH = 88

def main(page: ft.Page):
    page.title = "Gestor de Laboratorios"
    page.padding = 0
    page.window_min_width = 1060
    page.window_min_height = 680

    apply_theme(page)
    init_db()

    def is_nav_collapsed() -> bool:
        return bool(page.session.get("nav_collapsed") or False)

    refs: dict[str, ft.Control | None] = {"spacer": None, "nav_overlay": None, "menu_btn": None}

    def toggle_nav(_):
        collapsed = not is_nav_collapsed()
        page.session.set("nav_collapsed", collapsed)

        sp: ft.Container | None = refs.get("spacer")  # type: ignore
        if sp is not None:
            sp.width = 0 if collapsed else NAV_WIDTH
            if sp.page is not None:
                sp.update()

        ov: ft.Container | None = refs.get("nav_overlay")  # type: ignore
        if ov is not None:
            ov.left = -NAV_WIDTH if collapsed else 0
            if ov.page is not None:
                ov.update()

        mb: ft.IconButton | None = refs.get("menu_btn")  # type: ignore
        if mb is not None:
            mb.icon = ft.Icons.MENU if collapsed else ft.Icons.MENU_OPEN
            if mb.page is not None:
                mb.update()

    def logout(e):
        page.session.remove("user")
        page.go("/")

    def handle_resize(_):
        ov: ft.Container | None = refs.get("nav_overlay")  # type: ignore
        if ov is not None:
            ov.height = page.height
            if ov.page is not None:
                ov.update()

    page.on_resize = handle_resize

    def build_shell(active_key: str, body: ft.Control):
        u = page.session.get("user")
        allowed = [k for k in ORDER if k in allowed_routes(u["rol"])]
        if active_key not in allowed:
            active_key = allowed[0]
        idx = allowed.index(active_key)

        collapsed = is_nav_collapsed()
        menu_icon = ft.Icons.MENU if collapsed else ft.Icons.MENU_OPEN
        menu_btn = ft.IconButton(menu_icon, tooltip="Mostrar/Ocultar menú", on_click=toggle_nav)
        refs["menu_btn"] = menu_btn

        # Toggle tema
        def toggle_theme(_):
            cur = page.theme_mode
            new_mode = ft.ThemeMode.LIGHT if cur == ft.ThemeMode.DARK else ft.ThemeMode.DARK
            apply_theme(page, new_mode)
            router(None)

        theme_icon = ft.Icons.DARK_MODE if page.theme_mode == ft.ThemeMode.LIGHT else ft.Icons.LIGHT_MODE
        theme_btn = ft.IconButton(theme_icon, tooltip="Cambiar tema", on_click=toggle_theme)

        # Botón ajustes -> /ajustes
        settings_btn = ft.IconButton(ft.Icons.SETTINGS, tooltip="Ajustes de cuenta", on_click=lambda e: page.go("/ajustes"))

        top = ft.Container(
            content=ft.Row(
                [
                    menu_btn,
                    ft.Text(ROUTE_META[active_key][0]),
                    ft.Container(expand=True),
                    settings_btn,  # <-- NUEVO botón
                    theme_btn,
                    ft.Text(u["user"]),
                    ft.IconButton(ft.Icons.LOGOUT, on_click=logout),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=12,
        )

        # NAV
        destinations = [ft.NavigationRailDestination(icon=ROUTE_META[k][1], label=ROUTE_META[k][0]) for k in allowed]
        def nav_change(e):
            i = e.control.selected_index
            page.go("/" + allowed[i])

        rail = ft.NavigationRail(selected_index=idx, destinations=destinations, on_change=nav_change, min_width=72, extended=False)
        divider = ft.VerticalDivider(width=1)
        rail_row = ft.Row([rail, divider], spacing=0, tight=True)

        nav_overlay = ft.Container(
            content=rail_row, left=(-NAV_WIDTH if collapsed else 0), top=0, width=NAV_WIDTH, height=page.height,
            animate_position=ft.Animation(300, ft.AnimationCurve.EASE_IN_OUT),
        )
        refs["nav_overlay"] = nav_overlay

        spacer = ft.Container(width=(0 if collapsed else NAV_WIDTH), animate=ft.Animation(300, ft.AnimationCurve.EASE_IN_OUT))
        refs["spacer"] = spacer

        body_container = ft.Container(expand=True, content=body, alignment=ft.alignment.top_left, padding=0)
        base_row = ft.Row([spacer, body_container], expand=True, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START)

        main_stack = ft.Stack(controls=[base_row, nav_overlay], expand=True)
        return ft.View("/" + active_key, [top, main_stack], padding=0)

    def route_key():
        r = page.route.strip("/")
        return r if r else ""

    def ensure_allowed(r, u):
        if r == "":
            return True
        allow = allowed_routes(u["rol"])
        if r not in allow:
            page.go("/" + allow[0])
            return False
        return True

    def view_for(key: str):
        if key == "dashboard": return DashboardView(page)
        if key == "planteles": return PlantelesView(page)
        if key == "laboratorios": return LaboratoriosView(page)
        if key == "recursos": return PrestamosView(page)
        if key == "reservas": return ReservasView(page)
        if key == "usuarios": return UsuariosView(page)
        if key == "ajustes": return SettingsView(page)  # <-- NUEVO
        return DashboardView(page)

    def router(_):
        page.views.clear()
        u = page.session.get("user")
        rkey = route_key()

        if not u:
            if rkey == "":
                page.views.append(ft.View("/", [LoginView(page, lambda: page.go("/dashboard"))]))
            elif rkey == "register":
                page.views.append(ft.View("/register", [RegisterView(page)]))
            else:
                page.go("/")
        else:
            if not ensure_allowed(rkey, u):
                return
            if rkey == "":
                page.go("/dashboard")
                return
            body = view_for(rkey)
            page.views.append(build_shell(rkey, body))
        page.update()

    page.on_route_change = router
    page.go("/")

ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=8550)
