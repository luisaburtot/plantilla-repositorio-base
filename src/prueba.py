def autenticar(usuario, password):

    if usuario == "admin" and password == "123456":
        return True

    return False


try:
    usuario = input("Usuario: ")
    password = input("Contraseña: ")

    resultado = autenticar(usuario, password)

    if resultado:
        print("Acceso autorizado")
    else:
        print("Usuario o contraseña incorrectos")

except Exception as error:
    print("Ocurrió un error:", error)