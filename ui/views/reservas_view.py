import flet as ft
from datetime import datetime, date, time, timedelta
from core.db import SessionLocal
from core.models import Reserva, Laboratorio, Usuario, Plantel
from ui.components.buttons import Primary, Tonal, Icon, Danger, Ghost
from ui.components.cards import Card


def ReservasView(page: ft.Page):
    db = SessionLocal()
    u = page.session.get("user")

    # ---- Catálogos ----
    planteles = db.query(Plantel).order_by(Plantel.nombre.asc()).all()
    labs_all = db.query(Laboratorio).order_by(Laboratorio.nombre.asc()).all()

    # Mapa id->nombre del laboratorio (según plantel seleccionado)
    lab_map: dict[str, str] = {}

    # ---- Filtros (ft.Dropdown nativo) ----
    dd_plantel = ft.Dropdown(
        label="Plantel",
        width=260,
        options=[ft.dropdown.Option(str(p.id), p.nombre) for p in planteles],
    )
    dd_lab = ft.Dropdown(
        label="Laboratorio",
        width=320,
        options=[],   # se llenará según el plantel
    )

    info = ft.Text("")
    grid = ft.ResponsiveRow(run_spacing=12, spacing=12)
    state = {"confirm_for": None}

    # ---- Calendario / ventana de 5 días hábiles ----
    def is_weekend(d: date) -> bool: return d.weekday() >= 5

    def next_weekday(d: date, step: int = 1):
        n = d + timedelta(days=step)
        while is_weekend(n):
            n = n + timedelta(days=1 if step >= 0 else -1)
        return n

    today = date.today()
    start = today if not is_weekend(today) else next_weekday(today, 1)
    window = {"start": start}

    day_names_short = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    head_label = ft.Text("", size=18, weight=ft.FontWeight.W_600)

    prev_btn = Icon(ft.Icons.CHEVRON_LEFT, "Ventana anterior", on_click=lambda e: goto_prev())
    next_btn = Icon(ft.Icons.CHEVRON_RIGHT, "Siguiente ventana", on_click=lambda e: goto_next())

    header = ft.Row(
        [prev_btn, head_label, next_btn, ft.Container(expand=True), dd_plantel, dd_lab],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER
    )

    legend = ft.Row([
        ft.Chip(label=ft.Text("Disponible"), leading=ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE)),
        ft.Chip(label=ft.Text("Reservado"), leading=ft.Icon(ft.Icons.BLOCK)),
        ft.Chip(label=ft.Text("Descanso"), leading=ft.Icon(ft.Icons.SCHEDULE))
    ], spacing=8)

    def five_weekdays_from(d: date):
        days = []; cur = d
        while len(days) < 5:
            if not is_weekend(cur): days.append(cur)
            cur = cur + timedelta(days=1)
        return days

    def five_weekdays_before(end_exclusive: date):
        days = []; cur = end_exclusive - timedelta(days=1)
        while len(days) < 5:
            if not is_weekend(cur): days.append(cur)
            cur = cur - timedelta(days=1)
        return sorted(days)

    def goto_next():
        days = five_weekdays_from(window["start"])
        window["start"] = next_weekday(days[-1], 1)
        state["confirm_for"] = None
        render()

    def goto_prev():
        prev_days = five_weekdays_before(window["start"])
        window["start"] = prev_days[0]
        state["confirm_for"] = None
        render()

    # ---- Slots del día (7:00 a 14:30, con descanso 10:00–10:30) ----
    def defined_slots(d: date):
        slots = []
        def add(h1, m1, h2, m2, kind="slot"):
            s = datetime.combine(d, time(h1, m1)); f = datetime.combine(d, time(h2, m2))
            slots.append((s, f, kind))
        add(7,0,8,0); add(8,0,9,0); add(9,0,10,0)
        add(10,0,10,30,"break")
        add(10,30,11,30); add(11,30,12,30); add(12,30,13,30); add(13,30,14,30)
        return slots

    def slot_label(s: datetime, f: datetime): return f"{s.strftime('%H:%M')}–{f.strftime('%H:%M')}"

    # ---- Consultas ----
    def reservations_between(lab_id: int, start_dt: datetime, end_dt: datetime):
        return db.query(Reserva, Usuario.nombre, Usuario.id)\
                 .join(Usuario, Usuario.id == Reserva.usuario_id)\
                 .filter(Reserva.laboratorio_id == lab_id,
                         Reserva.estado != "cancelada",
                         Reserva.inicio >= start_dt,
                         Reserva.inicio < end_dt)\
                 .all()

    def create_reservation(lab_id: int, s: datetime, f: datetime):
        db.add(Reserva(usuario_id=u["id"], laboratorio_id=lab_id, inicio=s, fin=f, estado="activa"))
        db.commit()

    def cancel_reservation(rid: int):
        r = db.get(Reserva, rid)
        if not r:
            info.value = "Reserva no encontrada"; page.update(); return
        if not (u["rol"] == "admin" or u["id"] == r.usuario_id):
            info.value = "No tienes permiso para cancelar"; page.update(); return
        r.estado = "cancelada"
        db.commit()
        state["confirm_for"] = None
        info.value = "Reserva cancelada"
        render()

    def ask_inline_cancel(rid: int, etiqueta: str):
        state["confirm_for"] = rid
        info.value = f"Confirmar cancelación de {etiqueta}"
        render()

    # ---- UI por día ----
    def day_section(d: date, lid: int, day_reserveds: list[tuple]):
        title = ft.Text(f"{day_names_short[d.weekday()]} {d.strftime('%d/%m')}", size=16, weight=ft.FontWeight.W_600)

        tiles = []
        intervals = [(r.inicio, r.fin, r.id, nombre, uid) for (r, nombre, uid) in day_reserveds]

        for s, f, k in defined_slots(d):
            if k == "break":
                tiles.append(Tonal(f"Descanso {slot_label(s, f)}", disabled=True, width=200, height=50)); continue
            found = None
            for rs, rf, rid, nombre, uid in intervals:
                if rs < f and rf > s:
                    found = (rid, nombre, uid); break
            if found:
                rid, nombre, uid = found
                label = f"Reservado {slot_label(s, f)} · {nombre}"
                can_manage = (u["id"] == uid or u["rol"] == "admin")
                if can_manage and state["confirm_for"] == rid:
                    tiles.append(
                        ft.Row([
                            Danger("Confirmar", on_click=lambda e, _rid=rid: cancel_reservation(_rid), width=120, height=44),
                            Ghost("Volver", on_click=lambda e: (state.__setitem__("confirm_for", None), render()), width=72, height=44),
                        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                    )
                elif can_manage:
                    tiles.append(Tonal(label, on_click=lambda e, _rid=rid, _lab=label: ask_inline_cancel(_rid, _lab), width=200, height=50))
                else:
                    tiles.append(Tonal(label, disabled=True, width=200, height=50))
            else:
                def on_book(ss, ff):
                    def _(_):
                        create_reservation(lid, ss, ff)
                        info.value = "Reserva creada"
                        state["confirm_for"] = None
                        render()
                    return _
                tiles.append(Primary(slot_label(s, f), on_click=on_book(s, f), width=200, height=50))

        slots_row = ft.Row(controls=tiles, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER, scroll=ft.ScrollMode.AUTO)
        body = ft.Column([title, slots_row], spacing=10, tight=True)
        return ft.Container(content=Card(body, padding=14), col={"xs": 12})

    # ---- Dependencia Plantel → Laboratorio ----
    def set_lab_options_for_plantel(pid: int | None):
        """Ajusta opciones y valor actual del dropdown de laboratorio según plantel."""
        nonlocal lab_map
        if pid is None:
            filtered = []
        else:
            filtered = [l for l in labs_all if l.plantel_id == pid]

        dd_lab.options = [ft.dropdown.Option(str(l.id), l.nombre) for l in filtered]
        dd_lab.value = (str(filtered[0].id) if filtered else None)
        lab_map = {str(l.id): l.nombre for l in filtered}

    # ---- Render principal ----
    def render_header():
        days = five_weekdays_from(window["start"])
        lab_name = lab_map.get(str(int(dd_lab.value)), "") if dd_lab.value else ""
        head_label.value = f"{day_names_short[days[0].weekday()]} {days[0].strftime('%d/%m')} — {day_names_short[days[-1].weekday()]} {days[-1].strftime('%d/%m')} · {lab_name}"
        page.update()

    def render_grid():
        grid.controls.clear()
        if not dd_lab.value:
            page.update(); return

        lid = int(dd_lab.value)
        days = five_weekdays_from(window["start"])

        window_start_dt = datetime.combine(days[0], time(0,0))
        window_end_dt = datetime.combine(days[-1], time(23,59,59))
        all_rows = reservations_between(lid, window_start_dt, window_end_dt + timedelta(seconds=1))

        by_day = {d: [] for d in days}
        for r, nombre, uid in all_rows:
            dkey = r.inicio.date()
            if dkey in by_day:
                by_day[dkey].append((r, nombre, uid))

        for d in days:
            day_res = by_day.get(d, [])
            grid.controls.append(day_section(d, lid, day_res))
        page.update()

    def render():
        info.value = ""
        render_header()
        render_grid()

    # ---- Eventos de filtros ----
    def on_change_plantel(_):
        pid = int(dd_plantel.value) if dd_plantel.value and str(dd_plantel.value).isdigit() else None
        set_lab_options_for_plantel(pid)
        state["confirm_for"] = None
        render()

    dd_plantel.on_change = on_change_plantel
    dd_lab.on_change = lambda e: (state.__setitem__("confirm_for", None), render())

    # ---- Inicialización ----
    if planteles:
        dd_plantel.value = str(planteles[0].id)
        set_lab_options_for_plantel(planteles[0].id)
    else:
        dd_plantel.value = None
        set_lab_options_for_plantel(None)

    render()

    return ft.Column([
        ft.Text("Reservas", size=22, weight=ft.FontWeight.BOLD),
        Card(header, padding=14),
        legend,
        info,
        ft.Divider(),
        grid
    ], expand=True, scroll=ft.ScrollMode.AUTO)
