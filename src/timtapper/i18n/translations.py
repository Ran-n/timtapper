#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.159067
Revised: 2026/10/14 16:30:39.813437

Translation tables, keyed by the English source string exactly as written
in the code. English (EN) is built from the ES key set so it stays a
first-class table. When adding or renaming a user-facing string, add it to
EVERY table — tests/test_i18n.py fails on any missing or stale key.
"""

ES = {
    "Opening…": "Abriendo…",  # the web shell, while the app starts
    # navigation / screens
    "Events": "Eventos",
    "Event": "Evento",
    "Stats": "Estadísticas",
    "Settings": "Ajustes",
    "Press back again to exit": "Pulsa atrás otra vez para salir",
    "That event no longer exists": "Ese evento ya no existe",
    "timtapper could not open its database: {error}": "timtapper no pudo abrir su base de datos: {error}",
    # event types
    "Testing": "Testeo",
    "Pirates Party": "Pirates Party",
    "Locals": "Locales",
    "Release event": "Evento de lanzamiento",
    "Sealed": "Sellado",
    "Heroines Battle": "Heroines Battle",
    "Team battle": "Por equipos",
    "Store Championship": "Store Championship",
    "Treasure Cup": "Treasure Cup",
    "Flagship Battle": "Flagship Battle",
    "Extra Grand Battle": "Extra Grand Battle",
    "Regional": "Regional",
    "National": "Nacional",
    "World Championship": "Mundial",
    "Other": "Otro",
    # new event names, numbered per type
    "Testing #{n}": "Testeo #{n}",
    "Pirates Party #{n}": "Pirates Party #{n}",
    "Local #{n}": "Local #{n}",
    "Release #{n}": "Lanzamiento #{n}",
    "Sealed #{n}": "Sellado #{n}",
    "Heroines Battle #{n}": "Heroines Battle #{n}",
    "Team battle #{n}": "Equipos #{n}",
    "Store Championship #{n}": "Store Championship #{n}",
    "Treasure Cup #{n}": "Treasure Cup #{n}",
    "Flagship #{n}": "Flagship #{n}",
    "Extra Battle #{n}": "Extra Battle #{n}",
    "Regional #{n}": "Regional #{n}",
    "National #{n}": "Nacional #{n}",
    "Worlds #{n}": "Mundial #{n}",
    "Event #{n}": "Evento #{n}",
    # events list
    "New event": "Nuevo evento",
    "No events yet": "Aún no hay eventos",
    "Log a testing session, a locals or a major — then add each round as you play it.": (
        "Registra un testeo, un torneo local o un major — y añade cada ronda mientras la juegas."
    ),
    "No leader chosen": "Sin líder elegido",
    "1 round": "1 ronda",
    "{n} rounds": "{n} rondas",
    "#{place} of {players}": "#{place} de {players}",
    "#{place}": "#{place}",
    "{players} players": "{players} jugadores",
    "of {players} players": "de {players} jugadores",
    "place": "puesto",
    "Placement": "Puesto",
    "Players": "Jugadores",
    "Search events": "Buscar eventos",
    "Filters": "Filtros",
    "{shown} of {total} events": "{shown} de {total} eventos",
    "No events match": "Ningún evento coincide",
    "Try another search or filter.": "Prueba otra búsqueda u otro filtro.",
    "Clear filters": "Quitar filtros",
    # event screen
    "Event name": "Nombre del evento",
    "Type": "Tipo",
    "Playing": "Jugando",
    "Record": "Récord",
    "Tap to choose your leader": "Toca para elegir tu líder",
    "Your leader": "Tu líder",
    "Notes": "Notas",
    "Share result": "Compartir resultado",
    "Rounds": "Rondas",
    "No rounds yet — add one when you sit down to play.": "Aún no hay rondas — añade una al sentarte a jugar.",
    "Add round": "Añadir ronda",
    "Opponent's leader": "Líder rival",
    "Unknown leader": "Líder desconocido",
    "TC": "TC",
    "Win": "Victoria",
    "Loss": "Derrota",
    "Went 1st": "Fui 1º",
    "Went 2nd": "Fui 2º",
    "Won die roll": "Gané el dado",
    "Lost die roll": "Perdí el dado",
    "Top cut": "Top cut",
    "Round notes": "Notas de la ronda",
    "Change opponent": "Cambiar rival",
    "Delete round": "Borrar ronda",
    "Delete round {n}?": "¿Borrar la ronda {n}?",
    "This round and its notes will be removed.": "Se eliminarán esta ronda y sus notas.",
    "Remove noted games?": "¿Quitar partidas anotadas?",
    "Round {n}: the games this change drops hold results or turn orders, which will be removed.": (
        "Ronda {n}: las partidas que este cambio quita tienen resultados o turnos anotados, que se eliminarán."
    ),
    "Remove": "Quitar",
    "Delete": "Borrar",
    "Cancel": "Cancelar",
    "Delete event": "Borrar evento",
    "More options": "Más opciones",
    "Delete this event?": "¿Borrar este evento?",
    "The event and all its rounds will be removed. This can't be undone.": (
        "Se eliminarán el evento y todas sus rondas. No se puede deshacer."
    ),
    "Event deleted": "Evento borrado",
    "Could not save: {error}": "No se pudo guardar: {error}",
    "Could not save the change ({error})": "No se pudo guardar el cambio ({error})",
    # leader picker
    "Name, code or color": "Nombre, código o color",
    "Set": "Set",
    "All sets": "Todos los sets",
    "Red": "Rojo",
    "Green": "Verde",
    "Blue": "Azul",
    "Purple": "Morado",
    "Black": "Negro",
    "Yellow": "Amarillo",
    "No leader matches": "Ningún líder coincide",
    "{shown} of {total} leaders — search to find the rest": "{shown} de {total} líderes; busca para ver el resto",
    # stats
    "All leaders": "Todos los líderes",
    "Playing {leader}": "Jugando {leader}",
    "All event types": "Todos los tipos de evento",
    "Event type": "Tipo de evento",
    "Win rate": "% de victorias",
    "Going 1st": "Yendo 1º",
    "Going 2nd": "Yendo 2º",
    "Won the die roll": "Ganando el dado",
    "Lost the die roll": "Perdiendo el dado",
    "Best matchup": "Mejor enfrentamiento",
    "Worst matchup": "Peor enfrentamiento",
    "Not enough games": "No hay partidas suficientes",
    "Recent form": "Forma reciente",
    "Share summary": "Compartir resumen",
    "Matchups": "Enfrentamientos",
    "Share matchups": "Compartir enfrentamientos",
    "No games logged yet": "Aún no hay partidas registradas",
    "1st {first} · 2nd {second}": "1º {first} · 2º {second}",
    # share cards
    "Overall record": "Récord total",
    "1 event": "1 evento",
    "{n} events": "{n} eventos",
    "{rate} win rate": "{rate} de victorias",
    "1st": "1º",
    "2nd": "2º",
    "Result — tap to change": "Resultado — toca para cambiar",
    "Turn order — tap to change": "Orden de turno — toca para cambiar",
    "Die roll — tap to change": "Dado — toca para cambiar",
    "+{n} more": "+{n} más",
    "No rounds logged yet": "Aún no hay rondas registradas",
    "Opponent": "Rival",
    "W-L": "V-D",
    "Win %": "% Vict.",
    "Tracked with timtapper · One Piece TCG": "Registrado con timtapper · One Piece TCG",
    "Could not create the file ({error})": "No se pudo crear el archivo ({error})",
    "Could not share or save the file ({error})": "No se pudo compartir ni guardar el archivo ({error})",
    "Saved": "Guardado",
    # settings
    "Appearance": "Apariencia",
    "Language": "Idioma",
    "System": "Sistema",
    "Light": "Claro",
    "Dark": "Oscuro",
    "Theme": "Tema",
    "Classic": "Clásico",
    "Could not save this setting — it applies until the app restarts": (
        "No se pudo guardar este ajuste — se aplicará hasta que reinicies la app"
    ),
    "Could not save to this browser's storage — export a backup before closing the page": (
        "No se pudo guardar en el almacenamiento del navegador — exporta una copia antes de cerrar la página"
    ),
    "Leaders": "Líderes",
    "{n} leaders in the catalogue. New sets are added automatically.": (
        "{n} líderes en el catálogo. Las colecciones nuevas se añaden solas."
    ),
    "{n} new leaders added": "{n} líderes nuevos añadidos",
    "Update leaders": "Actualizar líderes",
    "Updating…": "Actualizando…",
    "Could not download leaders — check your connection and try again": (
        "No se pudieron descargar los líderes — revisa tu conexión e inténtalo de nuevo"
    ),
    "Leaders updated: {added} new, {updated} changed": "Líderes actualizados: {added} nuevos, {updated} cambiados",
    "{n} pictures could not be downloaded": "{n} imágenes no se pudieron descargar",
    "Backup": "Copia de seguridad",
    "Your data only lives on this device. Export a backup now and then so you never lose it.": (
        "Tus datos solo están en este dispositivo. Exporta una copia de vez en cuando para no perderlos nunca."
    ),
    "Export backup": "Exportar copia",
    "Import backup": "Importar copia",
    "timtapper backup": "Copia de timtapper",
    "Choose a backup file": "Elige un archivo de copia",
    "Could not open the file picker ({error})": "No se pudo abrir el selector de archivos ({error})",
    "Could not read that file": "No se pudo leer ese archivo",
    "Not a valid backup: {error}": "No es una copia válida: {error}",
    "Could not restore the backup ({error})": "No se pudo restaurar la copia ({error})",
    "Could not update leaders ({error})": "No se pudieron actualizar los líderes ({error})",
    "Events restored: {n}": "Eventos restaurados: {n}",
    "Restore this backup?": "¿Restaurar esta copia?",
    "All your current events will be replaced by the ones in the backup.": (
        "Todos tus eventos actuales se sustituirán por los de la copia."
    ),
    "Restore": "Restaurar",
    "About": "Acerca de",
    "Fan-made tracker. Not affiliated with or endorsed by Bandai, Eiichiro Oda or Shueisha. "
    "Leader data from optcgapi.com.": (
        "Tracker hecho por fans. Sin relación ni respaldo de Bandai, Eiichiro Oda o Shueisha. "
        "Datos de líderes de optcgapi.com."
    ),
    # rejected edits (events.repository.EventError), shown after "Could not save:"
    "event name is required": "el evento necesita un nombre",
    "event name is longer than {max} characters": "el nombre del evento pasa de {max} caracteres",
    "placement must be a whole number from 1 to {max}": "el puesto tiene que ser un número entero de 1 a {max}",
    "players must be a whole number from 1 to {max}": "los jugadores tienen que ser un número entero de 1 a {max}",
    "placement {placement} is past the {players} players": "el puesto {placement} supera los {players} jugadores",
    "notes must be text": "las notas tienen que ser texto",
    "date must be a date": "la fecha tiene que ser una fecha",
    "unknown event type {key!r}": "tipo de evento desconocido {key!r}",
    "unknown leader id {leader_id}": "líder desconocido (id {leader_id})",
    "unknown event fields: {fields}": "campos de evento desconocidos: {fields}",
    "unknown round fields: {fields}": "campos de ronda desconocidos: {fields}",
    "result must be one of {results} or None": "el resultado tiene que ser uno de {results} o ninguno",
    "went_first must be true, false or None": "el turno tiene que ser sí, no o desconocido",
    "event {event_id} not found": "no se encontró el evento {event_id}",
    "round {round_id} not found": "no se encontró la ronda {round_id}",
    # rounds: Swiss, top cut, byes; event standings and sets
    "1st place": "1.º puesto",
    "2nd place": "2.º puesto",
    "Top {n}": "Top {n}",
    "Outside the top {n}": "Fuera del top {n}",
    "Dropped": "Abandonado",
    "Not noted": "Sin anotar",
    "Swiss": "Suiza",
    "Bye": "Bye",
    "Byes": "Byes",
    "Automatic win": "Victoria automática",
    "Add a bye": "Añadir un bye",
    "a bye has no games": "un bye no tiene partidas",
    "a bye has no opponent": "un bye no tiene rival",
    "a played round needs an opponent": "una ronda jugada necesita un rival",
    "dropped must be true or false": "abandonado tiene que ser sí o no",
    "kind must be one of {kinds}": "el tipo de ronda tiene que ser uno de {kinds}",
    "unknown set {code!r}": "colección desconocida {code!r}",
    "event {event}, round {round}: a bye has no opponent, not {value!r}": (
        "evento {event}, ronda {round}: un bye no tiene rival, no {value!r}"
    ),
    "event {event}, round {round}: unknown kind of round {value!r}": (
        "evento {event}, ronda {round}: tipo de ronda desconocido {value!r}"
    ),
    "event {event}: dropped must be true/false/null, not {value!r}": (
        "evento {event}: abandonado tiene que ser true/false/null, no {value!r}"
    ),
    "event {event}: the set must be a set code, not {value!r}": (
        "evento {event}: la colección tiene que ser un código de colección, no {value!r}"
    ),
    # best of 3: games and who chose the turn order
    "Best of 1": "Al mejor de 1",
    "Best of 3": "Al mejor de 3",
    "Game {n}": "Partida {n}",
    "Games": "Partidas",
    "You": "Tú",
    "Opp": "Rival",
    "You chose turn": "Elegiste turno",
    "They chose turn": "Eligió el rival",
    "Who chose the turn order — tap to change": "Quién eligió el turno — toca para cambiarlo",
    "Who chose the turn order: the previous game's loser — tap to change": (
        "Quién eligió el turno: quien perdió la partida anterior — toca para cambiarlo"
    ),
    "games {record}": "partidas {record}",
    "best_of must be 1 or 3": "al mejor de tiene que ser 1 o 3",
    "chose_turn must be true, false or None": "quién eligió el turno tiene que ser sí, no o desconocido",
    "game {game_no} is not part of a best of {best_of}": (
        "la partida {game_no} no forma parte de un al mejor de {best_of}"
    ),
    "unknown game fields: {fields}": "campos de partida desconocidos: {fields}",
    "event {event}, round {round}: best of must be 1 or 3, not {value!r}": (
        "evento {event}, ronda {round}: al mejor de tiene que ser 1 o 3, no {value!r}"
    ),
    "event {event}, round {round}: the games are not a list": (
        "evento {event}, ronda {round}: las partidas no son una lista"
    ),
    "event {event}, round {round}: more games than a best of {best_of}": (
        "evento {event}, ronda {round}: más partidas que un al mejor de {best_of}"
    ),
    "event {event}, round {round}, game {game}: expected an object": (
        "evento {event}, ronda {round}, partida {game}: se esperaba un objeto"
    ),
    "event {event}, round {round}, game {game}: invalid result {value!r}": (
        "evento {event}, ronda {round}, partida {game}: resultado no válido {value!r}"
    ),
    "event {event}, round {round}, game {game}: the turn order must be true/false/null, not {value!r}": (
        "evento {event}, ronda {round}, partida {game}: el turno tiene que ser true/false/null, no {value!r}"
    ),
    "event {event}, round {round}, game {game}: who chose the turn order must be true/false/null, not {value!r}": (
        "evento {event}, ronda {round}, partida {game}: quién eligió el turno tiene que ser true/false/null, no "
        "{value!r}"
    ),
    # invalid backup files (backup.json_backup.BackupError), shown after "Not a valid backup:"
    "not a JSON file: {error}": "no es un archivo JSON: {error}",
    "not a timtapper backup": "no es una copia de timtapper",
    "unsupported backup version {version!r}": "versión de copia no compatible {version!r}",
    "the events are not a list": "los eventos no son una lista",
    "event {event}: expected an object": "evento {event}: se esperaba un objeto",
    "event {event}: unknown event type {value!r}": "evento {event}: tipo de evento desconocido {value!r}",
    "event {event}: invalid date {value!r}": "evento {event}: fecha no válida {value!r}",
    "event {event}: the rounds are not a list": "evento {event}: las rondas no son una lista",
    "event {event}: the placement must be a whole number from 1 to {max}, not {value!r}": (
        "evento {event}: el puesto tiene que ser un número entero de 1 a {max}, no {value!r}"
    ),
    "event {event}: the players must be a whole number from 1 to {max}, not {value!r}": (
        "evento {event}: los jugadores tienen que ser un número entero de 1 a {max}, no {value!r}"
    ),
    "event {event}: placement {placement} is past the {players} players": (
        "evento {event}: el puesto {placement} supera los {players} jugadores"
    ),
    "event {event}: the name must be text, not {value!r}": (
        "evento {event}: el nombre tiene que ser texto, no {value!r}"
    ),
    "event {event}: the name is longer than {max} characters": "evento {event}: el nombre pasa de {max} caracteres",
    "event {event}: the leader must be a leader code, not {value!r}": (
        "evento {event}: el líder tiene que ser un código de líder, no {value!r}"
    ),
    "event {event}: the notes must be text, not {value!r}": (
        "evento {event}: las notas tienen que ser texto, no {value!r}"
    ),
    "event {event}, round {round}: expected an object": "evento {event}, ronda {round}: se esperaba un objeto",
    "event {event}, round {round}: invalid result {value!r}": (
        "evento {event}, ronda {round}: resultado no válido {value!r}"
    ),
    "event {event}, round {round}: the opponent must be a leader code, not {value!r}": (
        "evento {event}, ronda {round}: el rival tiene que ser un código de líder, no {value!r}"
    ),
    "event {event}, round {round}: the turn order must be true/false/null, not {value!r}": (
        "evento {event}, ronda {round}: el turno tiene que ser true/false/null, no {value!r}"
    ),
    "event {event}, round {round}: the die roll must be true/false/null, not {value!r}": (
        "evento {event}, ronda {round}: la tirada de dado tiene que ser true/false/null, no {value!r}"
    ),
    "event {event}, round {round}: the top cut flag must be true/false/null, not {value!r}": (
        "evento {event}, ronda {round}: el top cut tiene que ser true/false/null, no {value!r}"
    ),
    "event {event}, round {round}: the notes must be text, not {value!r}": (
        "evento {event}, ronda {round}: las notas tienen que ser texto, no {value!r}"
    ),
}

GL = {
    "Opening…": "Abrindo…",  # the web shell, while the app starts
    # navigation / screens
    "Events": "Eventos",
    "Event": "Evento",
    "Stats": "Estatísticas",
    "Settings": "Axustes",
    "Press back again to exit": "Preme atrás outra vez para saír",
    "That event no longer exists": "Ese evento xa non existe",
    "timtapper could not open its database: {error}": "timtapper non puido abrir a súa base de datos: {error}",
    # event types
    "Testing": "Testeo",
    "Pirates Party": "Pirates Party",
    "Locals": "Locais",
    "Release event": "Evento de lanzamento",
    "Sealed": "Selado",
    "Heroines Battle": "Heroines Battle",
    "Team battle": "Por equipos",
    "Store Championship": "Store Championship",
    "Treasure Cup": "Treasure Cup",
    "Flagship Battle": "Flagship Battle",
    "Extra Grand Battle": "Extra Grand Battle",
    "Regional": "Rexional",
    "National": "Nacional",
    "World Championship": "Mundial",
    "Other": "Outro",
    # new event names, numbered per type
    "Testing #{n}": "Testeo #{n}",
    "Pirates Party #{n}": "Pirates Party #{n}",
    "Local #{n}": "Local #{n}",
    "Release #{n}": "Lanzamento #{n}",
    "Sealed #{n}": "Selado #{n}",
    "Heroines Battle #{n}": "Heroines Battle #{n}",
    "Team battle #{n}": "Equipos #{n}",
    "Store Championship #{n}": "Store Championship #{n}",
    "Treasure Cup #{n}": "Treasure Cup #{n}",
    "Flagship #{n}": "Flagship #{n}",
    "Extra Battle #{n}": "Extra Battle #{n}",
    "Regional #{n}": "Rexional #{n}",
    "National #{n}": "Nacional #{n}",
    "Worlds #{n}": "Mundial #{n}",
    "Event #{n}": "Evento #{n}",
    # events list
    "New event": "Novo evento",
    "No events yet": "Aínda non hai eventos",
    "Log a testing session, a locals or a major — then add each round as you play it.": (
        "Rexistra un testeo, un torneo local ou un major — e engade cada rolda mentres a xogas."
    ),
    "No leader chosen": "Sen líder escollido",
    "1 round": "1 rolda",
    "{n} rounds": "{n} roldas",
    "#{place} of {players}": "#{place} de {players}",
    "#{place}": "#{place}",
    "{players} players": "{players} xogadores",
    "of {players} players": "de {players} xogadores",
    "place": "posto",
    "Placement": "Posto",
    "Players": "Xogadores",
    "Search events": "Buscar eventos",
    "Filters": "Filtros",
    "{shown} of {total} events": "{shown} de {total} eventos",
    "No events match": "Ningún evento coincide",
    "Try another search or filter.": "Proba outra busca ou outro filtro.",
    "Clear filters": "Quitar filtros",
    # event screen
    "Event name": "Nome do evento",
    "Type": "Tipo",
    "Playing": "Xogando",
    "Record": "Récord",
    "Tap to choose your leader": "Toca para escoller o teu líder",
    "Your leader": "O teu líder",
    "Notes": "Notas",
    "Share result": "Compartir resultado",
    "Rounds": "Roldas",
    "No rounds yet — add one when you sit down to play.": "Aínda non hai roldas — engade unha ao sentarte a xogar.",
    "Add round": "Engadir rolda",
    "Opponent's leader": "Líder rival",
    "Unknown leader": "Líder descoñecido",
    "TC": "TC",
    "Win": "Vitoria",
    "Loss": "Derrota",
    "Went 1st": "Fun 1º",
    "Went 2nd": "Fun 2º",
    "Won die roll": "Gañei o dado",
    "Lost die roll": "Perdín o dado",
    "Top cut": "Top cut",
    "Round notes": "Notas da rolda",
    "Change opponent": "Cambiar rival",
    "Delete round": "Borrar rolda",
    "Delete round {n}?": "Borrar a rolda {n}?",
    "This round and its notes will be removed.": "Eliminaranse esta rolda e as súas notas.",
    "Remove noted games?": "Quitar partidas anotadas?",
    "Round {n}: the games this change drops hold results or turn orders, which will be removed.": (
        "Rolda {n}: as partidas que este cambio quita teñen resultados ou quendas anotadas, que se eliminarán."
    ),
    "Remove": "Quitar",
    "Delete": "Borrar",
    "Cancel": "Cancelar",
    "Delete event": "Borrar evento",
    "More options": "Máis opcións",
    "Delete this event?": "Borrar este evento?",
    "The event and all its rounds will be removed. This can't be undone.": (
        "Eliminaranse o evento e todas as súas roldas. Non se pode desfacer."
    ),
    "Event deleted": "Evento borrado",
    "Could not save: {error}": "Non se puido gardar: {error}",
    "Could not save the change ({error})": "Non se puido gardar o cambio ({error})",
    # leader picker
    "Name, code or color": "Nome, código ou cor",
    "Set": "Set",
    "All sets": "Todos os sets",
    "Red": "Vermello",
    "Green": "Verde",
    "Blue": "Azul",
    "Purple": "Morado",
    "Black": "Negro",
    "Yellow": "Amarelo",
    "No leader matches": "Ningún líder coincide",
    "{shown} of {total} leaders — search to find the rest": "{shown} de {total} líderes; busca para ver o resto",
    # stats
    "All leaders": "Todos os líderes",
    "Playing {leader}": "Xogando {leader}",
    "All event types": "Todos os tipos de evento",
    "Event type": "Tipo de evento",
    "Win rate": "% de vitorias",
    "Going 1st": "Indo 1º",
    "Going 2nd": "Indo 2º",
    "Won the die roll": "Gañando o dado",
    "Lost the die roll": "Perdendo o dado",
    "Best matchup": "Mellor enfrontamento",
    "Worst matchup": "Peor enfrontamento",
    "Not enough games": "Non hai partidas dabondo",
    "Recent form": "Forma recente",
    "Share summary": "Compartir resumo",
    "Matchups": "Enfrontamentos",
    "Share matchups": "Compartir enfrontamentos",
    "No games logged yet": "Aínda non hai partidas rexistradas",
    "1st {first} · 2nd {second}": "1º {first} · 2º {second}",
    # share cards
    "Overall record": "Récord total",
    "1 event": "1 evento",
    "{n} events": "{n} eventos",
    "{rate} win rate": "{rate} de vitorias",
    "1st": "1º",
    "2nd": "2º",
    "Result — tap to change": "Resultado — toca para cambiar",
    "Turn order — tap to change": "Orde de quenda — toca para cambiar",
    "Die roll — tap to change": "Dado — toca para cambiar",
    "+{n} more": "+{n} máis",
    "No rounds logged yet": "Aínda non hai roldas rexistradas",
    "Opponent": "Rival",
    "W-L": "V-D",
    "Win %": "% Vit.",
    "Tracked with timtapper · One Piece TCG": "Rexistrado con timtapper · One Piece TCG",
    "Could not create the file ({error})": "Non se puido crear o ficheiro ({error})",
    "Could not share or save the file ({error})": "Non se puido compartir nin gardar o ficheiro ({error})",
    "Saved": "Gardado",
    # settings
    "Appearance": "Aparencia",
    "Language": "Idioma",
    "System": "Sistema",
    "Light": "Claro",
    "Dark": "Escuro",
    "Theme": "Tema",
    "Classic": "Clásico",
    "Could not save this setting — it applies until the app restarts": (
        "Non se puido gardar este axuste — aplicarase ata que reinicies a app"
    ),
    "Could not save to this browser's storage — export a backup before closing the page": (
        "Non se puido gardar no almacenamento do navegador — exporta unha copia antes de pechar a páxina"
    ),
    "Leaders": "Líderes",
    "{n} leaders in the catalogue. New sets are added automatically.": (
        "{n} líderes no catálogo. As coleccións novas engádense soas."
    ),
    "{n} new leaders added": "{n} líderes novos engadidos",
    "Update leaders": "Actualizar líderes",
    "Updating…": "Actualizando…",
    "Could not download leaders — check your connection and try again": (
        "Non se puideron descargar os líderes — revisa a túa conexión e téntao de novo"
    ),
    "Leaders updated: {added} new, {updated} changed": "Líderes actualizados: {added} novos, {updated} cambiados",
    "{n} pictures could not be downloaded": "{n} imaxes non se puideron descargar",
    "Backup": "Copia de seguranza",
    "Your data only lives on this device. Export a backup now and then so you never lose it.": (
        "Os teus datos só están neste dispositivo. Exporta unha copia de cando en vez para non perdelos nunca."
    ),
    "Export backup": "Exportar copia",
    "Import backup": "Importar copia",
    "timtapper backup": "Copia de timtapper",
    "Choose a backup file": "Escolle un ficheiro de copia",
    "Could not open the file picker ({error})": "Non se puido abrir o selector de ficheiros ({error})",
    "Could not read that file": "Non se puido ler ese ficheiro",
    "Not a valid backup: {error}": "Non é unha copia válida: {error}",
    "Could not restore the backup ({error})": "Non se puido restaurar a copia ({error})",
    "Could not update leaders ({error})": "Non se puideron actualizar os líderes ({error})",
    "Events restored: {n}": "Eventos restaurados: {n}",
    "Restore this backup?": "Restaurar esta copia?",
    "All your current events will be replaced by the ones in the backup.": (
        "Todos os teus eventos actuais substituiranse polos da copia."
    ),
    "Restore": "Restaurar",
    "About": "Acerca de",
    "Fan-made tracker. Not affiliated with or endorsed by Bandai, Eiichiro Oda or Shueisha. "
    "Leader data from optcgapi.com.": (
        "Tracker feito por fans. Sen relación nin apoio de Bandai, Eiichiro Oda ou Shueisha. "
        "Datos de líderes de optcgapi.com."
    ),
    # rejected edits (events.repository.EventError), shown after "Could not save:"
    "event name is required": "o evento precisa un nome",
    "event name is longer than {max} characters": "o nome do evento pasa de {max} caracteres",
    "placement must be a whole number from 1 to {max}": "o posto ten que ser un número enteiro de 1 a {max}",
    "players must be a whole number from 1 to {max}": "os xogadores teñen que ser un número enteiro de 1 a {max}",
    "placement {placement} is past the {players} players": "o posto {placement} supera os {players} xogadores",
    "notes must be text": "as notas teñen que ser texto",
    "date must be a date": "a data ten que ser unha data",
    "unknown event type {key!r}": "tipo de evento descoñecido {key!r}",
    "unknown leader id {leader_id}": "líder descoñecido (id {leader_id})",
    "unknown event fields: {fields}": "campos de evento descoñecidos: {fields}",
    "unknown round fields: {fields}": "campos de rolda descoñecidos: {fields}",
    "result must be one of {results} or None": "o resultado ten que ser un de {results} ou ningún",
    "went_first must be true, false or None": "a quenda ten que ser si, non ou descoñecida",
    "event {event_id} not found": "non se atopou o evento {event_id}",
    "round {round_id} not found": "non se atopou a rolda {round_id}",
    # rounds: Swiss, top cut, byes; event standings and sets
    "1st place": "1.º posto",
    "2nd place": "2.º posto",
    "Top {n}": "Top {n}",
    "Outside the top {n}": "Fóra do top {n}",
    "Dropped": "Abandonado",
    "Not noted": "Sen anotar",
    "Swiss": "Suíza",
    "Bye": "Bye",
    "Byes": "Byes",
    "Automatic win": "Vitoria automática",
    "Add a bye": "Engadir un bye",
    "a bye has no games": "un bye non ten partidas",
    "a bye has no opponent": "un bye non ten rival",
    "a played round needs an opponent": "unha rolda xogada precisa un rival",
    "dropped must be true or false": "abandonado ten que ser si ou non",
    "kind must be one of {kinds}": "o tipo de rolda ten que ser un de {kinds}",
    "unknown set {code!r}": "colección descoñecida {code!r}",
    "event {event}, round {round}: a bye has no opponent, not {value!r}": (
        "evento {event}, rolda {round}: un bye non ten rival, non {value!r}"
    ),
    "event {event}, round {round}: unknown kind of round {value!r}": (
        "evento {event}, rolda {round}: tipo de rolda descoñecido {value!r}"
    ),
    "event {event}: dropped must be true/false/null, not {value!r}": (
        "evento {event}: abandonado ten que ser true/false/null, non {value!r}"
    ),
    "event {event}: the set must be a set code, not {value!r}": (
        "evento {event}: a colección ten que ser un código de colección, non {value!r}"
    ),
    # best of 3: games and who chose the turn order
    "Best of 1": "Ao mellor de 1",
    "Best of 3": "Ao mellor de 3",
    "Game {n}": "Partida {n}",
    "Games": "Partidas",
    "You": "Ti",
    "Opp": "Rival",
    "You chose turn": "Escolliches quenda",
    "They chose turn": "Escolleu o rival",
    "Who chose the turn order — tap to change": "Quen escolleu a quenda — toca para cambialo",
    "Who chose the turn order: the previous game's loser — tap to change": (
        "Quen escolleu a quenda: quen perdeu a partida anterior — toca para cambialo"
    ),
    "games {record}": "partidas {record}",
    "best_of must be 1 or 3": "ao mellor de ten que ser 1 ou 3",
    "chose_turn must be true, false or None": "quen escolleu a quenda ten que ser si, non ou descoñecido",
    "game {game_no} is not part of a best of {best_of}": (
        "a partida {game_no} non forma parte dun ao mellor de {best_of}"
    ),
    "unknown game fields: {fields}": "campos de partida descoñecidos: {fields}",
    "event {event}, round {round}: best of must be 1 or 3, not {value!r}": (
        "evento {event}, rolda {round}: ao mellor de ten que ser 1 ou 3, non {value!r}"
    ),
    "event {event}, round {round}: the games are not a list": (
        "evento {event}, rolda {round}: as partidas non son unha lista"
    ),
    "event {event}, round {round}: more games than a best of {best_of}": (
        "evento {event}, rolda {round}: máis partidas que un ao mellor de {best_of}"
    ),
    "event {event}, round {round}, game {game}: expected an object": (
        "evento {event}, rolda {round}, partida {game}: agardábase un obxecto"
    ),
    "event {event}, round {round}, game {game}: invalid result {value!r}": (
        "evento {event}, rolda {round}, partida {game}: resultado non válido {value!r}"
    ),
    "event {event}, round {round}, game {game}: the turn order must be true/false/null, not {value!r}": (
        "evento {event}, rolda {round}, partida {game}: a quenda ten que ser true/false/null, non {value!r}"
    ),
    "event {event}, round {round}, game {game}: who chose the turn order must be true/false/null, not {value!r}": (
        "evento {event}, rolda {round}, partida {game}: quen escolleu a quenda ten que ser true/false/null, non "
        "{value!r}"
    ),
    # invalid backup files (backup.json_backup.BackupError), shown after "Not a valid backup:"
    "not a JSON file: {error}": "non é un ficheiro JSON: {error}",
    "not a timtapper backup": "non é unha copia de timtapper",
    "unsupported backup version {version!r}": "versión de copia non compatible {version!r}",
    "the events are not a list": "os eventos non son unha lista",
    "event {event}: expected an object": "evento {event}: agardábase un obxecto",
    "event {event}: unknown event type {value!r}": "evento {event}: tipo de evento descoñecido {value!r}",
    "event {event}: invalid date {value!r}": "evento {event}: data non válida {value!r}",
    "event {event}: the rounds are not a list": "evento {event}: as roldas non son unha lista",
    "event {event}: the placement must be a whole number from 1 to {max}, not {value!r}": (
        "evento {event}: o posto ten que ser un número enteiro de 1 a {max}, non {value!r}"
    ),
    "event {event}: the players must be a whole number from 1 to {max}, not {value!r}": (
        "evento {event}: os xogadores teñen que ser un número enteiro de 1 a {max}, non {value!r}"
    ),
    "event {event}: placement {placement} is past the {players} players": (
        "evento {event}: o posto {placement} supera os {players} xogadores"
    ),
    "event {event}: the name must be text, not {value!r}": "evento {event}: o nome ten que ser texto, non {value!r}",
    "event {event}: the name is longer than {max} characters": "evento {event}: o nome pasa de {max} caracteres",
    "event {event}: the leader must be a leader code, not {value!r}": (
        "evento {event}: o líder ten que ser un código de líder, non {value!r}"
    ),
    "event {event}: the notes must be text, not {value!r}": (
        "evento {event}: as notas teñen que ser texto, non {value!r}"
    ),
    "event {event}, round {round}: expected an object": "evento {event}, rolda {round}: agardábase un obxecto",
    "event {event}, round {round}: invalid result {value!r}": (
        "evento {event}, rolda {round}: resultado non válido {value!r}"
    ),
    "event {event}, round {round}: the opponent must be a leader code, not {value!r}": (
        "evento {event}, rolda {round}: o rival ten que ser un código de líder, non {value!r}"
    ),
    "event {event}, round {round}: the turn order must be true/false/null, not {value!r}": (
        "evento {event}, rolda {round}: a quenda ten que ser true/false/null, non {value!r}"
    ),
    "event {event}, round {round}: the die roll must be true/false/null, not {value!r}": (
        "evento {event}, rolda {round}: a tirada de dado ten que ser true/false/null, non {value!r}"
    ),
    "event {event}, round {round}: the top cut flag must be true/false/null, not {value!r}": (
        "evento {event}, rolda {round}: o top cut ten que ser true/false/null, non {value!r}"
    ),
    "event {event}, round {round}: the notes must be text, not {value!r}": (
        "evento {event}, rolda {round}: as notas teñen que ser texto, non {value!r}"
    ),
}

EN = {key: key for key in ES}

TRANSLATIONS = {"en": EN, "es": ES, "gl": GL}
