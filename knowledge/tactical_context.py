"""Read-only conceptual interpretation. Sources located are not verified quotations."""
from copy import deepcopy

CONCEPTS={
 'connections':{
  'title':'Cómo se conecta el equipo para avanzar',
  'reading':'Las conexiones permiten estudiar qué jugadores enlazan las zonas de inicio y llegada. Una asociación frecuente puede sostener la circulación; para valorar su aportación también hay que revisar su continuidad y desenlace.',
  'alternative':'La frecuencia puede depender del rival, del marcador, de los minutos compartidos o del rol de cada jugador.',
  'limit':'Una red de pases representa intervenciones con balón. No demuestra formación simultánea, cohesión psicológica ni instrucciones del entrenador.',
  'question':'¿Qué conexiones aparecen cuando avanzamos y qué cambia en las secuencias que se interrumpen?','engine':'CTS descriptivo / complemento relacional de OC'},
 'pressure':{
  'title':'Conservar y encontrar continuidad ante presión',
  'reading':'Completar el pase es una parte de la respuesta. La siguiente acción ayuda a distinguir conservación, avance y pérdida. La atracción deliberada de presión es una hipótesis que requiere revisar la secuencia y su contexto.',
  'alternative':'Pocos pases bajo presión pueden reflejar poca presión rival, otras rutas de salida o cobertura incompleta; no constituyen por sí solos una debilidad.',
  'limit':'under_pressure describe una condición de la acción. No demuestra que el equipo haya provocado esa presión ni que el receptor estuviera libre.',
  'question':'¿El receptor puede dar continuidad al ataque y en qué casos la siguiente acción vuelve a quedar comprometida?','engine':'PCI/HPS como contexto y respuesta; sin recalcular índices'},
 'interior':{
  'title':'Dar sentido a las recepciones interiores',
  'reading':'Llegar a un pasillo interior importa por la acción que permite después. Conviene revisar quién recibe, de dónde viene el balón y si la continuidad acerca al equipo al área.',
  'alternative':'La misma zona puede servir para progresar, conservar o devolver el balón, según el contexto.',
  'limit':'El destino geométrico del pase no demuestra recepción entre líneas, desmarque, falso nueve o arrastre de un defensor.',
  'question':'¿Qué continuaciones se repiten tras recibir en esta zona y cuáles terminan en una llegada?','engine':'Tactical Framework / secuencias observadas'},
 'arrival':{
  'title':'De la llegada a una oportunidad de remate',
  'reading':'La frecuencia de llegada y su desenlace describen aspectos distintos. Comparar secuencias con entrada al área, con remate y sin remate ayuda a formular preguntas sobre la continuidad ofensiva.',
  'alternative':'Una ruta puede acumular acciones por volumen de posesión sin ser la más productiva; la muestra y el rival condicionan la comparación.',
  'limit':'xG y OBV disponibles son estimaciones del proveedor. La asociación entre una ruta y un remate no demuestra causalidad ni que fuese la mejor opción disponible.',
  'question':'¿Qué cambia entre las llegadas que permiten rematar y las que terminan sin una ocasión?','engine':'Capa de valor y secuencias; PMDS solo como guía de preguntas'},
 'defense':{
  'title':'Dónde interviene la defensa y qué sucede después',
  'reading':'La localización de las intervenciones ayuda a describir dónde participa el equipo cuando defiende. El contexto del ataque rival y la continuidad posterior permiten interpretar esas acciones con mayor precisión.',
  'alternative':'Una concentración de acciones puede responder a la iniciativa rival o al estado del partido, además de a una preferencia táctica propia.',
  'limit':'Las ubicaciones de eventos no son la altura de la línea defensiva. Los fueras de juego registrados no prueban una trampa deliberada ni coordinación entre centrales.',
  'question':'¿Qué intervenciones preceden a una recuperación y qué sucede en las posesiones rivales que consiguen continuar?','engine':'Defensa organizada / evidencia por posesión'},
}

def context_for(concept):
    """Neutral EFOS tactical reading, without provenance metadata in the product."""
    item=deepcopy(CONCEPTS[concept])
    item['status']='MARCO_CONCEPTUAL; no es un hallazgo calculado'
    return item

def enrich_claims(claims):
    """Add separate explanation; preserve every original field, number and identifier."""
    out=deepcopy(claims)
    for claim in out:
        ident=str(claim.get('id',''))
        concept=('pressure' if 'pressure_attraction' in ident else
                 'interior' if 'progression' in ident else
                 'arrival' if 'value' in ident or 'offensive' in ident else 'defense')
        claim['conceptual_context']=context_for(concept)
    return out
