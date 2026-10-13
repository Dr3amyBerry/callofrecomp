# Investigación profunda de rendimiento — CallofRecomp

**Fecha:** 2026-10-13  
**Proyecto objetivo:** Dr3amyBerry/callofrecomp, Call of Duty 1.5 single-player recompilado estáticamente para Android ARM64  
**Línea base documental:** main en 52f70c902fed41d728097622a19e810ae2457288; release 0.2.3 publicada el 2026-10-13  
**Naturaleza:** auditoría estática, comparación de referencias y protocolo experimental; NO constituye una medición en teléfono de la versión 0.2.3  
**Protección de datos:** informe publicable que usa exclusivamente código y documentación públicos. No contiene ROM/EXE/DLL/PK3, código generado privado, mapas, trazas privadas ni perfiles brutos.

> Esta investigación amplía el informe anterior sin sustituirlo: no se pudo abrir el archivo local ignorado bajo .local/profiles, ya que el único workspace registrado por RigorCore Dev MCP, llamado demo, corresponde a Case-Recomp y no a callofrecomp. No escribir dentro de ese otro workspace. Los experimentos que requieren el árbol local y la APK ARM64 real siguen pendientes.

## 0. Resumen ejecutivo y grado de certeza

**Observaciones verificadas directamente en el código:**

1. El motor ejecuta código generado desde p-code de los originales y vuelve a un despachador cuando cambia de chunk: tools/recomp/pcode2c.py y tools/recomp/runtime/guest.c.
2. Android compila el host y el código generado con -O1; puede aplicar -O0 al código generado mediante RECOMP_OPTIMIZATION=0: android/CMakeLists.txt. No existe una selección medida de -O2 por función en la compilación publicada.
3. El despachador utiliza un índice de páginas de 4 KiB con fallback de búsqueda por límites compartidos; esa optimización ya existe y no conviene rehacerla a ciegas.
4. Los PK3 de solo lectura utilizan mmap cuando está disponible, pero ello no demuestra que la descompresión, la preparación de modelos, las texturas o los shaders sean rápidos: tools/recomp/runtime/files.c.
5. gl_thunks.c conecta el renderer x86 recompilado con GL4ES. Muchos accesos a datos de cliente se traducen mediante GP(), que convierte direcciones invitadas en punteros del host.
6. gl_guest_string() anuncia al juego solo diez familias seleccionadas de extensiones (si el backend las publica), y NO anuncia GL_ARB_vertex_buffer_object ni programas ARB: tools/recomp/runtime/window.c. Esto puede influir en la ruta seleccionada por el motor original.
7. Las funciones t_glDrawElements, t_glDrawRangeElements, t_glVertexPointer, t_glNormalPointer, t_glColorPointer, t_glTexCoordPointer y t_glVertexAttribPointerARB traducen incondicionalmente su argumento de puntero mediante GP(). En OpenGL, cuando GL_ELEMENT_ARRAY_BUFFER o GL_ARRAY_BUFFER están enlazados, ese argumento es un **offset numérico**, no un puntero. Es una incompatibilidad potencial de las rutas VBO/IBO actualmente no expuestas, no una prueba de que el videojuego use una ruta rota hoy. Resolver antes de habilitar VBO/IBO.
8. GL4ES contiene caminos directos para draws compatibles, y caminos interceptados/de lista que pueden convertir y copiar geometría, asignar memoria y hacer trabajo adicional. La proporción ejecutada en las escenas de CoD aún no se ha medido.
9. El parámetro LIBGL_BATCH comienza deshabilitado en la revisión fijada de GL4ES; la activación indiscriminada no está justificada.
10. GL4ES genera programas de emulación de fixed-function cuando cambia a un estado no preparado y posee caché en memoria y archivo PSA opcional; su uso efectivo en la APK Android no está registrado.
11. El límite de FPS, perfiles de resolución, eliminación de flags muertos, temporales locales, separación de registros y RAM, manejo de divisiones, reserva agrupada y el indicador de carga ya están implementados.
12. La versión 0.2.3 no está certificada mediante captura representativa del teléfono donde se observó la caída de FPS. No se puede convertir un microbenchmark en una promesa de mejora de juego.

**Hipótesis de mayor valor a contrastar, en orden:** costo de ejecución CPU del renderer original recompilado; número y preparación de superficies; trabajo de GL4ES y shader/state conversion; rutas de geometría estática desaprovechadas; otros cálculos de entidades y colisiones; etapa dominante de CL_InitCGame.

**Objetivo de ingeniería:** aislar dónde se gastan los aproximadamente 16,67 ms presupuestarios a 60 FPS, corregir una causa a la vez y comparar A/B en el ARM64 real manteniendo jugabilidad, aspecto visual y compatibilidad de recursos.

## 1. Evidencia histórica y lo que NO prueba

La documentación pública del propio proyecto (PROGRESS.md) conserva pruebas anteriores en TECNO y WSA:
- Hubo intervalos de 4–17 FPS en un recorrido exigente y otros de 26–39 FPS, en APKs previas.
- Con perfilado activado se observaron intervalos de ~90–110 ms por frame y ~85–107 ms de tiempo de CPU del hilo del motor; swap rondaba pocos milisegundos. Incluía sobrecarga de perfilado.
- CL_InitCGame llegó a unos 47 segundos en TECNO. Distintas optimizaciones disminuyeron ciertas inicializaciones de WSA; ese resultado no valida el ARM64 físico.
- La escena de entrenamiento con alambres, ametralladoras y soldados reptando llegó a ~5 FPS en un Samsung con una versión previamente instalada, no verificada como 0.2.3.
- La release 0.2.3 y sus pruebas sintéticas de equivalencia demuestran integridad de determinadas optimizaciones, no FPS en campaña.

