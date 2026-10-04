# Memoria del proyecto: estudio de eventos

## Lecciones

1. **Rangos con borde explícito.** Al definir ventanas (vigencia de 24 velas, dedup de 8 velas, pivotes de n=3), escribí el rango con los dos bordes y su inclusión: "j en [i-23, i]", "bloquea i+1..i+7". Un "hasta 8 velas después" admite dos lecturas y el código eligió una sin que nadie lo decidiera.
2. **Registros con todas las celdas, incluso en cero.** Un registro que declara N celdas tiene que tener N filas. Si el script omite las celdas con cero eventos, el registro queda incompleto y no se nota hasta que un revisor recalcula.
3. **La descripción del PR no afirma lo que no está hecho.** Antes de escribir "hace X", verificá que X existe en el código y en los tests. Si está pendiente, decí "pendiente". En el PR #9 se afirmó que el bootstrap medía la diferencia contra el azar, y todavía no se implementó.
4. **Cuando la spec fija un número o una frase es ambigua, se contrasta el código y se pregunta antes de implementar.** Si la spec dice 76 celdas, el código tiene que producir 76 celdas agregadas; si una frase admite dos lecturas (relleno, dedup, unidad de celda), la duda va al dueño de la spec antes de codificarla. En este estudio pasó con el relleno estricto, la deduplicación y la unidad de celda, y en cada caso la implementación inicial se corrigió después.
5. **Antes de implementar una definición (celda, N, exclusión), contrastarla con el número declarado en la spec; si no coincide, se pregunta y se corrige la definición, no el registro.** Ya pasó con el relleno, la deduplicación, la celda y el costo: en cada caso la definición inicial no coincidía con las 76 celdas o con la regla de la spec, y se corrigió la definición.
