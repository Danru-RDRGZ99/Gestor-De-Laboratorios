import flet as ft

RADIUS=10
PAD=ft.Padding(12,10,12,10)

PRIMARY=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=RADIUS), padding=PAD)
TONAL=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=RADIUS), padding=PAD)
OUTLINE=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=RADIUS), padding=PAD)
GHOST=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=RADIUS), padding=PAD)
DANGER=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=RADIUS), padding=PAD, bgcolor=ft.Colors.ERROR_CONTAINER, color=ft.Colors.ON_ERROR_CONTAINER)

def Primary(text, on_click=None, icon=None, width=220, height=44, disabled=False):
    return ft.FilledButton(text, icon=icon, on_click=on_click, width=width, height=height, style=PRIMARY, disabled=disabled)

def Tonal(text, on_click=None, icon=None, width=220, height=44, disabled=False):
    return ft.FilledTonalButton(text, icon=icon, on_click=on_click, width=width, height=height, style=TONAL, disabled=disabled)

def Outline(text, on_click=None, icon=None, width=220, height=44, disabled=False):
    return ft.OutlinedButton(text, icon=icon, on_click=on_click, width=width, height=height, style=OUTLINE, disabled=disabled)

def Ghost(text, on_click=None, icon=None, width=220, height=44, disabled=False):
    return ft.TextButton(text, icon=icon, on_click=on_click, width=width, height=height, style=GHOST, disabled=disabled)

def Danger(text, on_click=None, icon=ft.Icons.WARNING_AMBER, width=220, height=44, disabled=False):
    return ft.FilledButton(text, icon=icon, on_click=on_click, width=width, height=height, style=DANGER, disabled=disabled)

def Icon(icon, tooltip=None, on_click=None):
    return ft.IconButton(icon, tooltip=tooltip, on_click=on_click)
