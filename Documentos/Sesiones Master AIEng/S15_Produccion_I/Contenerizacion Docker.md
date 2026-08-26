# Contenerización con Docker

Creada: 1 de agosto de 2026 12:06
Módulo: M6. Despliegue y puesta en producción (https://app.notion.com/p/M6-Despliegue-y-puesta-en-producci-n-345ea9ca03c480d8a7a9e2275f20c2ef?pvs=21)
Sesión: S15. Puesta en producción de proyectos, arquitectura e infra (https://app.notion.com/p/S15-Puesta-en-producci-n-de-proyectos-arquitectura-e-infra-3afea9ca03c4806d8222e1ade89cf01f?pvs=21)

La frase se dice siempre con el mismo tono: a la defensiva. Un compañero se baja vuestro servicio IA, lo arranca y peta. "Pues en mi máquina funciona." Lo subís a un servidor de pruebas y peta. "En mi máquina funcionaba." Y suena a excusa, a "el problema es tuyo, no mío".

Pero si os paráis a escucharla, la frase no es una defensa. Es una confesión. Lo que estáis admitiendo, sin querer, es que aquello que hace que el sistema funcione **no está en el código**: está en vuestra máquina. En una versión de Python que instalasteis hace meses, en una librería que está ahí de casualidad, en una variable de entorno que exportasteis y olvidasteis. El sistema no funciona porque lo hayáis construido bien; funciona porque vuestra máquina, por acumulación, ha llegado a un estado que nadie sabría reproducir. Y un sistema que solo arranca en un sitio del mundo no está listo para producción.

En el artículo anterior decidisteis las fronteras y el contrato. Cada servicio ya sabe cuál es su responsabilidad y cómo habla con los demás. Pero cada uno sigue siendo, ahora mismo, "un proceso que arranco a mano con lo que tengo instalado". Este artículo trata de cerrar esa grieta: de convertir cada servicio en algo que arranca igual en cualquier parte. Que es, de nuevo, una promesa que quedó pendiente al principio: arranca igual siempre, en cualquier máquina.

## **Un contenedor es vuestra máquina, empaquetada**

Un contenedor resuelve la confesión de raíz: empaqueta la aplicación **con todo lo que necesita para ejecutarse** —el runtime, las librerías, la configuración— en una imagen reproducible. En vez de esperar que la máquina de destino tenga lo correcto instalado, os lleváis lo correcto dentro. La imagen que corre en vuestro portátil es, bit a bit, la que corre en staging y en producción. "En mi máquina funciona" deja de ser relevante porque la máquina deja de importar: lo que importa es la imagen.

Para un sistema con IA esto no es una comodidad, es casi una necesidad. El servicio IA depende de un ecosistema de Python especialmente sensible a las versiones: el cliente del proveedor de LLM, las librerías de embeddings, los drivers de la base de datos vectorial. Un cambio de versión menor en cualquiera de ellos puede cambiar el comportamiento o romper el arranque. Fijar todo eso dentro de una imagen elimina de golpe una de las mayores fuentes de "a mí me funcionaba".

La mecánica concreta —el `Dockerfile` del servicio IA, el del backend de negocio— la trabajáis en el ejercicio. Aquí interesa entender el *porqué* de un par de costumbres que parecen manías y no lo son. Se instalan las dependencias **antes** de copiar el código, para que Docker reutilice esa capa y no reinstale medio mundo cada vez que cambiáis una línea. Se parte de imágenes **slim**, porque una imagen más pequeña se despliega antes y ofrece menos superficie que atacar. Y se define un **healthcheck**, para que el sistema sepa si el contenedor está de verdad listo, no solo "arrancado". Son hábitos, y como todo hábito, valen por lo que evitan.

## **Una imagen se comparte; un secreto dentro se filtra**

Hay una regla en la contenerización que no es opcional y que conviene grabar antes que ninguna otra: **los secretos no van dentro de la imagen. Nunca.**

La razón es directa. Una imagen es un artefacto pensado para compartirse: se sube a un registro, se la baja un compañero, se despliega en varios sitios. Si horneáis la clave del proveedor de LLM dentro de la imagen, esa clave viaja con ella a todas partes: al registro, al portátil del compañero, al historial de capas de donde se puede extraer aunque luego la "borréis". Un secreto dentro de una imagen no es un secreto: es un secreto con pasaporte.

Lo correcto es que la imagen no sepa nada de las claves. Los secretos entran **en tiempo de ejecución**, como variables de entorno, en el momento en que el contenedor arranca en su entorno. La misma imagen, sin cambiar un bit, corre en dev con unas claves y en producción con otras. En el repositorio solo vive un `.env.example` con los nombres de las variables, nunca los valores.

![articulo-15-4-diagrama-imagen-secretos.png](https://media1-production-mightynetworks.imgix.net/asset/9e35f89a-2142-4c58-9730-697d9fe13aae/articulo-15-4-diagrama-imagen-secretos.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: qué empaqueta una imagen —runtime, librerías, código— y qué no. Los secretos se inyectan al arrancar, no se hornean dentro, porque la imagen es un artefacto que se comparte.*

Esta es la costumbre que más se salta la gente "para ir más rápido", metiendo la clave en el `Dockerfile` o en el código. Va más rápido exactamente hasta el día en que esa imagen acaba en un sitio donde no debía, con la clave dentro. Ese día se paga con creces todo el tiempo que se ahorró.

## **docker-compose: el sistema entero con un comando**

Un contenedor por servicio resuelve cada pieza por separado, pero vuestro sistema son cuatro piezas que tienen que arrancar juntas y hablarse: el backend de negocio, el servicio IA, la base de datos relacional y la vectorial. Orquestar eso a mano sería volver al ritual de las cuatro terminales. `docker-compose` lo sustituye por un solo fichero y un solo comando.

Dos ideas que hacen que ese fichero esté bien montado, y que son la traducción operativa de todo lo que llevamos dicho:

**Solo el backend de negocio publica un puerto al host.** Es la frontera del primer artículo, hecha configuración. Dentro de la red interna de compose, los servicios se encuentran por su nombre (`ai-service`, `vector-db`), no por `localhost`. El servicio IA y las bases de datos no exponen puerto: son inalcanzables desde fuera, alcanzables solo desde dentro. Si os equivocáis y le ponéis un puerto al servicio IA, acabáis de abrir a internet la pieza que custodia la clave del LLM.

**El arranque tiene orden.** No sirve de nada que el servicio IA arranque antes que su base de datos vectorial: fallaría al primer intento. Con `depends_on` y healthchecks, cada servicio espera a que sus dependencias estén *sanas*, no solo *lanzadas*. Es la diferencia entre "el proceso existe" y "el proceso está listo para trabajar".

![articulo-15-4-diagrama-compose.png](https://media1-production-mightynetworks.imgix.net/asset/ba4c478c-ce01-4e2c-accb-3099d19722b1/articulo-15-4-diagrama-compose.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: docker-compose levanta los cuatro contenedores en una red interna. Solo el backend de negocio publica un puerto al host; los secretos se inyectan al arrancar desde el entorno.*

El resultado es que todo el sistema arranca —y vuelve a arrancar— con `docker compose up`, en cualquier máquina, en el mismo orden y con el mismo comportamiento. El ritual desaparece.

## **Cuándo el contenedor no os salva**

Conviene no confundir lo que un contenedor arregla con lo que no. Un contenedor os da **reproducibilidad, no corrección**. Si vuestra aplicación tiene un bug, la vais a poder reproducir perfectamente en todas partes: el contenedor no arregla el código, solo garantiza que el mismo código se comporta igual en todos lados. Está bien tenerlo claro para no esperar magia.

Dos trampas concretas que el contenedor no evita por vosotros. La primera, los datos: un contenedor es efímero por diseño, así que lo que se guarde dentro desaparece al recrearlo. La base de datos vectorial, que os costó tiempo y tokens poblar, tiene que vivir en un volumen persistente; si no, un redeploy la borra y os quedáis sin el conocimiento del sistema. La segunda, ya lo dijimos, los secretos: la disciplina de no hornearlos sigue siendo vuestra, el contenedor no la impone.

## **Lo que queda por decidir**

Con esto, cada servicio ha dejado de ser "un proceso que arranco con lo que tengo" para convertirse en una imagen reproducible, y el sistema entero se levanta con un comando. La confesión ya no aplica: no importa vuestra máquina, importa la imagen.

Pero una imagen en vuestro portátil todavía no es un sistema desplegado. Falta construir esa imagen de forma repetible cada vez que cambia el código, moverla entre los entornos —dev, staging, producción— sin sorpresas, e inyectar en cada uno los secretos correctos. Es decir: falta el pipeline.

Y ahí aparece una regla que descoloca a casi todo el mundo la primera vez que la oye. Cuando montéis la integración continua para este sistema, lo último que querréis es que vuestros tests llamen al modelo de verdad. Por qué esa aparente contradicción —tener un sistema de IA y pedirle al pipeline que no toque la IA— es el siguiente tramo del camino.