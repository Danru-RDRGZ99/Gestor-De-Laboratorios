import flet as ft
from ui.components.inputs import TextField, Dropdown
from ui.components.buttons import Primary, Ghost
from ui.components.cards import Card
from core.auth_service import create_user

def RegisterView(page:ft.Page):
    nombre=TextField("Nombre completo", expand=True)
    correo=TextField("Correo", expand=True)
    usuario=TextField("Usuario", expand=True)
    clave=TextField("Contraseña (min 6)", password=True, expand=True)
    clave2=TextField("Confirmar contraseña", password=True, expand=True)
    rol=Dropdown("Rol", options=[("docente","Docente"),("estudiante","Estudiante")], width=240)
    info=ft.Text("", color=ft.Colors.RED_400)

    def do_register(e):
        if clave.value!=clave2.value:
            info.value="Las contraseñas no coinciden"; page.update(); return
        ok, res=create_user(
            nombre.value.strip(),
            correo.value.strip(),
            usuario.value.strip(),
            clave.value,
            rol.value if rol.value else ""
        )
        if not ok:
            info.value=str(res); page.update(); return
        # ⬇️ Auto-login y a dashboard
        page.session.set("user", res)
        page.go("/dashboard")

    def back_login(e):
        page.go("/")

    form=ft.Column(
        controls=[
            ft.Text("Crear cuenta", size=22, weight=ft.FontWeight.BOLD),
            nombre, correo, usuario, clave, clave2, rol,
            Primary("Registrarse", on_click=do_register, width=240, height=44),
            Ghost("Volver al inicio de sesión", on_click=back_login, width=240, height=40),
            info
        ],
        spacing=12, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER
    )

    return ft.Row(
        [ft.Container(content=Card(form, padding=24), width=520, alignment=ft.alignment.center)],
        alignment=ft.MainAxisAlignment.CENTER, expand=True
    )
