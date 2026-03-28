import httpx
import csv
import io
import json

SHEET_ID = "17cgprZE6fp7PpNCve3zHlLWXWdiN07ZsK2ZiiKiv8XI"
BASE_URL = "https://docs.google.com/spreadsheets/d/" + SHEET_ID + "/gviz/tq?tqx=out:csv"
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzQoz-k0ElDXq7acU6w99IVurrs2n9xmhlwnqCXBdEm92_8IfaAvRnbwlWvL_j7ZCBhpw/exec"


async def get_catalogo() -> str:
    url = BASE_URL + "&sheet=Catalogo"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)

    productos = []
    for row in rows:
        if len(row) < 10:
            continue
        if not row[0].startswith("R"):
            continue
        if row[9].strip() != "Activo":
            continue

        precio_raw = row[7].strip().replace("$", "").replace(".", "").replace(",", "").strip()
        try:
            precio = int(precio_raw)
            precio_fmt = "${:,}".format(precio).replace(",", ".")
        except:
            precio_fmt = row[7]

        producto = (
            "- " + row[2] +
            " | Categoría: " + row[1] +
            " | Capacidad: " + row[4] +
            " | Precio: " + precio_fmt +
            " | Beneficio: " + row[5] +
            " | Ref: " + row[8]
        )
        productos.append(producto)

    if not productos:
        return "No hay servicios disponibles en este momento."

    return "\n".join(productos)


async def buscar_producto_por_referencia(referencia: str):
    url = BASE_URL + "&sheet=Catalogo"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)

    referencia = referencia.strip().upper()

    for row in rows:
        if len(row) < 10:
            continue
        if not row[0].startswith("R"):
            continue
        if row[9].strip() != "Activo":
            continue

        if row[8].strip().upper() == referencia:
            precio_raw = row[7].strip().replace("$", "").replace(".", "").replace(",", "").strip()
            try:
                precio = int(precio_raw)
            except:
                precio = 0

            return {
                "id": row[0].strip(),
                "categoria": row[1].strip(),
                "servicio": row[2].strip(),
                "descripcion": row[3].strip(),
                "capacidad": row[4].strip(),
                "beneficio": row[5].strip(),
                "normativo": row[6].strip(),
                "precio": precio,
                "referencia": row[8].strip(),
                "estado": row[9].strip()
            }

    return None


async def registrar_pedido(
    telefono: str,
    nombre: str,       # ✅ FIX: clave unificada como "nombre" (igual que el Apps Script)
    empresa: str,      # ✅ NUEVO: se agrega empresa
    ciudad: str,       # ✅ NUEVO: se agrega ciudad
    referencia: str,
    servicio: str,
    descripcion: str,
    capacidad: str,
    precio: int
) -> bool:
    try:
        data = {
            "telefono": telefono,
            "nombre": nombre,          # ✅ FIX: antes era "nombre_cliente", no coincidía con Apps Script
            "empresa": empresa,        # ✅ NUEVO
            "ciudad": ciudad,          # ✅ NUEVO
            "referencia": referencia,
            "servicio": servicio,
            "descripcion": descripcion,
            "capacidad": capacidad,
            "precio": precio
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                APPS_SCRIPT_URL,
                content=json.dumps(data),
                headers={"Content-Type": "application/json"},
                follow_redirects=True,
                timeout=15.0
            )
        result = response.json()
        if result.get("status") == "ok":
            print("[PEDIDO OK] " + result.get("pedido", ""))
            return True
        else:
            print("[PEDIDO ERROR] " + str(result))
            return False
    except Exception as e:
        print("[ERROR PEDIDO] " + str(e))
        return False