Separaciones obligatorias:
- Tiempo de pared entre frames no es lo mismo que CPU activa del motor.
- El tiempo de SDL_GL_SwapWindow no equivale al tiempo de toda la GPU: el trabajo puede estar encolado/asíncrono.
- Una zona visualmente compleja no prueba que sus alambres, partículas o IA sean la causa.
- Ni WSA x86_64, ni microbenchmarks host, ni compilar ARM64 sustituyen una captura en teléfono ARM64.
- El perfil de gráficos Light modifica varias opciones además de resolución: una comparación entre perfiles no aísla por sí sola fill-rate.

**Archivos públicos:** PROGRESS.md; docs/ANDROID_PERFORMANCE.md; docs/FRAME_PACING.md; docs/RELEASE_NOTES_v0.2.3.md.

## 2. Recorrido de un frame y fronteras de coste

Camino simplificado:

CoDSP.exe/cgamex86.dll/gamex86.dll/uix86.dll compilados como chunks C
  -> guest_run() + dispatch_index_find()
  -> thunks Win32 y OpenGL
  -> gl_thunks.c
  -> GL4ES de escritorio OpenGL a GLES2
  -> driver GLES, GPU y EGL/SDL_SwapWindow.

**Dónde mirar:**
- pcode2c.py: CHUNK = 1500, etiquetas por instrucción y switch dinámico de entrada; espacios de memoria separados con restrict en bloques compatibles y cálculo de flags muertos.
- runtime/guest.c: guest_run en torno a la línea 605; resolución de PC, ejecución del chunk y host thunk. Estadística muestreada opcional en torno a las líneas 440–489.
- runtime/dispatch_index.h: tabla page[1 << 20] de uint16_t, ≈2 MiB, reconstruida al cargar/descargar módulos; fallback de búsqueda binaria para páginas con más de un chunk.
- runtime/gl_thunks.c: envoltorios de funciones, conversión de parámetros, llamadas a punteros p_gl*.
- runtime/window.c: contexto GLES2/GL4ES, presentación SDL y estadísticas agregadas de CPU, swap y pacing.
- runtime/audio.c: mezcla SDL en hilo de audio; si una captura revela interferencias por audio, perfilar aparte.
- runtime/files.c: puente CreateFile/ReadFile con mmap de PK3 inmutable, búsqueda overlay/home/install.
- android/native_host.c y android/java/org/callofrecomp/RenderProfile.java: inicialización y perfiles de gráficos.

Un único hilo puede estar ocupado en preparación de objetos, VM, traducción GL, driver o sincronización. El primer trabajo es descomponer su tiempo activo por categoría.

## 3. Hallazgo arquitectónico nuevo: capabilities y offsets de VBO/IBO

### 3.1 Extensiones que el invitado puede ver

En runtime/window.c, gl_guest_string(GL_EXTENSIONS) conserva solo una lista corta:
- multitexture;
- compiled vertex array;
- texture_env_add/combine;
- texture compression / S3TC;
- texture_env_dot3;
- cube map.

Se consulta realmente desde t_glGetString en runtime/gl_thunks.c. En particular, el string no contiene GL_ARB_vertex_buffer_object, GL_ARB_vertex_program o GL_ARB_fragment_program, aunque GL4ES pudiera soportar sus interfaces. Por tanto, las decisiones de capacidad del motor basadas en GL_EXTENSIONS pueden excluir rutas aceleradas. Confirmar qué ruta elige el motor mediante sus mensajes de inicialización y el binario privado.

**No quitar la lista blanca todavía:** existe evidencia de que los thunks de punteros/offsets no están adaptados para VBO/IBO y hay diferencias de compatibilidad de shaders.

### 3.2 Semántica de los punteros

runtime/gl_thunks.h declara GP(a) como a ? G(a) : NULL, es decir traduce a puntero de RAM invitada.

Aplicaciones actuales:
- glDrawElements y glDrawRangeElements convierten la dirección de índices mediante GP.
- glVertexPointer, glNormalPointer, glColorPointer, glTexCoordPointer, glInterleavedArrays y glVertexAttribPointerARB convierten direcciones de atributos mediante GP.
- glBindBufferARB transmite identificadores, y glBufferDataARB transmite datos cliente mediante GP.

Contrato OpenGL:
- Con GL_ELEMENT_ARRAY_BUFFER=0, el cuarto argumento de glDrawElements representa puntero a índices cliente: traducir con GP es adecuado.
- Con GL_ELEMENT_ARRAY_BUFFER != 0, ese argumento se interpreta como offset en bytes del buffer: GP cambia su valor de forma incorrecta.
- Con GL_ARRAY_BUFFER != 0, el argumento pointer de glVertexPointer y derivados es offset en bytes: necesita conservarse como valor numérico.
- Con binding cero, sigue siendo dirección cliente y necesita traducción.

**Consecuencia:** la presencia de thunks ARB no prueba que la ruta VBO esté preparada. Habilitarla solo será seguro tras:
1. Registrar y mantener el binding efectivo GL_ARRAY_BUFFER/GL_ELEMENT_ARRAY_BUFFER para cada contexto.
2. Separar explícitamente en los thunks cada parámetro cliente vs offset de buffer, con cobertura de glDrawRangeElements y arrays multi-textura.
3. Probar un buffer enlazado con offset 0 y offset >0, y un puntero cliente real; la diferencia debe verificarse por contenido renderizado o lectura de salida, no solo compilación.
4. Comprobar que la capa GL4ES no reinterpreta ese offset como memoria cliente y que los estados se restauran correctamente entre draw calls.
5. Solo entonces contrastar la ruta estática del motor en un dispositivo.

