import flet as ft
from ui.views.login_view import LoginView
from ui.views.register_view import RegisterView
from ui.views.dashboard_view import DashboardView
from core.store import AppStore

def main(page: ft.Page):
    try:
        page.title = "Gestor de Laboratorios"
        page.vertical_alignment = ft.MainAxisAlignment.CENTER
        page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        
        pr = ft.ProgressRing(width=16, height=16, stroke_width=2)
        page.add(ft.Text("Iniciando..."), pr)
        page.update()

        store = AppStore(page)
        page.store = store
        
        def route_change(route):
            page.views.clear()
            if page.route == "/register":
                page.views.append(RegisterView(page))
            elif page.route == "/dashboard":
                page.views.append(DashboardView(page))
            else:
                page.views.append(LoginView(page))
            page.update()

        def view_pop(view):
            page.views.pop()
            top_view = page.views[-1]
            page.go(top_view.route)

        page.on_route_change = route_change
        page.on_view_pop = view_pop
        page.go(page.route)

    except Exception as e:
        page.clean()
        error_text = ft.Text(f"Ha ocurrido un error al iniciar la app:\n\n{e}", size=14, selectable=True)
        page.add(ft.Container(content=error_text, padding=15))
        page.update()

# Para ejecutar en el navegador (opcional)
if __name__ == "__main__":
    ft.app(target=main)
