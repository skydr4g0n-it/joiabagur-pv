# CI/CD con tokens

Creada: 1 de agosto de 2026 12:06
Módulo: M6. Despliegue y puesta en producción (https://app.notion.com/p/M6-Despliegue-y-puesta-en-producci-n-345ea9ca03c480d8a7a9e2275f20c2ef?pvs=21)
Sesión: S15. Puesta en producción de proyectos, arquitectura e infra (https://app.notion.com/p/S15-Puesta-en-producci-n-de-proyectos-arquitectura-e-infra-3afea9ca03c4806d8222e1ade89cf01f?pvs=21)

Tenéis las imágenes del artículo anterior: cada servicio empaquetado, reproducible, arrancable en cualquier parte. Pero una imagen en vuestro portátil todavía no es un sistema desplegado. Para cruzar esa distancia hace falta un pipeline: algo que, cada vez que cambia el código, construya las imágenes, pase los tests y las lleve por dev, staging y producción sin sorpresas.

Y en el momento en que os sentáis a escribir esos tests, chocáis con una regla que suena a contradicción: **la integración continua de vuestro sistema de IA no debe llamar a la IA.**

Léelo otra vez, porque es raro. Habéis construido un sistema cuyo corazón es un modelo de lenguaje, y lo primero que os digo es que el pipeline no lo toque. Parece absurdo. No lo es. Es, simplemente, que hay dos cosas que casi todo el mundo confunde —testear vuestro código y evaluar el modelo— y que el pipeline solo debe hacer una de ellas.

## **Por qué el modelo no puede entrar en CI**

Un test de CI tiene un trabajo: dar siempre la misma respuesta ante el mismo código. Verde si el código está bien, rojo si está mal, y —esto es lo importante— siempre lo mismo mientras el código no cambie. Sobre esa fiabilidad se construye todo lo demás: si el pipeline está verde, se despliega; si está rojo, se para.

Una llamada al modelo rompe esa propiedad por tres sitios a la vez.

Rompe el **determinismo**. El mismo prompt puede dar respuestas distintas en dos ejecuciones seguidas. Un test que a veces pasa y a veces no, sin que hayáis tocado nada, no es un test: es una moneda al aire con aspecto de test. Y lo peor que le puede pasar a un equipo es un pipeline que falla de vez en cuando "sin motivo", porque enseña a la gente a ignorar los rojos —y el día que el rojo es de verdad, ya nadie lo mira.

Rompe el **coste**. Cada ejecución de CI, en cada push, en cada rama, gastaría tokens de verdad. Multiplicad eso por un equipo trabajando y tenéis una factura que crece con la actividad de desarrollo, no con el uso del producto. Estáis pagando por tener miedo a hacer commit.

Y rompe la **velocidad**. Una llamada al modelo tarda segundos; un test unitario debería tardar milisegundos. Un CI que llama al modelo es un CI lento, y un CI lento es un CI que la gente evita.

Determinista, barato y rápido: eso es lo que CI necesita. El modelo no es ninguna de las tres.

## **Mockear el modelo es testear lo vuestro, no lo suyo**

Aquí está el giro que deshace la aparente contradicción. Cuando decís "no llaméis al modelo en CI", no estáis renunciando a testear. Estáis distinguiendo *qué* testeáis.

No es trabajo de CI comprobar si el modelo estima bien. Eso —si la calidad de las respuestas es buena, si alucina, si acierta— es **evaluación**, y es un mundo aparte que se trabaja en la siguiente sesión, con sus golden test sets y sus métricas. Evaluar el modelo y testear vuestro código son actividades distintas, con herramientas distintas y ritmos distintos.

Lo que CI sí testea es **todo lo vuestro que rodea al modelo**: que el prompt se construye con los datos correctos, que el output del modelo se parsea bien, que un JSON malformado no revienta el servicio, que un `503` de la base de datos vectorial se maneja como toca, que el contrato `/v1/` sigue devolviendo lo que el backend de negocio espera. Nada de eso necesita al modelo real. Solo necesita una respuesta *fija* en su lugar.

Eso es mockear: sustituir la llamada al modelo por una respuesta predecible y testear toda la lógica que la envuelve.

```python
# ai-service/tests/test_estimation.py
from unittest.mock import patch

def test_estimate_parses_model_output():
    fake_completion = '{"estimate_points": 5, "confidence": 0.8, "sources": ["task-42"]}'
    with patch("app.llm.client.complete", return_value=fake_completion):
        result = estimation_pipeline.run(EstimateRequest(
            task_description="Add OAuth login",
            project_id="proj-1",
        ))
    assert result.estimate_points == 5
    assert 0 <= result.confidence <= 1
```

Fijaos en lo que este test comprueba: no si "5 puntos" es una buena estimación —eso no le toca—, sino que vuestro código toma la respuesta del modelo y la convierte correctamente en un `EstimateResponse` válido. Es determinista, es instantáneo y no cuesta un céntimo. A esto se le suman los **contract tests**, que verifican que el servicio IA respeta el contrato que el backend de negocio espera, para que la frontera no se rompa en silencio al evolucionar una de las dos capas.

## **El smoke test es donde el modelo sí entra**

Entonces, ¿el modelo real no se prueba nunca en el pipeline? Sí, pero en otro momento y con otra intención.

Después de desplegar —no en cada commit— se ejecuta un **smoke test**: una comprobación mínima de que el sistema desplegado está vivo y responde con la forma correcta. Que `/health` contesta, que una estimación de prueba recorre el flujo completo y devuelve algo con la estructura esperada. Este sí toca el sistema real, modelo incluido, porque su pregunta no es "¿el código está bien?" —eso ya lo respondió CI— sino "¿el despliegue de verdad funciona de punta a punta?".

La distinción es la clave de todo el capítulo: **CI es determinista, mockeado y corre en cada commit; el smoke test es real, escaso y corre después de desplegar.** No compiten; cubren cosas distintas. Confundirlos —meter el modelo en CI o fiar toda la confianza al smoke test— es lo que produce pipelines lentos, caros e inútiles.

![articulo-15-5-diagrama-pipeline.png](https://media1-production-mightynetworks.imgix.net/asset/ed874cf6-51e3-4d78-8133-687499c746ad/articulo-15-5-diagrama-pipeline.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: el recorrido del pipeline. En CI el modelo está mockeado (determinista, en cada commit); solo el smoke test posterior al despliegue toca el sistema real.*

## **Una imagen, tres entornos**

Queda la otra mitad del pipeline: mover esas imágenes por los entornos. Trabajáis con tres —dev, staging y producción— y la regla que los gobierna es sencilla y estricta: **la misma imagen corre en los tres; lo único que cambia es la configuración.**

Es el principio *12-factor*. El artefacto que construís una vez —la imagen— es idéntico en todas partes. Lo que cambia entre dev y producción no es el código: son las variables de entorno. La clave del LLM, las URLs de las bases de datos, el nivel de logging. Todo eso vive en el entorno, no en la imagen, exactamente por la misma razón que vimos con los secretos: para que el mismo artefacto sea reproducible y solo cambie el contexto en el que corre.

![articulo-15-5-diagrama-una-imagen-tres-entornos.png](https://media1-production-mightynetworks.imgix.net/asset/7fb5d7fa-978c-4485-845b-fdc5ddb1b86c/articulo-15-5-diagrama-una-imagen-tres-entornos.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: una única imagen construida en el pipeline se despliega en dev, staging y producción. El artefacto es el mismo; cada entorno inyecta su propia configuración y sus propios secretos.*

Y eso ata el último cabo sobre los secretos. En el pipeline, las claves no viven en el repositorio ni aparecen en los logs de la ejecución: se guardan en el gestor de secretos de la plataforma de CI/CD y del proveedor cloud, y se inyectan como variables de entorno en el momento del despliegue. En el repositorio solo vive `.env.example`, con los nombres y sin los valores. Un secreto que aparece en un log de pipeline es un secreto quemado, igual que uno horneado en una imagen.

## **Lo que queda por decidir**

Recapitulando: el pipeline construye las imágenes, las testea sin tocar el modelo —porque testear vuestro código y evaluar el modelo son cosas distintas—, comprueba con un smoke test que el despliegue vive, y mueve el mismo artefacto por tres entornos cambiando solo la configuración. Determinista donde tiene que serlo, real solo donde aporta.

Pero hasta ahora "desplegar" ha sido una palabra que hemos usado sin abrirla. El pipeline sabe *construir* y *mover* imágenes; falta decidir *a dónde* y *cómo*. Y ese último tramo es donde todo lo anterior se materializa sobre infraestructura de verdad: elegir dónde corre cada pieza, y —sobre todo— llevar la frontera público/privado del primer artículo a redes reales, donde equivocarse de qué se expone ya no es un puerto de más en un `docker-compose`, sino la clave del LLM abierta a internet.

Desplegar en cloud, y decidir qué mira a la calle y qué no, es la última decisión del camino.