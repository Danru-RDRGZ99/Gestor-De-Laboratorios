import flet as ft
from core.auth_service import login
from ui.components.buttons import Primary, Ghost
from ui.components.cards import Card

def LoginView(page: ft.Page, on_success):
    # --- Estado / mensajes ---
    info = ft.Text("", color=ft.Colors.RED_400, size=12)
    flash = page.session.get("flash")
    if flash:
        info.value = flash
        page.session.remove("flash")

    # --- Campos ---
    user = ft.TextField(
        label="Usuario",
        prefix_icon=ft.Icons.PERSON,
        autofocus=True,
        dense=False,
        text_size=14,
    )
    pwd = ft.TextField(
        label="Contraseña",
        password=True,
        can_reveal_password=True,
        prefix_icon=ft.Icons.LOCK,
        dense=False,
        text_size=14,
        on_submit=lambda e: do_login(e),  # Enter en contraseña -> login
    )

    # --- Acciones ---
    btn_login = Primary("Entrar", on_click=lambda e: do_login(e), width=260, height=46)
    btn_register = Ghost("Registrarse", on_click=lambda e: page.go("/register"), width=260, height=40)

    def validate():
        btn_login.disabled = not (user.value.strip() and (pwd.value or ""))
        page.update()

    user.on_change = lambda e: validate()
    pwd.on_change = lambda e: validate()
    validate()

    # --- Helpers para normalizar el usuario que devuelve login() ---
    def _pick(d_or_obj, *keys, default=None):
        """Toma la primera llave/atributo existente y no vacía."""
        for k in keys:
            if isinstance(d_or_obj, dict):
                val = d_or_obj.get(k)
            else:
                val = getattr(d_or_obj, k, None)
            if val is not None and str(val).strip() != "":
                return val
        return default

    def _as_int(v, default=None):
        try:
            return int(v)
        except Exception:
            return default

    def normalize_user(raw, fallback_user_input: str):
        """
        Convierte el resultado de login() (dict/obj) a:
        {
          "id": int,
          "user": str,
          "correo": str,
          "rol": "admin" | "docente" | "estudiante" | ...
        }
        """
        uid = _as_int(_pick(raw, "id", "user_id", "usuario_id"))
        uname = _pick(raw, "user", "username", "nombre", "name", "display_name") or fallback_user_input
        mail = _pick(raw, "correo", "email", "mail")

        rol = _pick(raw, "rol", "role")
        if not rol:
            is_admin = _pick(raw, "is_admin", "admin", "es_admin", "superuser", default=False)
            try:
                rol = "admin" if bool(is_admin) else "user"
            except Exception:
                rol = "user"

        return {
            "id": uid,
            "user": str(uname) if uname is not None else "",
            "correo": str(mail) if mail is not None else "",
            "rol": str(rol),
        }

    # --- Acción de login ---
    def do_login(e):
        username = user.value.strip()
        password = pwd.value or ""

        r = login(username, password)
        if not r:
            info.value = "Usuario o contraseña incorrectos"
            page.update()
            return

        norm = normalize_user(r, username)
        if norm["id"] is None:
            info.value = "No se recibió un ID de usuario válido desde el servidor."
            page.update()
            return
        if not norm["rol"]:
            norm["rol"] = "user"

        # Guardamos en sesión con alias compatibles para otras vistas
        session_user = {
            "id": norm["id"],
            "user": norm["user"],
            "username": norm["user"],   # alias
            "nombre": norm["user"],     # alias
            "correo": norm["correo"],
            "email": norm["correo"],    # alias
            "rol": norm["rol"],
        }
        page.session.set("user", session_user)

        # Debug: ver sesión en consola tras login
        print("SESSION USER =>", page.session.get("user"))

        on_success()

    # --- Encabezado ---
    logo = ft.Container(
        content=ft.Icon(ft.Icons.SCIENCE, size=34),
        width=56,
        height=56,
        bgcolor=ft.Colors.SURFACE_TINT,
        border_radius=9999,
        alignment=ft.alignment.center,
    )

    header = ft.Column(
        [
            logo,
            ft.Text("Laboratorios", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("Inicia sesión para gestionar reservas y recursos", size=12, opacity=0.8),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # --- Formulario ---
    form = ft.Column(
        controls=[
            header,
            ft.Divider(opacity=0.2),
            user,
            pwd,
            info,
            ft.Container(height=4),
            btn_login,
            btn_register,
        ],
        spacing=14,
        tight=True,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # --- Tarjeta ---
    card = Card(form, padding=22)
    card = ft.Container(
        content=card,
        width=440,
        border_radius=16,
        shadow=ft.BoxShadow(
            blur_radius=16,
            spread_radius=1,
            color=ft.Colors.with_opacity(0.18, ft.Colors.BLACK)
        ),
    )

    # --- Layout general ---
    shell = ft.Container(
        expand=True,
        bgcolor=ft.Colors.SURFACE,
        content=ft.Row(
            [ft.Container(expand=True), card, ft.Container(expand=True)],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=20,
    )

    return shell
