"""Banco de prompts de la miniaplicación.

Cada entrada junta cuatro cosas: el nombre de la tarea, el prompt de sistema,
un ejemplo de entrada de usuario, y las claves que debe traer la respuesta JSON.

Las tres tareas giran alrededor del mismo caso: opiniones de clientes sobre un
producto o servicio, escritas en texto libre, que hay que convertir en datos
que un programa pueda guardar y consultar.
"""

BANCO_DE_PROMPTS = [
    {
        "nombre": "clasificar_opinion",
        "system_instruction": (
            "Eres un asistente que clasifica opiniones de clientes sobre productos "
            "y servicios.\n"
            "Responde únicamente con un objeto JSON válido, sin texto adicional, con "
            "exactamente estas claves:\n"
            "- 'sentimiento': uno de estos valores exactos: 'positivo', 'negativo', "
            "'neutro'.\n"
            "- 'confianza': número entre 0 y 1 con tu nivel de certeza."
        ),
        "ejemplo_usuario": (
            "Compré la cafetera hace un mes y la uso todos los días. Calienta rápido, "
            "es fácil de limpiar y el precio fue muy bueno. La recomiendo."
        ),
        "claves_esperadas": ["sentimiento", "confianza"],
    },
    {
        "nombre": "extraer_datos_opinion",
        "system_instruction": (
            "Eres un asistente que extrae datos de opiniones de clientes.\n"
            "Responde únicamente con un objeto JSON válido, sin texto adicional, con "
            "exactamente estas claves:\n"
            "- 'producto': el producto o servicio del que habla la opinión, como "
            "texto breve, o null si no se menciona.\n"
            "- 'aspectos_positivos': lista de cosas que el cliente valora. Lista "
            "vacía si no hay.\n"
            "- 'aspectos_negativos': lista de cosas que el cliente critica. Lista "
            "vacía si no hay.\n"
            "No inventes datos que la opinión no diga."
        ),
        "ejemplo_usuario": (
            "Los audífonos tienen buen sonido y la batería dura todo el día, pero el "
            "estuche llegó rayado y la aplicación del celular se cierra sola."
        ),
        "claves_esperadas": ["producto", "aspectos_positivos", "aspectos_negativos"],
    },
    {
        "nombre": "resumir_opinion",
        "system_instruction": (
            "Eres un asistente que resume opiniones de clientes para el equipo de "
            "atención al cliente.\n"
            "Responde únicamente con un objeto JSON válido, sin texto adicional, con "
            "exactamente estas claves:\n"
            "- 'resumen': una sola frase, de máximo 25 palabras, en tercera persona.\n"
            "- 'accion_sugerida': una frase breve con lo que el equipo debería hacer, "
            "o la palabra 'ninguna' si no amerita acción.\n"
            "No agregues interpretaciones: resume solo lo que la opinión dice."
        ),
        "ejemplo_usuario": (
            "Llevo tres semanas esperando el reembolso del pedido 4471. Escribí dos "
            "veces al correo de soporte y nadie me responde. Si no tengo respuesta "
            "esta semana voy a presentar un reclamo formal."
        ),
        "claves_esperadas": ["resumen", "accion_sugerida"],
    },
]
