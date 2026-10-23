"""Prueba la consistencia del banco de prompts contra la API real.

Ejecuta cada prompt varias veces con la misma entrada y cuenta cuántas respuestas
llegaron como JSON válido y con la estructura esperada.

Distingue dos tipos de falla, que no significan lo mismo:
  - validación: la API respondió, pero el prompt no produjo el JSON esperado.
    Esto SÍ mide la consistencia del prompt.
  - infraestructura: la API no respondió (503, corte de red). Esto NO dice
    nada del prompt, así que se cuenta aparte y no castiga su tasa.

Si se acaba la cuota diaria o el presupuesto de peticiones, la corrida se corta
y el registro guarda lo que alcanzó a medirse, con el motivo del corte.

Los reintentos y el manejo de cuota vienen de consumir_gemini.py.
Deja el resultado en prompts/registro_resultados.json.

Uso:
    python3 prompts/test_consistencia.py
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# El módulo vive en src/ y este script en prompts/, así que hay que agregar las
# dos carpetas al camino de búsqueda. Se calculan desde la ubicación de este
# archivo, para que funcione sin importar desde qué carpeta lo ejecutes.
AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(AQUI))

from consumir_gemini import (  # noqa: E402
    LIMITE_DIARIO_GRATUITO,
    PAUSA_SEGUNDOS,
    REINTENTOS,
    CuotaAgotada,
    Presupuesto,
    PresupuestoAgotado,
    armar_peticion,
    enviar_con_reintento,
    es_transitorio,
    extraer_texto,
    parsear_respuesta_json,
)

from banco import BANCO_DE_PROMPTS  # noqa: E402

# ---------------------------------------------------------------------------
# Configuración de esta prueba
# ---------------------------------------------------------------------------

REPETICIONES = 3            # el mínimo que pide la actividad

# Tope de peticiones de una corrida completa, bajo el límite diario de 20.
# 3 prompts x 3 repeticiones son 9 si todo sale a la primera; el resto es margen
# para reintentos.
PRESUPUESTO_PETICIONES = 16

ARCHIVO_SALIDA = AQUI / "registro_resultados.json"


def enviar_ejemplo(prompt, presupuesto):
    """Envía el ejemplo_usuario de un prompt, con reintentos. Devuelve la respuesta cruda."""
    url, headers, body = armar_peticion(
        prompt["ejemplo_usuario"],
        prompt["system_instruction"],
        prompt.get("response_schema"),
    )
    datos, _ = enviar_con_reintento(url, headers, body, REINTENTOS, presupuesto)
    return datos


# ---------------------------------------------------------------------------
# Prueba de un prompt
# ---------------------------------------------------------------------------

def probar_prompt(prompt, presupuesto):
    """Corre las repeticiones de un prompt. Devuelve (registro, corte).

    corte es None si se pudieron hacer todas las repeticiones. Si la cuota o el
    presupuesto se acabaron a mitad de camino, corte trae el motivo, y el
    registro trae igual lo que alcanzó a medirse: no se pierde.
    """
    print(f"\n{'-' * 64}")
    print(f"  {prompt['nombre']}")
    print(f"  claves esperadas: {', '.join(prompt['claves_esperadas'])}")
    print(f"{'-' * 64}")

    validos = 0
    invalidos = 0
    no_medidos = 0
    fallos = []
    ultima_salida = None
    corte = None

    for intento in range(1, REPETICIONES + 1):
        # --- Paso 1: conseguir la respuesta. Si falla acá, es infraestructura.
        # CuotaAgotada y PresupuestoAgotado van primero porque son casos
        # particulares de RuntimeError: con ellas no se sigue intentando.
        try:
            respuesta = enviar_ejemplo(prompt, presupuesto)
        except CuotaAgotada as error:
            corte = f"cuota diaria agotada: {error}"
            break
        except PresupuestoAgotado as error:
            corte = f"presupuesto agotado: {error}"
            break
        except RuntimeError as error:
            no_medidos += 1
            fallos.append({
                "intento": intento,
                "tipo": "infraestructura",
                "motivo": str(error),
            })
            print(f"  intento {intento}: NO MEDIDO  →  {error}")
            if intento < REPETICIONES:
                time.sleep(PAUSA_SEGUNDOS)
            continue

        # --- Paso 2: validar la respuesta. Si falla acá, es el prompt.
        try:
            texto = extraer_texto(respuesta)
            datos = parsear_respuesta_json(texto, prompt["claves_esperadas"])
            validos += 1
            ultima_salida = datos
            print(f"  intento {intento}: válido    →  {json.dumps(datos, ensure_ascii=False)}")
        except (ValueError, RuntimeError) as error:
            invalidos += 1
            fallos.append({
                "intento": intento,
                "tipo": "validacion",
                "motivo": str(error),
            })
            print(f"  intento {intento}: INVÁLIDO   →  {error}")

        if intento < REPETICIONES:
            time.sleep(PAUSA_SEGUNDOS)

    medidos = validos + invalidos
    faltan = REPETICIONES - medidos      # por falla del servicio o por el corte
    tasa = round(validos / medidos, 2) if medidos else None

    if corte:
        print(f"  CORTE: {corte}")
    if medidos:
        print(f"  resultado: {validos}/{medidos} respuestas válidas", end="")
        print(f" ({faltan} sin medir)" if faltan else "")
    else:
        print("  resultado: ninguna repetición se pudo medir")

    registro = {
        "validos": validos,
        "invalidos": invalidos,
        "no_medidos": no_medidos,
        "repeticiones": REPETICIONES,
        "tasa_consistencia": tasa,
        "usa_response_schema": prompt.get("response_schema") is not None,
        "claves_esperadas": prompt["claves_esperadas"],
        "fallos": fallos,
        "ultima_salida_valida": ultima_salida,
    }
    return registro, corte


# ---------------------------------------------------------------------------
# Corrida completa
# ---------------------------------------------------------------------------

def main():
    # Un presupuesto nuevo en cada corrida: si main.py la llama dos veces
    # seguidas, la segunda también parte con su tope completo.
    presupuesto = Presupuesto(PRESUPUESTO_PETICIONES)

    modelo = os.getenv("AI_MODEL", "(no declarado)")
    print(f"Banco: {len(BANCO_DE_PROMPTS)} prompts, {REPETICIONES} repeticiones cada uno.")
    print(f"Modelo: {modelo}")
    print(f"Presupuesto: {presupuesto.tope} peticiones "
          f"(límite diario del nivel gratuito: {LIMITE_DIARIO_GRATUITO})")

    registro = {
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "modelo": modelo,
        "repeticiones_por_prompt": REPETICIONES,
        "prompts": {},
    }

    corte = None
    for prompt in BANCO_DE_PROMPTS:
        resultado, corte = probar_prompt(prompt, presupuesto)
        # Se guarda siempre, también el prompt que quedó a medias.
        registro["prompts"][prompt["nombre"]] = resultado
        if corte:
            # Sin cuota o sin presupuesto, los prompts que faltan tampoco salen.
            break

    # --- Resumen
    print(f"\n{'=' * 64}")
    print("  RESUMEN")
    print(f"{'=' * 64}")

    total_validos = total_medidos = total_sin_medir = 0
    for nombre, d in registro["prompts"].items():
        medidos = d["validos"] + d["invalidos"]
        # Las que faltan para llegar a REPETICIONES: por falla del servicio
        # o porque la corrida se cortó antes de intentarlas.
        faltan = d["repeticiones"] - medidos
        total_validos += d["validos"]
        total_medidos += medidos
        total_sin_medir += d["no_medidos"]
        if medidos == 0:
            marca = "SIN DATO"
        elif d["invalidos"] > 0:
            marca = "REVISAR"
        elif faltan > 0:
            marca = "INCOMPLETO"     # todo lo medido salió bien, pero no alcanza
        else:
            marca = "OK"
        extra = f"  ({faltan} sin medir)" if faltan else ""
        print(f"  [{marca:>10}] {nombre}: {d['validos']}/{medidos}{extra}")

    registro["total_validos"] = total_validos
    registro["total_medidos"] = total_medidos
    registro["total_sin_medir"] = total_sin_medir
    registro["peticiones_gastadas"] = presupuesto.gastadas
    registro["tasa_global"] = (
        round(total_validos / total_medidos, 2) if total_medidos else None
    )
    if corte:
        registro["corte"] = corte

    if total_medidos:
        print(f"\n  Global: {total_validos}/{total_medidos} ({registro['tasa_global']:.0%})")
    else:
        print("\n  Global: no se pudo medir nada.")
    print(f"  Peticiones gastadas: {presupuesto.gastadas} de {presupuesto.tope}")

    if corte:
        # El detalle completo ya se mostró arriba y queda en el registro; acá
        # basta el motivo corto, lo que va antes de los dos puntos.
        motivo = corte.split(":")[0]
        print(f"\n  La corrida se cortó antes de terminar ({motivo}).")
        sin_probar = [p["nombre"] for p in BANCO_DE_PROMPTS
                      if p["nombre"] not in registro["prompts"]]
        if sin_probar:
            print(f"  Quedaron sin probar: {', '.join(sin_probar)}")

    # --- Prompts que hay que ajustar (solo fallas de validación cuentan)
    a_revisar = {
        n: d for n, d in registro["prompts"].items()
        if d["invalidos"] > 0
    }
    if a_revisar:
        print("\n  Prompts a ajustar antes de entregar:")
        for nombre, d in a_revisar.items():
            for fallo in d["fallos"]:
                if fallo["tipo"] == "validacion":
                    print(f"    - {nombre}, intento {fallo['intento']}: {fallo['motivo']}")

    if total_sin_medir:
        # Un 503 se arregla esperando; un 400 (llave mala, esquema mal escrito)
        # o un 404 (modelo que no existe), no. El aviso tiene que decir cuál es.
        de_infraestructura = [
            fallo for d in registro["prompts"].values() for fallo in d["fallos"]
            if fallo["tipo"] == "infraestructura"
        ]
        no_se_arreglan = [f for f in de_infraestructura if not es_transitorio(f["motivo"])]
        print(f"\n  {total_sin_medir} intentos fallaron antes de poder validar la respuesta.")
        if no_se_arreglan:
            print("  Hay errores que NO se arreglan esperando, por ejemplo:")
            print(f"    {no_se_arreglan[0]['motivo']}")
            print("  Revisa la llave, el modelo o el esquema antes de volver a correr.")
        else:
            print("  Fueron fallas pasajeras del servicio: eso no dice nada de tus")
            print("  prompts. Vuelve a correr el script más tarde para completarlas.")

    ARCHIVO_SALIDA.write_text(
        json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n  Registro guardado en {ARCHIVO_SALIDA}")


if __name__ == "__main__":
    main()
