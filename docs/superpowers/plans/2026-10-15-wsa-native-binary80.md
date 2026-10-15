# WSA: componente binary80 nativo y contrato pendiente

La transformación del renderer `0x005061B0` concentra ~18 % de las muestras
del perfil exacto High. El helper double antiguo no conserva precisión x86.
Objetivo de este bloque: operaciones binary80 reales y aislamiento host probado,
como base para una futura ruta arquitectónica; no habilitar un fast path parcial.
La autorización del usuario cubre decisiones técnicas, pruebas y publicación
en main. La misión completa de 120 FPS permanece abierta.

## Diseño

`runtime/x87_native_math.h`: valores de 10 bytes explícitos, sin depender de
`long double`. ADD/SUB/MUL/DIV con CW explícito y resultado binary80; devuelve
excepciones frescas y C1 antes del almacenamiento. Solo controles con todas las
excepciones enmascaradas y precisión válida. Entrada/salida pueden compartir
memoria. Rechazo sin efectos. Una única región asm guarda, inicializa, calcula
y restaura x87/MXCSR para impedir intercalado del compilador. Implementación
GNU/Clang x86_64; otras arquitecturas rechazan, sin degradación a double.

El componente no accede a RAM guest, no está incluido en `recomp_rt.h`, no
modifica pcode2c y no habilita opciones del builder. El status retornado **no**
es un FSW guest. No resuelve TOP/tag, pila llena, FIP/FDP, excepciones sin
máscara, fallos de memoria o estado recuperable por PC.

## Ejecución y evidencia

- [x] Medir potencial: ensayo privado WSA, secuencia p-code real O2 frente a
  x87 explícito con aislamiento. Diez rondas alternadas de 300.000 iteraciones;
  medianas 435,083 / 135,617 ns. Un solo input finito fijo; no son FPS ni
  rendimiento integrado, no incluye exportar estado virtual en la variante nativa.
- [x] Escribir test; compilación inicial falla por ausencia del componente.
- [x] Implementar API y añadir test CMake por detección del compilador x87.
- [x] Verificar 12 controles, precisión >binary64, rango extendido, subnormales,
  cero con signo, NaN/invalid/divzero, alias, rechazo y restauración x87/MXCSR.
- [x] Revisión independiente: corregir tres bloques asm a uno; sin hallazgos
  restantes tras relectura. Tests con valores del compilador vivos y O0/O2/O3
  aprobados en host Windows y NDK/WSA, avisos estrictos sin errores.
- [x] Regresión final host tras el ajuste de aislamiento: **36/36 CTest**,
  71,51 s; matriz específica O0/O2/O3 aprobada.

## Próximo bloque necesario para integración

Diseñar y probar un estado x87 guest explícito (binary80, CW/SW/TOP/tag y
metadatos). Demostrar importación/exportación y efectos por instrucción usando
oráculo nativo además de Unicorn: este último no reflejó flags de precisión
en el corpus anterior. Resolver accesos y excepciones precisos antes de unir
operaciones entre puntos recuperables. Medir el coste de ese contrato completo;
la ganancia aislada puede reducirse. Solo después: compilar APK y A/B/A/B con
la misma escena/Alta, preservando partidas. No se considera completada esa
integración ni el objetivo de 8,33 ms por fotograma.

Un escaneo privado del PE y p-code intersectó instrucciones decodificadas con
entradas exportadas: 12 FLDCW escriben `R+0x10a0` (2 bytes), tres FNSTCW lo
leen; 1.733 FNSTSW leen `R+0x10a2` (2 bytes), y dos FNCLEX lo modifican.
Una FRSTOR también escribe `0x10a4/0x10a6/0x10a8/0x10ac` y los ocho registros
de 10 bytes. Esta evidencia localiza control/status en vez de asumir que no
existen; no prueba aún todo su significado ni su actualización correcta.
El lowering aritmético actual sigue ignorando ese CW. Priorizar la validación
de esta frontera antes de añadir estado paralelo o reinterpretar los campos
restantes. Datos: `fpu_control_mapping.json` privado.

La prueba posterior ejecutó el FRSTOR real generado con un entorno sintético
de 108 bytes, cada palabra distinta y operando `[ECX+8]` confirmado por
Capstone. Copias directas comprobadas (offsets relativos al operando):
`R+10a0 ← env+0`, `10a2 ← +4`, `10a4 ← +8`, `10a6 ← +18`,
`10a8 ← +20`, `10ac ← +12`; los ocho slots de 10 bytes en `R+1100+16*i`
cargan `env+28+10*i`. Esto identifica el formato que usa el lowering sin
suponer que sus operaciones mantienen todos los campos correctamente.
No se ejecutó FRSTOR nativo con ese patrón arbitrario ni se validaron aquí
selectores/semántica de excepciones. Evidencia: `frstor_mapping_v6/summary.json`.

**Publicación:** componente `f389f2d`; [CI 38734909191 aprobado](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38734909191).

**Continuación implementada:** [adaptador de estado y oráculo nativo x86](../../performance/wsa/WSA120_NATIVE_X87_STATE_2026-10-15.md).
37/37 CTest; 1.596 casos contrastados en CPU x86 y WSA para RAM, CW, SW,
tags y ocho slots. No incluye metadatos, alias ni fallos y sigue fuera de APK.