Este hallazgo implica oportunidad de rendimiento **y riesgo de corrección**. El ahorro FPS todavía es hipotético.

### 3.3 Posible elección de ruta estática original

OpenCoD1 reconstruye varias estrategias de almacenamiento y caché de modelos estáticos: Generic, ARB, ATI y NV. El renderer usa variables de configuración y capacidades para escoger. El camino exacto del ejecutable CoD SP 1.5 tiene que verificarse independientemente contra su propio binario.

Registro que falta: número de superficies estáticas; ruta elegida por modelo/mapa; frecuencia de recreación de buffer; cantidad de bytes enviados por cada frame; estados/capacidades expuestos.

## 4. Quake3e: qué copiar conceptualmente y qué no

Revisión estudiada: fe07ae0eb34aad954715c74ec0cd76baa48a0419.

### 4.1 Static world VBO: code/renderer/tr_vbo.c

R_BuildWorldVBO:
- Verifica soporte de buffers y opción de VBO.
- Requiere otros recursos de shader y unidades de texturas.
- Recorre superficies de mundo, clasificando candidatas estáticas.
- Calcula tamaños de índices/vértices antes de reservar la memoria.
- Empaqueta geometría, colores, normales y coordenadas de textura.
- Prepara colas que, cuando es rentable, permiten dibujar grupos contiguos de índices.

isStaticShader rechaza shaders especiales/incompatibles (deformaciones, ciertas alteraciones de textura, etapas no estáticas, etc.). VBO_PrepareQueues ordena items y forma tramos de índices cuando procede.

**Idea transferible:** separar geometría estática preprocesable de dinámica, cachear buffers de mundo, minimizar copias y dibujos pequeños sin sacrificar materiales especiales. No asumir que todo alambrado o efecto de la escena sea estático y compatible.

**Precondición crítica para CallofRecomp:** corregir primero traducción de offsets de buffers y verificar compatibilidad real de shaders y funciones ARB. No activar r_vbo/LIBGL_BATCH como solución sin pruebas.

### 4.2 Caché de estados y sorting

code/renderer/tr_backend.c:
- GL_State evita emitir cambios redundantes según bits de estado.
- RB_RenderDrawSurfList compara orden/sort y tiene camino rápido para estados consecutivos iguales; evita procesar el estado completo cuando no cambia.
- Los cambios de entidad, textura, fog, shader y dlight siguen pudiendo forzar cambios.

**Idea transferible:** medir cambios de estado *reales* enviados a GL4ES/GLES, no solo invocaciones desde código recompilado. Si el motor ya filtra redundancia, otro filtro superficial puede empeorar CPU.

### 4.3 Culling y LOD

code/renderer/tr_world.c: visibilidad, frustum y superficies por tipo.  
code/renderer/tr_mesh.c: R_CullModel y R_ComputeLOD antes de añadir superficies.

**Idea transferible:** contar superficies candidatas, rechazadas y finalmente dibujadas, y medir tiempo de culling. Un culling demasiado caro puede costar más que lo que ahorra si los objetos son diminutos; medir por escena.

### 4.4 ARM64 VM

code/qcommon/vm_aarch64.c:
- asignación de registros enteros y escalares;
- caché de constantes;
- reducción de cargas y direcciones;
- reutilización de retornos y optimizaciones de FPU.

Es un compilador para una VM de Quake3e, NO un sustituto del generador de p-code de CoD. Utilizar sus estrategias como lista de chequeo del ensamblador ARM64 de chunks medidos. No copiar su backend ni alterar el modelo de memoria sin pruebas de equivalencia.

## 5. OpenCoD1: subsistemas específicos de Call of Duty

Revisión estudiada: 718e994af62ca2cbc79d911bab73c445637b94e7.

OpenCoD1 reconstruye sobre todo Call of Duty 1.x multiplayer; las estructuras, offsets, funciones o cvars pueden variar con single-player 1.5. No copiar su código: el proyecto no declara una licencia reutilizable clara en el inventario local.

### 5.1 DPVS: src/renderer/tr_dpvs.c

Funciones candidatas:
- R_AddWorldSurfacesDPVS;
- R_AddTrianglesSurface;
- R_CullOccluderByPlane, R_AddCellOccluders;
- filtros de modelos hacia celdas;
- controles de frustum/occlusión.

Medir, por frame, tiempo total de la preparación DPVS, nodos/celdas/superficies visitadas, superficies rechazadas y superficies añadidas. Relacionar con cuándo entra en vista el alambrado.

### 5.2 Modelos estáticos: src/renderer/tr_staticmodel.c y tr_staticmodelcache.c

R_RegisterStaticModel, R_FinishLoadingStaticModels, R_CacheStaticModelSurface y SMC_Allocate muestran preparación y caché específicos de CoD. Se observan estrategias Generic/ARB/ATI/NV y almacenamiento de superficies.

**Experimento:** una vez identificadas las funciones SP correspondientes, anotar por mapa memoria temporal usada, número de objetos estáticos, número de cachés reutilizados e inserciones/evicciones. Evitar recalcular el mundo estático en cada frame, pero validar invalidaciones por nivel y materiales animados.

### 5.3 Materiales y envío: tr_shade.c, tr_main.c

RB_SetupMultitexture, RB_BindAnimatedImage, glDrawElements y R_RenderView/R_GenerateDrawSurfs/R_SortDrawSurfs revelan separación entre preparación de superficies, cambios de material y trabajo GL.

