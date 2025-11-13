"""
LoginView mejorado para Flet con soporte para Google OAuth.
Proporciona un flujo de autenticación robusto y user-friendly.
"""

import flet as ft
import os
import base64
import logging
from typing import Callable, Optional

from api_client import ApiClient

logger = logging.getLogger(__name__)


def LoginView(page: ft.Page, api: ApiClient, on_success: Callable, is_mobile: bool) -> ft.Container:
    """
    Vista de login con soporte para autenticación tradicional y Google OAuth.
    
    Args:
        page: Página de Flet
        api: Cliente API para comunicarse con el backend
        on_success: Callback ejecutado tras login exitoso
        is_mobile: Si la aplicación está en modo móvil
        
    Returns:
        Container con la UI del login
    """
    
    # ========== ESTADO Y VARIABLES ==========
    info = ft.Text("", color=ft.Colors.RED_400, size=12)
    flash = page.session.get("flash")
    if flash:
        info.value = flash
        page.session.remove("flash")

    # ========== CAMPOS DE FORMULARIO ==========
    user_field = ft.TextField(
        label="Usuario o Correo",
        prefix_icon=ft.Icons.PERSON,
        autofocus=True,
        text_size=14,
    )
    pwd_field = ft.TextField(
        label="Contraseña",
        password=True,
        can_reveal_password=True,
        prefix_icon=ft.Icons.LOCK,
        text_size=14,
        on_submit=lambda e: do_login(),
    )

    # ========== FUNCIONES DE LÓGICA ==========
    def show_message(message: str, is_error: bool = True):
        """Muestra un mensaje al usuario."""
        info.value = message
        info.color = ft.Colors.RED_400 if is_error else ft.Colors.GREEN_400
        page.update()

    def set_loading(loading: bool, button: ft.Control):
        """Muestra/oculta indicador de carga en un botón."""
        if hasattr(button, 'disabled'):
            button.disabled = loading
        if hasattr(button, 'text'):
            button.text = "Cargando..." if loading else button.text
        page.update()

    def do_login():
        """Maneja el login tradicional con usuario/correo y contraseña."""
        username = user_field.value.strip()
        password = pwd_field.value or ""
        
        if not username or not password:
            show_message("Por favor, completa ambos campos.")
            return
        
        # Guardar intento en sesión y redirigir al CAPTCHA
        page.session.set("login_attempt", {"username": username, "password": password})
        page.go("/captcha-verify")

    def do_google_login(e):
        """Inicia el flujo de Google OAuth."""
        show_message("Iniciando sesión con Google...", is_error=False)
        page.update()
        
        # Aquí puedes usar google-auth-oauthlib o una solución alternativa
        # Por ahora, mostramos el diálogo para pegar el token manualmente
        show_google_token_dialog()

    def show_google_token_dialog():
        """
        Muestra un diálogo para que el usuario ingrese manualmente su Google ID Token.
        
        En una aplicación web real, esto se haría con un flujo OAuth completo.
        Para aplicaciones de escritorio/móvil con Flet, es común usar este flujo híbrido.
        """
        id_field = ft.TextField(
            label="Google ID Token",
            hint_text="Pega aquí el token de Google",
            multiline=True,
            min_lines=3,
            width=400,
        )
        status_text = ft.Text("", color=ft.Colors.RED_400, size=12)

        def submit_token(ev):
            token = (id_field.value or "").strip()
            if not token:
                status_text.value = "Por favor, pega un token válido."
                page.update()
                return

            status_text.value = "Verificando con Google..."
            page.update()

            # Llamar al endpoint de Google login
            result = api.login_with_google(token)
            
            if result and isinstance(result, dict) and result.get("access_token"):
                dialog.open = False
                page.update()
                show_message("¡Sesión iniciada!", is_error=False)
                page.update()
                # Pequeño delay para que vea el mensaje
                import time
                time.sleep(1)
                on_success()
            else:
                error_msg = result.get("error") if isinstance(result, dict) else "Error desconocido"
                status_text.value = f"Error: {error_msg}"
                status_text.color = ft.Colors.RED_400
                page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Iniciar sesión con Google"),
            content=ft.Column([
                ft.Text(
                    "1. Abre tu navegador\n"
                    "2. Ve a https://accounts.google.com/o/oauth2/v2/auth\n"
                    "3. Obtén tu ID Token\n"
                    "4. Pégalo abajo",
                    size=11,
                ),
                ft.Divider(),
                id_field,
                status_text,
            ], tight=True, scroll=ft.ScrollMode.AUTO),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: (
                    setattr(dialog, 'open', False),
                    page.update()
                )),
                ft.FilledButton("Continuar", on_click=submit_token),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.dialog = dialog
        dialog.open = True
        page.update()

    # ========== VALIDACIÓN DE FORMULARIO ==========
    def validate(_):
        """Habilita/deshabilita botón según validación."""
        btn_login.disabled = not (user_field.value.strip() and pwd_field.value)
        page.update()

    user_field.on_change = validate
    pwd_field.on_change = validate
    validate(None)

    # ========== BOTONES ==========
    btn_login = ft.OutlinedButton(
        "Entrar",
        on_click=lambda e: do_login(),
        width=260,
        height=46,
    )
    btn_register = ft.OutlinedButton(
        "Registrarse",
        on_click=lambda e: page.go("/register"),
        width=260,
        height=40,
    )
    btn_google = ft.OutlinedButton(
        "Iniciar sesión con Google",
        icon=ft.Icon(ft.Icons.LOGIN),
        on_click=do_google_login,
        width=260,
        height=44,
    )

    # ========== LOGO ==========
    LOGO_PATH = "ui/assets/a.png"
    logo_b64 = None
    try:
        if os.path.exists(LOGO_PATH):
            with open(LOGO_PATH, "rb") as image_file:
                logo_b64 = base64.b64encode(image_file.read()).decode("utf-8")
        else:
            logger.warning(f"Logo no encontrado en: {LOGO_PATH}")
    except Exception as e:
        logger.error(f"Error al cargar el logo: {e}")

    if logo_b64:
        logo_content = ft.Image(src_base64=logo_b64, fit=ft.ImageFit.COVER)
    else:
        logo_content = ft.Icon(ft.Icons.SCIENCE, size=34)

    logo = ft.Container(
        content=logo_content,
        width=56,
        height=56,
        alignment=ft.alignment.center
    )

    # ========== ENCABEZADO ==========
    header = ft.Column(
        [
            logo,
            ft.Text("BLACKLAB", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("Inicia sesión para gestionar reservas y recursos", size=12, opacity=0.8),
        ],
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # ========== FORMULARIO ==========
    form = ft.Column(
        controls=[
            header,
            ft.Divider(opacity=0.2),
            user_field,
            pwd_field,
            info,
            ft.Container(height=4),
            btn_login,
            ft.Container(height=10),
            ft.Text("O", size=12, opacity=0.6, text_align=ft.TextAlign.CENTER),
            ft.Container(height=6),
            btn_google,
            ft.Container(height=10),
            ft.Text("¿No tienes cuenta?", size=11, opacity=0.7, text_align=ft.TextAlign.CENTER),
            btn_register,
        ],
        spacing=10,
        tight=True,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # ========== CARD CONTAINER ==========
    card_container = ft.Container(
        content=ft.Card(
            content=ft.Padding(form, padding=22),
        ),
        width=440,
    )

    # ========== MAIN CONTAINER ==========
    main_container = ft.Container(
        expand=True,
        content=ft.Row(
            [card_container],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.MainAxisAlignment.CENTER
        ),
        padding=20,
    )

    # ========== ADAPTACIÓN MÓVIL ==========
    if is_mobile:
        card_container.width = None
        main_container.padding = 0
        main_container.vertical_alignment = ft.MainAxisAlignment.START
        main_container.content.vertical_alignment = ft.MainAxisAlignment.START

    return main_container
