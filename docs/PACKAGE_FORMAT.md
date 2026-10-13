# Paquetes de instalación `.codpack` (versión 1)

La web convierte una instalación propia de Call of Duty 1.5 en un único archivo
que el lanzador Android importa. No modifica el APK ni sube recursos a servidores.
Los PK3 ya están comprimidos; el contenedor los copia sin recomprimir.

Todos los enteros usan orden big endian. Cabecera: ocho bytes ASCII `CODPACK1`
y un entero unsigned de 32 bits con la cantidad de archivos. Cada entrada contiene
la longitud del nombre (unsigned 16 bits), el nombre ASCII, la longitud del contenido
(unsigned 64 bits), el contenido y su CRC32 (unsigned 32 bits).

Se permiten exclusivamente `CoDSP.exe`, `gamex86.dll`, `cgamex86.dll`, `uix86.dll`
y `main/<nombre>.pk3`. Se requieren los cuatro binarios y al menos un PK3.
Los nombres PK3 usan letras ASCII, números, guion, punto y guion bajo; sin `..`.
No se permiten duplicados ni contenido después de la última entrada.
Límites: 1.024 entradas, nombres de 200 bytes, 2 GiB por archivo, 8 GiB en total.

La web comprueba el SHA-256 de los cuatro binarios contra la misma versión que
acepta Android. Android vuelve a comprobar esos hashes antes de activar la
instalación. CRC32 detecta daños de transferencia; no es autenticación.
La extracción utiliza una carpeta temporal, mantiene la instalación anterior
hasta validar el paquete y nunca escribe en la carpeta de partidas.

## Implementación y publicación

1. Pruebas del contenedor y del intercambio JavaScript → Java con datos sintéticos.
2. Escritor web por bloques de 1 MiB e importador Java con memoria acotada.
3. Selector de paquetes Android, staging y limpieza ante errores; conservar selector de carpetas.
4. README de uso, build de ambas ABI, pruebas automáticas y auditoría de los APK públicos.
5. Publicar web pública y prerelease; excluir APK privado y todos los archivos originales.

La revisión visual y la prueba con una instalación real las realiza el usuario,
según su preferencia. No se declara completa la campaña por pruebas del empaquetador.
