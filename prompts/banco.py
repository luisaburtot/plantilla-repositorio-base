"""Banco de prompts de la miniaplicación.

Cada entrada junta cuatro cosas: el nombre de la tarea, el prompt de sistema
completo, un ejemplo de entrada de usuario, y la forma que debe tener la salida.

Las tres tareas giran alrededor del mismo caso: procesar novedades escritas por
personal de guardia en terreno, que llegan como texto libre y mal redactado, y
convertirlas en datos que el sistema pueda guardar y consultar.
"""

BANCO_DE_PROMPTS = [
    {
        "nombre": "clasificar_novedad",
        "system_instruction": (
            "Eres un asistente que clasifica novedades de turno escritas por personal "
            "de guardia en terreno. El texto llega sin corregir, con abreviaturas y "
            "errores de tipeo.\n"
            "Responde únicamente con un objeto JSON válido, sin texto adicional y sin "
            "bloques de markdown, con exactamente estas claves:\n"
            "- 'categoria': uno de estos valores exactos: 'acceso_no_autorizado', "
            "'falla_tecnica', 'emergencia_medica', 'dano_a_la_propiedad', "
            "'incidente_vehicular', 'rutina'.\n"
            "- 'severidad': uno de estos valores exactos: 'baja', 'media', 'alta', "
            "'critica'.\n"
            "- 'requiere_escalamiento': true o false, según si la novedad necesita "
            "aviso inmediato al supervisor de turno.\n"
            "- 'confianza': número entre 0 y 1 con tu nivel de certeza en la "
            "clasificación."
        ),
        "ejemplo_usuario": (
            "23:40 hrs se detecto a sujeto no identificado intentando saltar el cierre "
            "perimetral sector norte, al dar el alto se dio a la fuga en direccion a la "
            "ruta. no se registraron daños. se dio aviso a central."
        ),
        "claves_esperadas": ["categoria", "severidad", "requiere_escalamiento", "confianza"],
        "response_schema": {
            "type": "OBJECT",
            "properties": {
                "categoria": {"type": "STRING"},
                "severidad": {"type": "STRING"},
                "requiere_escalamiento": {"type": "BOOLEAN"},
                "confianza": {"type": "NUMBER"},
            },
            "required": ["categoria", "severidad", "requiere_escalamiento", "confianza"],
        },
    },
    {
        "nombre": "extraer_datos_novedad",
        "system_instruction": (
            "Eres un asistente que extrae datos estructurados de novedades de turno "
            "escritas por personal de guardia.\n"
            "Responde únicamente con un objeto JSON válido, sin texto adicional y sin "
            "bloques de markdown, con exactamente estas claves:\n"
            "- 'hora': la hora mencionada en formato HH:MM de 24 horas, o null si el "
            "texto no la indica.\n"
            "- 'ubicacion': el lugar dentro de la instalación donde ocurrió, como texto "
            "breve, o null si no se menciona.\n"
            "- 'personas': lista de nombres de personas mencionadas. Lista vacía si no "
            "hay ninguna.\n"
            "- 'patentes': lista de patentes de vehículos mencionadas, en mayúsculas y "
            "sin guiones ni puntos. Lista vacía si no hay ninguna.\n"
            "No inventes datos que el texto no diga. Ante la duda, usa null o lista "
            "vacía."
        ),
        "ejemplo_usuario": (
            "08:15 ingresa camioneta patente KXRT-42 conducida por el sr. Pedro Mellado "
            "de la empresa contratista, se dirige a bodega 3 para retiro de materiales. "
            "acompañado por don Luis Paredes. se registra en libro de ingresos."
        ),
        "claves_esperadas": ["hora", "ubicacion", "personas", "patentes"],
        "response_schema": {
            "type": "OBJECT",
            "properties": {
                "hora": {"type": "STRING", "nullable": True},
                "ubicacion": {"type": "STRING", "nullable": True},
                "personas": {"type": "ARRAY", "items": {"type": "STRING"}},
                "patentes": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["hora", "ubicacion", "personas", "patentes"],
        },
    },
    {
        "nombre": "resumir_para_parte",
        "system_instruction": (
            "Eres un asistente que redacta el resumen de una novedad de turno para el "
            "parte diario que lee el encargado de la instalación.\n"
            "Responde únicamente con un objeto JSON válido, sin texto adicional y sin "
            "bloques de markdown, con exactamente estas claves:\n"
            "- 'titulo': título de máximo 8 palabras que identifique la novedad.\n"
            "- 'resumen': una sola frase, de máximo 30 palabras, en español neutro y en "
            "tercera persona, con los hechos corregidos de ortografía.\n"
            "- 'accion_sugerida': una frase breve con lo que corresponde hacer, o la "
            "cadena 'ninguna' si no amerita acción.\n"
            "No agregues interpretaciones ni suposiciones: resume solo lo que el texto "
            "dice."
        ),
        "ejemplo_usuario": (
            "siendo las 03:20 se escucho ruido fuerte en sala de maquinas, al concurrir "
            "se constata que la bomba 2 esta botando agua por la union, hay acumulacion "
            "en el piso aprox 2 cm. se corto el suministro y se aviso a mantencion."
        ),
        "claves_esperadas": ["titulo", "resumen", "accion_sugerida"],
        "response_schema": {
            "type": "OBJECT",
            "properties": {
                "titulo": {"type": "STRING"},
                "resumen": {"type": "STRING"},
                "accion_sugerida": {"type": "STRING"},
            },
            "required": ["titulo", "resumen", "accion_sugerida"],
        },
    },
]