**Experimento:** top N materiales por draws y cambios de textura; agrupar solo dentro de límites de blending, orden transparente y textura compatibles. No reordenar transparencias automáticamente.

### 5.4 Animación de XModels: src/renderer/tr_xanim.c

RB_SurfaceXModelRigid y RB_SurfaceXModelWeight permiten distinguir trabajo rígido, ponderado y variantes SSE/ARB/ATI/NV. Su coste concreto en SP Android no está identificado.

Contar modelos animados visibles, vértices procesados, coste de transformaciones por modelo y frecuencia de pose update. No optimizar IA o colisiones basándose en la cantidad de soldados antes de medir.

### 5.5 Colisiones: src/qcommon/cm_trace.c

CM_TraceThroughBrush/Patch/Leaf y caminos de terreno/patch implementan pruebas previas de volumen y contadores para evitar repetir chequeos dentro de un recorrido.

**Experimento:** CPU por tipo de trace, número de brushes/patches probados y tasa de rechazo. Cambiar esto solo si el perfil real lo revela; la física es sensible a errores de determinismo.

### 5.6 Filesystem: src/qcommon/files.c

FS_Read2, FS_FOpenFileRead_Internal y búsquedas por rutas y paquetes dan contexto sobre la carga del CoD original. La llamada host ReadFile no representa toda la lectura lógica, búsqueda de ZIP o descompresión.

## 6. GL4ES: auditoría de trabajo CPU y de GPU

Revisión integrada: ec16bedd8819c475326f4f1a3063772c6d986e06. Copia local fijada por tools/recomp/build_android.py y modificada solo por el parche controlado de normalización en array.c.

### 6.1 Dibujo: src/gl/drawing.c

gl4es_glDrawElements:
- decide interceptar o usar camino normal;
- puede activar creación de lista si hay modo de batching;
- convierte índices a GL_UNSIGNED_SHORT si el tipo/driver no soporta el camino directo;
- cuando se intercepta o compila lista, puede reservar/copiar índices y transformarlos;
- en la ruta normal llama al backend mediante glDrawElementsCommon.

gl4es_glDrawArrays tiene también rutas directas y de interceptación/lista.

**No asumir copia por draw:** las rutas normales GLES2 con matrices compatibles pueden pasar datos directamente. Contar la ruta que verdaderamente se utiliza.

### 6.2 Conversión de arrays: src/gl/array.c

copy_gl_array, copy_gl_array_convert y copy_gl_pointer* convierten tipos, anchos, strides o colores. Algunos caminos reservan memoria y realizan memcpy. Medir:
- llamadas por frame a conversión;
- bytes de origen y destino;
- llamadas malloc/realloc/free;
- número de conversiones realmente necesarias por atributos de cliente;
- repetición exacta de la misma geometría/datos.

El parche local ya omite restar cero en normalize_indices_us/ui cuando min=0. Es conservador y está probado; no se ha demostrado que ese camino domine la escena.

### 6.3 Shaders: src/gl/fpe.c y fpe_cache.c

fpe_program:
- materializa estado relevante de fixed-function;
- compara estado actual;
- consulta caché de programas de emulación;
- cuando falta programa puede crear shader, compilar y enlazar.

fpe_cache.c posee hash de estado y un archivo de programas precompilados opcional (PSA). init.c consulta LIBGL_NOPSA/LIBGL_PSA_FOLDER y capacidades del driver.

**Hipótesis separadas:**
- Recompilación de shaders no vistos durante la inicialización o primera visita: picos de carga/frames.
- Muchas transiciones entre shaders ya cacheados: coste CPU recurrente, no compilación.
- Caché PSA ausente/no utilizable en Android: carga fría y caliente parecidas.

No habilitar cache persistente sin comprobar soporte program binary, ruta de guardado escribible, compatibilidad entre versiones de driver/shader y política de invalidación. Instrumentar cache hit/miss y tiempo de shader compile/link.

### 6.4 Texturas: src/gl/texture.c

swizzle_texture, pixel_convert, TexImage2D y TexSubImage2D pueden convertir formatos y reservar buffers temporales. Separar bytes cargados al entrar al mapa de bytes subidos cada frame. Un upload repetido durante combate puede generar stalls; un upload masivo solo en carga explica otra categoría.

### 6.5 Batching y VBO: src/gl/init.c

LIBGL_BATCH por defecto deshabilitado en esta revisión; LIBGL_USEVBO tiene modos distintos y por defecto el sistema declara modo 1 en el camino GLES2. En GL4ES, batching puede reducir draws *o* sumar conversiones y memoria transitoria.

**A/B futuro, solo después de corregir la compatibilidad del bridge:** modo actual contra variantes controladas, comparando draws GLES, allocations, CPU activo, GPU busy, memoria y errores visuales. Ningún valor experimental debe introducirse silenciosamente en builds generales.

## 7. openmohaa: reutilización de animaciones

Revisión estudiada: a2f340195975f4f042e28a60b62561dd9a0b2700.

- code/skeletor/skeletor.cpp: SetPose prepara blends y marca huesos sucios.
- code/skeletor/skeletorbones.cpp: skelBone_Base::GetTransform devuelve matriz cacheada cuando no está dirty; en caso contrario recalcula mediante GetDirtyTransform y dependencias parentales.
- Esto demuestra una estrategia de invalidez/reutilización, no compatibilidad directa de formatos TIKI con XModel de CoD SP.

**Aplicación únicamente si el perfil lo justifica:** cache de matrices por pose/personaje, cálculo jerárquico una vez por actualización y consumo repetido de matrices en render/adjuntos. Medir exactitud de pose, blend, attach points, hitboxes y FPS; evitar desincronización visual/colisión.

