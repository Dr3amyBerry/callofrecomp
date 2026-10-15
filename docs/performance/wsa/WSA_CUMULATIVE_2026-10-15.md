# Integración acumulativa WSA — 2026-10-15

Por petición del usuario se evalúa el conjunto de optimizaciones compatibles,
incluidas las que antes no mostraron una subida individual de FPS. Una ganancia
de fidelidad, CPU, memoria o estabilidad puede justificar conservar un cambio;
no se exige que cada opción eleve por sí sola los FPS medios.

## Conjunto reproducible

`build_android.py --abi x86_64 --native-x87-region RUTA_PE --wsa-cumulative`
añade a la referencia actual:

| Opción | Tratamiento |
| --- | --- |
| Región nativa x87 `0x005061B0` | 57 instrucciones binary80 en el orden original, importación/exportación completa, comprobación de código/controles/direcciones y retorno virtual |
| copia32 | Se conserva el flujo original en solapamientos, desbordamientos o páginas ausentes; guarda Android nueva antes del bloque optimizado |
| NaN / normal-f2d / FCOM | Se activan conjuntamente los helpers p1/p8 existentes; preservan el contrato del traductor actual, cuya fidelidad x87 global sigue incompleta |
| renderer / visibilidad | `-O2 -ffp-contract=off` en las particiones delimitadas, sin fast-math |
| caché de despacho | Reutilización del último chunk con límites y generación de módulos |
| Correcciones y optimizaciones ya presentes | Permanecen en ambos APK; no se atribuyen de nuevo al conjunto |

Las variantes exclusivas ARM64 no se pueden ejecutar en WSA x86_64. El transform
antiguo basado en double y CFG14 siguen bloqueados por errores de precisión y
estado ante faltas. No son equivalentes a cambios lentos pero correctos.
La captura Vulkan, los contadores GL/CPU y los modos GL4ES previamente
regresivos son diagnósticos o alternativas de backend, no mejoras acumulables.

El helper nativo se compila solo mediante opción explícita. Dentro del APK
experimental, el archivo privado `files/profile/native_x87`, contenido exacto
`1`, lo activa al reiniciar; su ausencia conserva el despachador anterior.
Los selectores se mantienen en cero, como el modelo virtual actual sin campos
CS/DS mapeados. La ruta no certifica reanudación SEH ni excepciones sin máscara.
El juego deja CW como `023f` en el traductor: se acepta ese alias y se
normaliza su bit fijo 6 a `027f`, como hace el hardware. Se preservan todos
los bits operativos de precisión/redondeo/máscaras. Las llamadas rechazadas
no normalizan ni escriben el estado.
Las faltas nativas reconocidas restauran R/PC antes del diagnóstico terminal;
las señales ajenas se delegan al manejador Android previo. Esa delegación no
reproduce todos los flags/máscaras POSIX de un manejador arbitrario.

## Verificación y medición

- Ruta realmente emitida y adaptador ejecutados en WSA: **22.344 casos**, cero
  diferencias contra los resultados x86 originales en RAM128, CW/SW/tags,
  ocho slots binary80 y metadatos. Incluye 14 disposiciones de alias.
- Tres pruebas del generador ejecutan código compilado, verifican el retorno,
  los controles rechazados y el rechazo sin cambios de bytes inesperados.
- La integración detectó y corrigió incompatibilidades entre los parches ya
  aplicados y sus includes transitivos. La suite comprobó también que los
  bloqueos de CFG14 siguen intactos.
- A/B/A/B físico: referencia y conjunto completo, APK reinstalado con `-r -t`,
  mismo entrenamiento/guardado/cámara, Alta, superficie 1280×720 y límite 120.
  Cada corrida obtiene 45 segundos de presentación y ventanas de motor tras
  carga y calentamiento. No se compila durante las capturas.

Los APK, fuentes comerciales, logs, símbolos y capturas permanecen ignorados
en `.local/profiles/wsa120_20261015/`. El objetivo de 120 FPS sostenidos y la
estabilidad en escenas complejas siguen abiertos. La pantalla WSA está en 75 Hz.

## Resultados físicos finales

Las cuatro capturas tienen cobertura completa, PID estable y cero huecos del
buffer de presentación. En B1/B2 se exigió el marcador de ejecución nativa
**antes** de medir. El APK acumulativo quedó instalado y activo.

| Corrida, Alta / límite 120 | FPS mediana de ventanas | CPU ms/frame mediana | Presentados/s | Presentación p99 ms |
| --- | ---: | ---: | ---: | ---: |
| A1 referencia | 53,8 | 18,570 | 51,81 | 40,00 |
| B1 conjunto | 66,7 | 15,000 | 63,29 | 32,64 |
| A2 referencia | 55,7 | 17,930 | 53,35 | 40,00 |
| B2 conjunto | 66,8 | 14,970 | 64,01 | 31,69 |

Promedio de las dos medianas por variante: **54,75 → 66,75 FPS (+21,92 %)**,
**18,250 → 14,985 ms CPU/frame (−17,89 %)**. La presentación pasa de
52,58 a 63,65/s. Los p10 de ventanas B son 60,9 y 61,9 FPS, pero sus mínimos
son 52,4 y 57,5: **no son 60 FPS mínimos garantizados ni 120 FPS sostenidos**.
No se atribuye el resultado a cada opción individual ni se extrapola a TECNO.

En A1/A2/B1/B2 se registraron respectivamente 0/3/1/0 intervalos >50 ms y
ninguno >100 ms. La pareja visual A1/B1 conserva escena, HUD y geometría sin
diferencia evidente; no es una certificación gráfica de todo el juego.
Guardados finales: los dos SHA256 coinciden exactamente con la copia protegida.

La primera B exploratoria dio 58,3 FPS / 17,14 ms, pero la guarda rechazaba
CW=`023f` y **no ejecutó la región nativa**. Quedó excluida del A/B/A/B final;
sirvió para diagnosticar el bit fijo. El oráculo original i686 confirmó después
22.344 casos con bit 6 borrado idénticos al control canónico. La ruta WSA final
repitió esos 22.344 casos alias sin diferencias en los campos contrastados.

Validación local: 37 CTest no Python aprobados y suite Python aprobada tras
corregir la regresión detectada del manejador desktop; pruebas compiladas de
región/alias y retorno aprobadas. La revisión independiente no encontró
bloqueadores nuevos; quedan los límites de señales/SEH descritos arriba.
Código integrado `8401f29`: [CI 38773880404 aprobada](https://github.com/Dr3amyBerry/callofrecomp/actions/runs/38773880404).

SHA256 APK referencia: `c722b4ea7bcfcf8bb8d95456e9201a0bed210ae348888a682b1d9cd4499caa55`.
SHA256 APK conjunto medido: `a19ea65e30024f7f1f6f55d2be97ba99c854fd1e32e6c151bed6213194da1702`.

**Decisión:** conservar el conjunto como preset experimental reproducible y
dejarlo activo en WSA, conforme a la petición. Los defaults generales ARM64 no
cambian. El siguiente trabajo es perfilar este APK exacto y probar una escena
más exigente; el antiguo perfil de la referencia ya no atribuye el coste nuevo.
