# Memoria del proyecto: estudio de eventos

## Lecciones

1. **Rangos con borde explícito.** Al definir ventanas (vigencia de 24 velas, dedup de 8 velas, pivotes de n=3), escribí el rango con los dos bordes y su inclusión: "j en [i-23, i]", "bloquea i+1..i+7". Un "hasta 8 velas después" admite dos lecturas y el código eligió una sin que nadie lo decidiera.
2. **Registros con todas las celdas, incluso en cero.** Un registro que declara N celdas tiene que tener N filas. Si el script omite las celdas con cero eventos, el registro queda incompleto y no se nota hasta que un revisor recalcula.
3. **La descripción del PR no afirma lo que no está hecho.** Antes de escribir "hace X", verificá que X existe en el código y en los tests. Si está pendiente, decí "pendiente". En el PR #9 se afirmó que el bootstrap medía la diferencia contra el azar, y todavía no se implementó.