## 8. Árbol causal de los ~5 FPS en la zona de alambres

### Escenario A: CPU recompilada en funciones gráficas (primero a medir)

Indicadores: CPU activa del hilo alta; chunks identificados como R_GenerateDrawSurfs, DPVS, RB_Surface*, sorting o materiales; tiempo GPU moderado. Acción posterior: selectivo -O2, loops nativos equivalentes, eliminar trabajo repetido, preprocesado de geometría.

### Escenario B: sobrecarga de bridge GL4ES

Indicadores: demasiadas llamadas thunk->GL4ES para draws de pocos triángulos, conversiones/allocs frecuentes, GLES draw calls significativamente menores o mayores que invocaciones originales, coste CPU activo alto. Acción posterior: batching seguro dentro del material, conversión cacheada donde entradas son inmutables, reducciones de estado ya comprobadas.

### Escenario C: GPU fill-rate/fragmentos

Indicadores: GPU fragment busy / frecuencia máxima alta, CPU con esperas, descenso pronunciado al bajar solo resolución y mantener el resto igual. Posible alambre/transparencias/overdraw; NO concluyente por simple conteo de objetos. Acción: optimizar geometría/orden de transparencias, overdraw, no sacrificar NPC ni objetivos.

### Escenario D: animación

Indicadores: incrementos proporcionales al número de soldados visibles; altos tiempos en transforms/XModel. Acción: reuse de cálculos de pose, SIMD en kernels matemáticos validados, LOD coherente con distancia sin alterar conducta.

### Escenario E: colisiones/IA

Indicadores: top chunks de trazas o simulación, no del renderer; la carga varía con movimiento/interacción más que con cámara. Acción: optimizar broadphase/filtrado y evitar cálculos redundantes con equivalencia total.

### Escenario F: térmico/planificación

Indicadores: FPS normal tras arranque, caída progresiva con reducción de clocks CPU/GPU, tiempo en runnable/espera. Acción: reducir CPU sostenida y sync innecesarios; NO ocultar el efecto con FPS temporales.

## 9. Investigación de CL_InitCGame: 47 s no son 47 s de ReadFile

Etapas a medir por hitos, sin falsificar porcentajes:
1. Inicio del nivel; creación del estado del cliente.
2. Búsqueda de recursos y aperturas PK3; tiempo y cantidad por tamaño.
3. Lectura/copia PK3; fallos de página si OS expone métricas.
4. Descompresión ZIP y creación de assets lógicos.
5. Parseo/preparación BSP, mapas, modelos y animaciones.
6. Texturas: formato, conversiones y uploads.
7. Shaders GL4ES: compilación/enlace y reutilización en caché.
8. Inicialización cgame/VM, entidades, scripts, UI/HUD.
9. Presentación de primer frame listo.

Cada etapa reportará tiempo de pared, tiempo CPU del hilo pertinente, número de operaciones, bytes y picos de memoria. Utilizar trazas ATrace y contadores de host; los pasos internos del binario se asocian a chunks mapeados localmente, no modificando código derivado distribuido.

A/B de carga:
- fría tras reinicio o limpieza **controlada** de cachés no esenciales (sin destruir datos de usuario);
- caliente con caches OS/driver ya pobladas;
- 5 ejecuciones por variante; mismo mapa y dispositivo;
- evitar que una compilación o aplicación de archivos durante la prueba sesgue el resultado.

No reiterar mmap/índice de dispatch como la solución principal: ya existen y anteriores ensayos no demostraron resolver la inicialización completa.

## 10. Plan de instrumentación de bajo overhead

### 10.1 Modo diagnóstico separado

Mantener producción sin CPU sampler. Diagnóstico compilado mediante CODRECOMP_CPU_PROFILING=ON (su definición se limita a guest.c). Crear el archivo de activación pertinente solo en el perfil del dispositivo y reiniciar. No suponer que crear cpu_stats en APK normal habilita código ausente.

Semántica actual:
- window.c registra frame stats cada ~1 s con fps, ms avg/min/max, cpu, swap y pace.
- guest.c registra muestras de chunks y thunks cada ~5 s, con periodo pseudoaleatorio para evitar aliasing.
- muestreo tiene overhead y los tiempos pueden incluir host nested; no inferir porcentajes exactos sumándolos.

### 10.2 Contadores nuevos sugeridos (no implementados por este informe)

HOST / THUNK:
- numero de llamadas por familia gl*, kernel32/files*, audio y miscellaneous por segundo;
- tiempo de CPU muestreado, total y por función; llamadas a glGetError/glGetString;
- bytes/operaciones FS_READ/SEEK/OPEN/MAP.

GL4ES:
- draws recibidos; draws reales del backend;
- draws directos / interceptados / list render;
- triángulos e índices por draw (histograma, mediana y p95);
- numero de cambios reales de shader, textura, blend/depth;
- cache hit/miss FPE y tiempo de compilación/link;
- bytes y tiempo de conversiones de arrays;
- temporary allocation count/bytes;
- bytes TexImage/TexSubImage, formato fuente/destino;
- uso efectivo VBO/IBO, ruta client arrays.

RECOMP:
- top chunks por CPU muestreada y frecuencia;
- frecuencia de retorno guest_run; llamadas al dispatcher;
- conteo de saltos entre chunks por frame;
- mapeo OFFLINE a función original verificada, preservando información privada fuera de Git.

LOAD:
- marcas de etapa, tiempo wall+CPU, número/bytes de recursos, first frame ready;
- cantidad de shaders nuevos frente a reutilizados.

Tomar contadores atómicos solo cuando haga falta y preferir un único hilo si es seguro. Un flush por ventana agregada (p.ej. 5 s); nunca printf por draw, por vértice ni por instrucción.

