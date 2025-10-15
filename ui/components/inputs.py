import flet as ft

def TextField(label:str, value:str="", password:bool=False, expand:bool=False, width:int|None=None, read_only:bool=False, can_reveal:bool=True):
    return ft.TextField(label=label, value=value, password=password, can_reveal_password=can_reveal, expand=expand, width=width, read_only=read_only)

def Dropdown(label:str, options:list[str]|list[tuple]=(), width:int|None=None, value:str|None=None):
    opts=[ft.dropdown.Option(o) if isinstance(o,str) else ft.dropdown.Option(o[0], text=o[1]) for o in options]
    return ft.Dropdown(label=label, options=opts, width=width, value=value)

def DateBadge(date_str:str, width=160):
    return ft.TextField(value=date_str, read_only=True, width=width, text_align=ft.TextAlign.CENTER)

def SearchBox(placeholder:str="Buscar", on_change=None, width:int=260):
    return ft.TextField(hint_text=placeholder, prefix_icon=ft.Icons.SEARCH, on_change=on_change, width=width, dense=True)
