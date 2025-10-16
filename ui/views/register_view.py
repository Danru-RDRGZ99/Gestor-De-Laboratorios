import flet as ft
# ANTES: from core.auth_service import register_user
from core import auth_service # AHORA: Importa el módulo
from core.schemas import UserCreate
from .login_view import LoginView
from core.db import SessionLocal

class RegisterView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.route = "/register"
        self.page = page
        self.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER

        self.username_field = ft.TextField(label="Usuario", width=300)
        self.password_field = ft.TextField(label="Contraseña", password=True, width=300)

        def register_clicked(e):
            db = SessionLocal()
            try:
                new_user = UserCreate(username=self.username_field.value, password=self.password_field.value)
                # ANTES: user = register_user(db, new_user)
                user = auth_service.register_user(db, new_user) # AHORA: Usa auth_service.register_user
                if user:
                    self.page.go("/")
                else:
                    # Considerar añadir manejo de errores aquí, ej. usuario ya existe
                    pass
            finally:
                db.close()

        self.controls = [
            ft.Column(
                [
                    ft.Text("Registro", size=30),
                    self.username_field,
                    self.password_field,
                    ft.ElevatedButton("Registrarse", on_click=register_clicked),
                    ft.TextButton("¿Ya tienes cuenta? Inicia Sesión", on_click=lambda e: self.page.go("/")),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        ]