### 10.3 API de trazas Android

Android NDK dispone de ATrace_beginSection / ATrace_endSection desde API 23; la APK tiene minSdk 26. Deben estar balanceadas dentro del mismo hilo; proteger con ATrace_isEnabled. Para versiones de API modernas, ATrace_setCounter permite métricas numéricas desde API 29. Perfetto y APA pueden visualizar los slices si la configuración de tracing los recoge.

Marcas de alta granularidad solo en operaciones gruesas: Frame_Engine, Frame_GL_Submit, Load_PK3, Load_Models, Load_Shaders, Load_CGame. Para operaciones pequeñas, usar sumarios, no slices por invocación.

Fuentes:
- https://developer.android.com/ndk/reference/group/tracing
- https://perfetto.dev/docs/getting-started/atrace
- https://developer.android.com/android-performance-analyzer/

## 11. Medición en Android físico y límites de las herramientas

### 11.1 Android Performance Analyzer (APA)

Usar System Profiler para planificación CPU, frecuencia, estado de hilos, GPU busy/counters si el dispositivo los expone, memoria y consumo energético. Elegir una captura inferior a 60 s con escena fluida, escena mala y carga (idealmente capturas separadas). Guardar proyecto/capturas en .local/profiles.

La versión pública de APA documenta Frame Profiler de Vulkan; el OpenGL directo necesita una capa ANGLE hacia Vulkan. CallofRecomp funciona con GL4ES sobre GLES2; no asumir que el Frame Profiler capturará sus draw calls directamente, ni cambiar el backend solo para obtener perfiles.

Fuentes:
- https://developer.android.com/android-performance-analyzer/frame-profiler/compatibility
- https://developer.android.com/android-performance-analyzer/run

### 11.2 Perfetto y herramientas NDK

Agregar slices de ATrace en host y estudiar trazas de scheduling, CPU frequency, GPU counters/render stages disponibles. Callstack sampling puede estar restringido en dispositivos comerciales; no desactivar la seguridad del teléfono por conveniencia. En ausencia de simpleperf/debuggerd, conservar el sampler opt-in por chunk y sumar contadores.

### 11.3 Repetibilidad

- Mismo teléfono/versión/API/driver, mismo mapa, ruta y pose de cámara, mismas configuraciones.
- Comparación A/B/A/B de compilaciones con identificación SHA, nunca entre diferentes assets/versiones.
- 30–60 s de estabilización antes de cada traza, y registrar temperatura/frecuencias.
- Presentar p50/p95/p99 de frame time y FPS equivalente; no solo FPS instantáneo.
- Repetir 3–5 veces y reportar dispersión. Separar instrumentación ON de la validación final OFF.

## 12. Experimentos priorizados y criterios para aprobar cambios

| ID | Cambio experimental | Condición previa | Métrica de éxito | Riesgo |
|----|---------------------|------------------|------------------|--------|
| E0 | Captura 0.2.3 Android ARM64 en escena de entrenamiento | Dispositivo disponible | Baseline de CPU/GPU/frame/carga con reproducibilidad | Bajo |
| E1 | Mapeo de top 20 chunks/thunks a subsistema SP | E0 y análisis privado local | Tiempo y función atribuibles, sin confundir nested samples | Bajo |
| E2 | Contadores direct/intercepted/list en GL4ES | E0 y build diagnóstico | Ratio real y bytes convertidos | Bajo-medio |
| E3 | Registro de ruta de modelos estáticos (Generic/ARB/etc.) | E1/E2 | Ruta elegida y frecuencia de rebuild por frame | Bajo |
| E4 | -O2 solo en 5–10 chunks medidos | E1; equivalencia completa | Reducción de frame p95/CPU y código razonable | Medio |
| E5 | Cache de array/índices o eliminación de conversiones redundantes | E2 con ruta caliente | Menor CPU/alloc sin modificar bytes dibujados | Medio |
| E6 | Compatibilidad de offsets para VBO/IBO | Tests GL exhaustivos | Binding, offsets y punteros cliente correctos | Alto |
| E7 | Activación selectiva y A/B de ruta VBO estática | E3 y E6; validación shaders | Menos draws/copia/CPU, sin anomalías en mapas | Alto |
| E8 | Shader compilation cache PSA/config | Cache miss real demostrado | Menor tiempo carga sin errores/incompatibilidad de drivers | Medio |
| E9 | Optimización de XModel/poses | E1 y costes de animación altos | Menor tiempo transform manteniendo poses y colisiones | Medio-alto |
| E10 | Trace/culling CPU | E1 y costes altos de DPVS/CM | Menor tiempo y estado idéntico | Alto |
| E11 | Desglose y optimización de carga | Capturas load | Menor wall/CPU en etapa dominante | Medio |

**Reglas de aceptación:**
- Una sola variable por experimento, contraprueba A/B.
- Pruebas de equivalencia de estado completo para cualquier cambio al recompiler.
- Tests de GL con client pointer, buffer offset cero y no cero, stride, draw modes y una ruta de transparencia.
- Visual y gameplay sobre la misma escena: soldados, animaciones, fog, alambres, HUD, misión, interacción y guardado.
- Sin reducción unilateral de calidad ni simplificación de IA como sustituto de la mejora.
- Compilación y CI verdes, APK firmada y auditoría de ausencia de recursos originales.
- Registrar regresiones y revertir si la diferencia es ruido o empeora p95/temperatura.
- Objetivo sugerido: >10 % sostenido de mejora de p95 frente a baseline en la escena afectada para un cambio importante; este es umbral de decisión, **no predicción de FPS**.

