# Portal EFOS — autenticación y fuente de datos

La autenticación sigue activa (`auth/users.txt`).

Desde **v0.4.7** el flujo principal ya no utiliza Browse / drag & drop. La interfaz consume directamente los datasets disponibles en `data/raw/statsbomb/` mediante el catálogo automático:

`Liga -> Temporada -> Equipo -> Periodo`

El uploader multi-CSV de versiones anteriores se conserva únicamente como código legado para desarrollo, pero no forma parte de la navegación v2 del producto.

Menú v2:

`Selección de Equipo | Informe Ejecutivo | Modelo de Juego y DT | Ataque Organizado | Defensa Organizada | Transiciones | Balón Parado | Momentos del Partido`
