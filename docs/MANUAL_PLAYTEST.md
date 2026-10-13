# Pruebas de juego pendientes

El usuario realizará las comprobaciones visuales y las partidas completas.
Los arranques y las pruebas automáticas no certifican todos los objetivos.

## Primero: entrenamiento

- Comprobar el modo panorámico: ver más escenario a los lados, con personas y
  objetos proporcionados. Probar también apuntar y la posición de menús/HUD.
  El arranque aplica resolución nativa, `r_mode -1`, `r_customaspect` y un FOV
  ajustado a la pantalla; no hace falta editar la configuración del juego.

- Iniciar una partida nueva y entrar al entrenamiento original.
- Moverse, girar despacio, apuntar y recargar: buscar saltos, aceleraciones o
  entradas que se queden pulsadas. El límite es 60 FPS; puede rendir menos.
- En Android, ocultar los controles, usar el menú y volver a mostrarlos.
- Completar todos los objetivos del entrenamiento y cerrar la victoria.
- Confirmar que el siguiente nivel carga y responde, sin pantalla negra ni cierre.
- Guardar, cerrar la aplicación, usar Continuar y comprobar posición/objetivos.
- Morir o reiniciar un nivel y comprobar que vuelve a funcionar.

## Campaña completa

En cada casilla, completar los objetivos y comprobar el paso al siguiente nivel.
No marcar una misión solo porque cargó. Probar también guardar/Continuar y
muerte/reintento. Priorizar Brecourt y Hurtgen, donde se corrigieron bloqueos.

- [ ] training
- [ ] pathfinder
- [ ] burnville
- [ ] dawnville
- [ ] carride
- [ ] brecourt
- [ ] chateau
- [ ] powcamp
- [ ] pegasusnight
- [ ] pegasusday
- [ ] dam
- [ ] truckride
- [ ] airfield
- [ ] ship
- [ ] stalingrad
- [ ] redsquare
- [ ] trainstation
- [ ] sewer
- [ ] pavlov
- [ ] factory
- [ ] railyard
- [ ] tankdrivecountry
- [ ] tankdrivetown
- [ ] hurtgen
- [ ] rocket
- [ ] berlin

Comprobar las pantallas de transición `us_intro`, `us_mid`, `uk_6ab`, `uk_sas`,
`ru_stalingrad`, `allied_start` y los créditos finales. Seguir la progresión normal,
sin saltar mapas por consola: cargar un mapa directamente no prueba su desbloqueo.

Si falla algo, indicar plataforma, nivel, último objetivo, qué acción lo provocó
y si hubo cierre, congelación o pantalla negra. El registro de Android está en
el perfil interno; el lanzador permite verlo.
