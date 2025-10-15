import flet as ft
from .buttons import Primary, Ghost, Danger

def confirm(page:ft.Page, title:str, content:str, on_yes, on_no=None, yes_text="Sí", no_text="No"):
    dlg=ft.AlertDialog(
        title=ft.Text(title),
        content=ft.Text(content),
        actions=[
            Primary(yes_text, on_click=lambda e: (on_yes(e), page.close(dlg))),
            Ghost(no_text, on_click=lambda e: page.close(dlg))
        ]
    )
    page.dialog=dlg
    dlg.open=True
    page.update()

def danger_confirm(page:ft.Page, title:str, content:str, on_yes, on_no=None, yes_text="Eliminar", no_text="Cancelar"):
    dlg=ft.AlertDialog(
        title=ft.Text(title),
        content=ft.Text(content),
        actions=[
            Danger(yes_text, on_click=lambda e: (on_yes(e), page.close(dlg))),
            Ghost(no_text, on_click=lambda e: page.close(dlg))
        ]
    )
    page.dialog=dlg
    dlg.open=True
    page.update()
