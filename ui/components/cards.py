import flet as ft

def Card(content:ft.Control, padding=16, radius=12, expand=False):
    return ft.Container(
        content=content,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        padding=padding,
        border_radius=radius,
        expand=expand
    )

def Stat(title:str, value:str):
    return Card(
        ft.Column(
            controls=[ft.Text(title), ft.Text(value, size=22, weight=ft.FontWeight.BOLD)],
            tight=True
        ),
        padding=18
    )
