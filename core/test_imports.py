import os
import importlib.util

def verificar_importaciones(directorio):
    errores = []
    for root, _, files in os.walk(directorio):
        for archivo in files:
            if archivo.endswith(".py") and archivo != "test_imports.py":
                path_completo = os.path.join(root, archivo)
                try:
                    spec = importlib.util.spec_from_file_location("modulo_temporal", path_completo)
                    modulo = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(modulo)
                except Exception as error:
                    errores.append((path_completo, error))
    return errores

if __name__ == "__main__":
    errores = verificar_importaciones("core")
    errores += verificar_importaciones("routes")

    if errores:
        print("\n--- ERRORES DE IMPORTACIÓN DETECTADOS ---\n")
        for path, error in errores:
            print(f"❌ {path}:\n    {error}\n")
        raise SystemExit("❌ Se detectaron errores de importación.")
    else:
        print("✅ Todas las importaciones funcionan correctamente.")
