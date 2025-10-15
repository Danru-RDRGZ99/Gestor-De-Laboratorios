import flet as ft

def DataTable(columns:list[str]):
    return ft.DataTable(
        columns=[ft.DataColumn(ft.Text(c)) for c in columns],
        rows=[],
        heading_row_height=38,
        data_row_min_height=36,
        data_row_max_height=44,
        column_spacing=20
    )

def Row(cells:list[str|ft.Control]):
    _cells=[ft.DataCell(ft.Text(c)) if isinstance(c,str) else ft.DataCell(c) for c in cells]
    return ft.DataRow(cells=_cells)