## 13. Prioridad de ejecución recomendada

**P0 — Conseguir evidencia reproducible:** dispositivo con APK 0.2.3, sistema APA/Perfetto, frame_stats y diagnóstico muestreado que no altere release. Crear baseline, no suposiciones.

**P0 — Auditar correctamente la ruta gráfica:** comparar culling/prepare/sort, thunks y GL4ES; saber qué porcentaje de tiempo se gasta en cada frontera y cuántos draws llegan a GLES.

**P1 — Pequeñas mejoras medidas de CPU:** -O2 por chunks, optimización de punto flotante/aritmética solamente cuando el chunk caliente lo justifique; vigilar tamaño ARM64 e I-cache.

**P1 — Explorar capacidades de hardware y ruta estática:** la whitelist actual y la semántica incorrecta de offsets ofrecen una pista especialmente concreta. Corregir el bridge con pruebas antes de cualquier intento de VBO. No prometer mejora sin medir.

**P1 — Carga:** identificar subetapa real de CL_InitCGame: PK3, descompresión, modelos, texturas, shaders, cgame. Mejorar la dominante.

**P2 — Animación, colisiones y efectos:** solo según perfiles medidos, no por sospecha visual.

**P3 — Rediseño global del renderer/Vulkan/threads:** únicamente si alternativas más acotadas están agotadas y las métricas demuestran un límite arquitectónico irremediable.

## 14. Cambios que NO deben hacerse por intuición

1. No sustituir el renderer por Quake3e: motor, ABI, materiales y culling difieren.
2. No copiar funciones de OpenCoD1 sin licencia y sin correspondencias independientes SP.
3. No portar Skeletor de openmohaa: no son los mismos formatos/modelos que Call of Duty.
4. No activar LIBGL_BATCH/LIBGL_USEVBO globalmente ni quitar whitelist GL sin arreglar offsets y probar GLES.
5. No habilitar -O2 en todos los chunks: el crecimiento de .text puede anular la ventaja.
6. No descomprimir todo PK3 a RAM: mayor memoria y picos sin medir.
7. No crear threads de preparación mientras el motor recompilado no garantice invariantes de memoria y orden.
8. No deshabilitar AI, colisiones, objetivos, scripts o sonidos para inflar un contador de FPS.
9. No atribuir GPU únicamente por tiempo de SDL_GL_SwapWindow.
10. No declarar victoria usando solo WSA, tests sintéticos o bench aislados.
11. No publicar perfiles privados, rutas internas del usuario, assets comerciales ni resultados derivados de código original que deban permanecer locales.

## 15. Artefactos y evidencia a generar en el workspace CORRECTO

Destino local privado preferido: .local/profiles/ (en workspace callofrecomp, NO el workspace demo de Case-Recomp).

- baseline_023_device_and_build.md: modelo, SoC, versión Android, driver, manifest/sha de APK, perfil y parámetros.
- 023_training_frame_stats.log: segmentos de render y juego, sin datos personales.
- 023_training_cpu_chunks.csv: VA y samples en privado, nunca en el repo público.
- 023_training_gpu_system_trace.perfetto-trace: captura APA/Perfetto y condiciones.
- 023_loading_phases.csv: wall/CPU/bytes/op por etapa de carga.
- 023_gl4es_counters.csv: direct/intercept/batch, conversiones, asignaciones, uploads y cache de shaders.
- function_map_private.md: correspondencia VA -> subsistema SP con pruebas del binario local.
- experiment_matrix.csv: SHA A/B, métricas, conclusión y criterio revert/retain.
- DIFFERENTIAL_VERIFICATION.md: equivalencia de estado y screenshots/referencias visuales privadas.

**Contrato de privacidad:** no subir esos archivos privados a GitHub. El informe actual es un índice técnico de código público, no reemplaza esa evidencia.

## 16. Checklist de revisión de código para futuras implementaciones

### Recompiler
- [ ] Identificar top chunks por ejecución ARM64 real, no sólo por conteo de instrucciones estáticas.
- [ ] Relacionar cada chunk con función SP verificada sin hacer commit de datos originales.
- [ ] Revisar ensamblador ARM64 y footprint para -O1 / -O2 por chunk, con checksum y estado completos.
- [ ] Separar CPU dentro de chunk y CPU en thunk sin doble contabilización.
- [ ] No alterar características semánticas de x87, flags, punteros alias, branch targets y excepciones.

### Renderer / bridge
- [ ] Registrar lista de extensiones visible por el invitado y capacidades reales GLES.
- [ ] Determinar fallback gráfico actual y razón de selección.
- [ ] Instrumentar los thunks Draw*/Vertex*/Tex* y su distribución.
- [ ] Identificar direct/intercept/list paths GL4ES.
- [ ] Verificar VBO/IBO client pointer vs byte offset en TODOS los thunks afectados.
- [ ] Capturar cantidad de draw calls y cambios efectivos de estado/material.
- [ ] Comparar cantidad de buffers/texturas/shaders creados por nivel y por frame.
- [ ] Verificar tamaño de textura/formatos y peso de conversión.
- [ ] Verificar invalidación de caché de shaders y estabilidad entre lanzamientos.

### Load / sistema
- [ ] Medir CL_InitCGame desglosado por segmentos e hilos.
- [ ] Distinguir frío/caliente sin alterar archivos de usuario.
- [ ] Registrar IO, decompression, parse, recursos y GPU upload.
- [ ] Conservar indicador de carga basado en hitos reales.
- [ ] Verificar FPS final con perfilado desactivado y A/B reproducible.

## 17. Índice de fuentes primarias (revisiones fijadas)

