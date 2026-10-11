#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.159067
Revised: 2026/10/11 17:20:12.966075

Translation tables, keyed by the English source string exactly as written
in the code. English (EN) is built from the ES key set so it stays a
first-class table. When adding or renaming a user-facing string, add it to
EVERY table — tests/test_i18n.py fails on any missing or stale key.
"""

ES = {
    # navigation / screens
    "Events": "Eventos",
    "Event": "Evento",
    "Stats": "Estadísticas",
    "Settings": "Ajustes",
    "Press back again to exit": "Pulsa atrás otra vez para salir",
    "That event no longer exists": "Ese evento ya no existe",
    # event types
    "Testing": "Testeo",
    "Locals": "Locales",
    "Regional": "Regional",
    "National": "Nacional",
    "Online": "Online",
    "Other": "Otro",
    # events list
    "New event": "Nuevo evento",
    "No events yet": "Aún no hay eventos",
    "Log a testing session, a locals or a major — then add each round as you play it.": (
        "Registra un testeo, un torneo local o un major — y añade cada ronda mientras la juegas."
    ),
    "No leader chosen": "Sin líder elegido",
    "1 round": "1 ronda",
    "{n} rounds": "{n} rondas",
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
    "Draw": "Empate",
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
    "Delete": "Borrar",
    "Cancel": "Cancelar",
    "Delete event": "Borrar evento",
    "Delete this event?": "¿Borrar este evento?",
    "The event and all its rounds will be removed. This can't be undone.": (
        "Se eliminarán el evento y todas sus rondas. No se puede deshacer."
    ),
    "Event deleted": "Evento borrado",
    "Could not save: {error}": "No se pudo guardar: {error}",
    # leader picker
    "Search name, code or color": "Busca por nombre, código o color",
    "No leader matches": "Ningún líder coincide",
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
    "+{n} more": "+{n} más",
    "No rounds logged yet": "Aún no hay rondas registradas",
    "Opponent": "Rival",
    "W-L": "V-D",
    "Win %": "% Vict.",
    "Tracked with timtapper · One Piece TCG": "Registrado con timtapper · One Piece TCG",
    "Could not create the image ({error})": "No se pudo crear la imagen ({error})",
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
}

GL = {
    # navigation / screens
    "Events": "Eventos",
    "Event": "Evento",
    "Stats": "Estatísticas",
    "Settings": "Axustes",
    "Press back again to exit": "Preme atrás outra vez para saír",
    "That event no longer exists": "Ese evento xa non existe",
    # event types
    "Testing": "Testeo",
    "Locals": "Locais",
    "Regional": "Rexional",
    "National": "Nacional",
    "Online": "En liña",
    "Other": "Outro",
    # events list
    "New event": "Novo evento",
    "No events yet": "Aínda non hai eventos",
    "Log a testing session, a locals or a major — then add each round as you play it.": (
        "Rexistra un testeo, un torneo local ou un major — e engade cada rolda mentres a xogas."
    ),
    "No leader chosen": "Sen líder escollido",
    "1 round": "1 rolda",
    "{n} rounds": "{n} roldas",
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
    "Draw": "Empate",
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
    "Delete": "Borrar",
    "Cancel": "Cancelar",
    "Delete event": "Borrar evento",
    "Delete this event?": "Borrar este evento?",
    "The event and all its rounds will be removed. This can't be undone.": (
        "Eliminaranse o evento e todas as súas roldas. Non se pode desfacer."
    ),
    "Event deleted": "Evento borrado",
    "Could not save: {error}": "Non se puido gardar: {error}",
    # leader picker
    "Search name, code or color": "Busca por nome, código ou cor",
    "No leader matches": "Ningún líder coincide",
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
    "+{n} more": "+{n} máis",
    "No rounds logged yet": "Aínda non hai roldas rexistradas",
    "Opponent": "Rival",
    "W-L": "V-D",
    "Win %": "% Vit.",
    "Tracked with timtapper · One Piece TCG": "Rexistrado con timtapper · One Piece TCG",
    "Could not create the image ({error})": "Non se puido crear a imaxe ({error})",
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
}

EN = {key: key for key in ES}

TRANSLATIONS = {"en": EN, "es": ES, "gl": GL}
