import flet as ft
# ANTES: from core.auth_service import login
from core import auth_service # AHORA: Importa el módulo
from .dashboard_view import DashboardView
from core.schemas import UserLogin
from core.db import SessionLocal

class LoginView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.route = "/"
        self.page = page
        self.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER

        self.username_field = ft.TextField(label="Usuario", width=300)
        self.password_field = ft.TextField(label="Contraseña", password=True, width=300)

        def login_clicked(e):
            db = SessionLocal()
            try:
                user_login = UserLogin(username=self.username_field.value, password=self.password_field.value)
                # ANTES: user_data = login(db, user_login)
                user_data = auth_service.login(db, user_login) # AHORA: Usa auth_service.login
                if user_data:
                    self.page.session.set("access_token", user_data["access_token"])
                    self.page.go("/dashboard")
                else:
                    self.page.snack_bar = ft.SnackBar(ft.Text("Usuario o contraseña incorrectos"), open=True)
                    self.page.update()
            finally:
                db.close()

        self.controls = [
            ft.Column(
                [
                    ft.Text("Iniciar Sesión", size=30),
                    self.username_field,
                    self.password_field,
                    ft.ElevatedButton("Iniciar Sesión", on_click=login_clicked),
                    ft.TextButton("¿No tienes cuenta? Regístrate", on_click=lambda e: self.page.go("/register")),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        ]