**CallofRecomp:**
- https://github.com/Dr3amyBerry/callofrecomp/blob/main/PROGRESS.md
- https://github.com/Dr3amyBerry/callofrecomp/blob/main/tools/recomp/pcode2c.py
- https://github.com/Dr3amyBerry/callofrecomp/blob/main/tools/recomp/runtime/guest.c
- https://github.com/Dr3amyBerry/callofrecomp/blob/main/tools/recomp/runtime/dispatch_index.h
- https://github.com/Dr3amyBerry/callofrecomp/blob/main/tools/recomp/runtime/window.c
- https://github.com/Dr3amyBerry/callofrecomp/blob/main/tools/recomp/runtime/gl_thunks.c
- https://github.com/Dr3amyBerry/callofrecomp/blob/main/tools/recomp/runtime/gl_thunks.h
- https://github.com/Dr3amyBerry/callofrecomp/blob/main/tools/recomp/runtime/files.c
- https://github.com/Dr3amyBerry/callofrecomp/blob/main/android/CMakeLists.txt
- https://github.com/Dr3amyBerry/callofrecomp/blob/main/tools/recomp/patch_gl4es.py
- https://github.com/Dr3amyBerry/callofrecomp/blob/main/docs/ANDROID_PERFORMANCE.md
- https://github.com/Dr3amyBerry/callofrecomp/blob/main/docs/FRAME_PACING.md

**Quake3e fe07ae0eb34aad954715c74ec0cd76baa48a0419:**
- https://github.com/ec-/Quake3e/blob/fe07ae0eb34aad954715c74ec0cd76baa48a0419/code/renderer/tr_vbo.c
- https://github.com/ec-/Quake3e/blob/fe07ae0eb34aad954715c74ec0cd76baa48a0419/code/renderer/tr_backend.c
- https://github.com/ec-/Quake3e/blob/fe07ae0eb34aad954715c74ec0cd76baa48a0419/code/renderer/tr_world.c
- https://github.com/ec-/Quake3e/blob/fe07ae0eb34aad954715c74ec0cd76baa48a0419/code/qcommon/vm_aarch64.c

**OpenCoD1 718e994af62ca2cbc79d911bab73c445637b94e7:**
- https://github.com/opencod1/opencod1/blob/718e994af62ca2cbc79d911bab73c445637b94e7/src/renderer/tr_dpvs.c
- https://github.com/opencod1/opencod1/blob/718e994af62ca2cbc79d911bab73c445637b94e7/src/renderer/tr_staticmodelcache.c
- https://github.com/opencod1/opencod1/blob/718e994af62ca2cbc79d911bab73c445637b94e7/src/renderer/tr_staticmodel.c
- https://github.com/opencod1/opencod1/blob/718e994af62ca2cbc79d911bab73c445637b94e7/src/renderer/tr_xanim.c
- https://github.com/opencod1/opencod1/blob/718e994af62ca2cbc79d911bab73c445637b94e7/src/qcommon/cm_trace.c

**GL4ES ec16bedd8819c475326f4f1a3063772c6d986e06:**
- https://github.com/ptitSeb/gl4es/blob/ec16bedd8819c475326f4f1a3063772c6d986e06/src/gl/drawing.c
- https://github.com/ptitSeb/gl4es/blob/ec16bedd8819c475326f4f1a3063772c6d986e06/src/gl/array.c
- https://github.com/ptitSeb/gl4es/blob/ec16bedd8819c475326f4f1a3063772c6d986e06/src/gl/fpe.c
- https://github.com/ptitSeb/gl4es/blob/ec16bedd8819c475326f4f1a3063772c6d986e06/src/gl/fpe_cache.c
- https://github.com/ptitSeb/gl4es/blob/ec16bedd8819c475326f4f1a3063772c6d986e06/src/gl/texture.c
- https://github.com/ptitSeb/gl4es/blob/ec16bedd8819c475326f4f1a3063772c6d986e06/src/gl/init.c

**openmohaa a2f340195975f4f042e28a60b62561dd9a0b2700:**
- https://github.com/openmoh/openmohaa/blob/a2f340195975f4f042e28a60b62561dd9a0b2700/code/skeletor/skeletor.cpp
- https://github.com/openmoh/openmohaa/blob/a2f340195975f4f042e28a60b62561dd9a0b2700/code/skeletor/skeletorbones.cpp

**Android y Perfetto:**
- https://developer.android.com/android-performance-analyzer/
- https://developer.android.com/android-performance-analyzer/frame-profiler/compatibility
- https://developer.android.com/ndk/reference/group/tracing
- https://perfetto.dev/docs/getting-started/atrace
- https://perfetto.dev/docs/data-sources/gpu

## 18. Conclusión

La investigación descarta el enfoque de "más optimización por intuición". La prueba estática más importante es que el host limita las capacidades OpenGL visibles al motor y que sus thunks actuales no distinguen offsets VBO/IBO de direcciones cliente. Esto puede impedir usar rutas estáticas aceleradas que existen conceptualmente en motores de la familia y, a la vez, explica por qué habilitarlas directamente sería arriesgado.

La segunda frontera importante es GL4ES: solo un perfil real decidirá si el coste principal está en conversiones, dibujo de superficies pequeñas, cambios de estado, generación de shaders o código recompilado alrededor de esas llamadas. Para la carga, es imprescindible separar PK3, descompresión, modelos, textura/shaders y CL_InitCGame.

**Estado final de este documento:** investigación estática ampliada, con subsistemas concretos, hipótesis falsables, métricas, matriz de experimentos y criterios de aceptación. Sin modificaciones al motor, sin benchmark nuevo en teléfono y sin afirmaciones de FPS ganados.
