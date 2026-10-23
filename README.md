# Miniaplicación Gemini — Novedades de turno

Proyecto de la Especialización en Desarrollo con IA Generativa (Accenture).

Procesa novedades de turno escritas por personal de guardia, en texto libre y sin
corregir, y las convierte en datos estructurados usando la API de Gemini: las
clasifica por categoría y severidad, extrae hora, ubicación, personas y patentes,
y redacta un resumen para el parte diario. Si una novedad requiere aviso
inmediato, la aplicación lo indica.

---

## Requisitos

- **Python 3.10 o superior.** Se desarrolló con Python 3.12.
- **Una llave de la API de Gemini**, que se crea en Google AI Studio:
  <https://aistudio.google.com/apikey>

---

## Instalación

### Linux y macOS

```bash
git clone https://github.com/luisaburtot/plantilla-repositorio-base.git
cd plantilla-repositorio-base
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Windows

```bat
git clone https://github.com/luisaburtot/plantilla-repositorio-base.git
cd plantilla-repositorio-base
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Si PowerShell no deja activar el entorno por la política de ejecución, corre una
vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelve a intentarlo.

### Configurar la llave

Abre el archivo `.env` recién creado y reemplaza `tu_llave_aqui` por tu llave de
Gemini. `AI_MODEL` ya viene con el modelo elegido para el proyecto; no hace falta
cambiarlo.

> El archivo `.env` es personal y nunca se sube al repositorio: está excluido en
> `.gitignore`. Si ya tienes un `.env`, no lo sobrescribas con la copia.

### Verificar que quedó bien

```bash
python variables_entorno.py
```

Tiene que mostrar la llave como `cargada` con su cantidad de caracteres, sin
revelarla, y el nombre del modelo. Si alguna dice `NO ENCONTRADA`, revisa el
`.env`.

Si muestra `cargada (13 chars)`, todavía tienes el texto de ejemplo
`tu_llave_aqui`: una llave real es bastante más larga.

---

## Uso

Con el entorno virtual activado, desde la carpeta del proyecto:

```bash
python src/main.py
```

Se abre un menú con todas las funciones de la aplicación:

| Opción | Qué hace | Peticiones a la API |
|---|---|---|
| 1 | Procesa una novedad de turno con las tres tareas del banco | 3 a 9 |
| 2 | Prueba la conexión y el manejo de errores | 1 |
| 3 | Compara dos modelos por costo y latencia | 7 a 16 por modelo |
| 4 | Valida la consistencia del banco de prompts | 9 a 16 |
| 5 | Muestra la configuración actual | ninguna |

Para procesar una novedad directo, sin pasar por el menú:

```bash
python src/main.py "23:40 sujeto intenta saltar el cierre perimetral norte, huye al dar el alto"
```

Cada pieza también se puede correr por separado:

```bash
python src/consumir_gemini.py         # prueba de conexión y manejo de errores
python src/comparar_modelos.py        # comparación de modelos
python prompts/test_consistencia.py   # validación del banco de prompts
```

### Cuota del nivel gratuito

El nivel gratuito de Gemini permite **20 peticiones diarias por modelo**, y cada
reintento cuenta como una petición: por eso las cifras de la tabla son rangos.
El mínimo es cuando el servicio responde a la primera; el máximo, cuando hay que
reintentar. Las opciones 1, 3 y 4 muestran al final cuántas gastaron.

Para probar todo en un día sin quedarse sin cuota, este orden gasta 13 de las 20
si el servicio responde a la primera:

1. Opción **5**: confirma la configuración sin gastar nada.
2. Opción **2**: una petición; si responde, hay cuota disponible.
3. Opción **1**: tres peticiones; la aplicación completa.
4. Opción **4**: nueve peticiones; genera `prompts/registro_resultados.json`.

La opción 3 es la que más gasta: conviene correrla en un día aparte.

---

## Estructura de carpetas

- `src/` : código fuente.
  - `main.py` : punto de entrada; el menú de la aplicación.
  - `consumir_gemini.py` : módulo común. Arma, envía e interpreta las
    peticiones a Gemini, con manejo de errores, reintentos, control de cuota y
    cálculo de costo. Los precios y el límite diario se definen solo acá; los
    demás archivos los importan.
  - `comparar_modelos.py` : mide latencia y costo real de dos modelos.
- `prompts/` : banco de prompts y su validación.
  - `banco.py` : las tres tareas, cada una con su prompt de sistema y su
    esquema de salida JSON.
  - `test_consistencia.py` : repite cada prompt y mide qué tan seguido entrega
    un JSON válido.
- `docs/` : documentación técnica.
  - `diagrama_arquitectura.png` : el flujo completo de una petición.
  - `decision-arquitectura.md` : por qué se eligió el modelo que usa la aplicación.
- `tests/` : reservada para pruebas automatizadas, que se agregan más adelante en
  el programa.
- `postman/` y `.postman/` : configuración de la extensión Postman de VS Code.
- `variables_entorno.py` : verifica que el `.env` se cargue, sin mostrar la llave.
- `requirements.txt` : dependencias de Python; se instalan con un solo comando.
- `.env.example` : plantilla de las variables de entorno, sin valores reales.
- `.gitignore` : lo que Git no debe subir (`.env`, el entorno virtual, cachés).

---

## Reglas que se mantienen durante todo el programa

- Ningún secreto (contraseña, llave de API, token) va escrito directamente en el
  código ni en ningún archivo que se suba al repositorio.
- Cada proyecto nuevo tiene su propio entorno virtual: no se comparten
  dependencias entre proyectos distintos.
- Todo el trabajo que se entrega en este programa vive en un repositorio de
  GitHub, sin excepción.
