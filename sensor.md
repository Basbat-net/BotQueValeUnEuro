El ToF básicamente el sensor emite luz infrarroja esa luz rebota en un objeto y vuelve, midiendo cuánto tarda en regresar, el sensor calcula la distancia. 
Dentro de los ToF hay dos tipos interesantes.

##TOF-------------
El primero es el ToF puntual. Este sensor mira una zona pequeña de unos 1,2 a 1,3m y con 100medidas por segundo cn una actualizacion de 10ms. funciona muy bien para cajas bien colocadas para
detección frontal de una caja (para pinzas) o para detectar paredes. pero generalmente es para corto alcance
ToF multipuntual funciona de la misma manera que uno puntual pero funciona de forma matricial 8x8 de modo que
podremos localizar su centro mediante depth map similar a como se hace en robotica, ayuda a calibrar al robot
con objetos que no estan directamente en el frontal
Tof Luna es bueno para distancias que ya sabes sobre un objeto que esta enfrente, con una paroximacion muy recta
 el problema es con el desplazamiento de las cajas

VL53L0X	ToF puntual	~3–10 € 	Antiguo, poco alcance, solo una distancia	Pruebas simples
VL53L1X	ToF puntual	~15 €  configurable	No sabe izquierda/derecha, solo mide una zona	Distancia a pared
VL53L4CD	ToF puntual corto alcance	~4–5 € chip / ~10–20 € módulo	Rápido, hasta ~100 Hz, bueno a corta distancia	No genera mapa, solo una distancia	Aproximación final
VL53L8CX	ToF multizona 8×8	~7,8 € chip / ~22–30 € módulo	64 zonas, hasta ~4 m, I²C/SPI, mapa de profundidad	No ve 360°, resolución muy baja comparada con cámara	Cajas y centrado

TF-Luna	LiDAR/ToF puntual de haz estrecho	~22–30 €	Hasta 8 m, hasta 250 Hz, haz estrecho, UART/I²C	No sabe posición lateral
TFmini-S	LiDAR puntual	~42 €	Hasta 12 m, muy rápido, UART/I²C	Mucho alcance innecesario para Eurobot, solo un punto

 ##Ultrasonido
 El problema de los ultrasonidos es el cono puede detectar cosas que esta en su cono de emision pero no sabe que
 esta midiendo solo devuelve una aproximacion, tb tiene problemas de interferencia de otros ultrasonidos que pueden
 alterar las mediciones

HC-SR04	Ultrasonido	~2–5 €	Poco preciso espacialmente, ecos, interferencias
DFRobot URM09	Ultrasonido	~$12,90 / ~10–15 €	2 cm–5 m, hasta 50 Hz, compensación de temperatura, I²C	Sigue teniendo cono acústico, no sabe dónde está el objeto

 ##LiDAR 
 el lidar funciona como un ToF pero con girando el laser presenta puntos con angulos y distancias permitiendo saber elementos dentro del mapa tanta simas como robots
 como cajas, su version LiDAR360 mide los 360grados

YDLIDAR T-mini Plus	LiDAR 2D 360° ToF	~69–90 €	360°, 0,05–12 m, 4000 puntos/s, ROS/ROS2, pequeño	Solo ve un plano horizontal	
RPLIDAR C1	LiDAR 2D 360° dToF	~80–100 €	360°, 12 m, ~5000 puntos/s, ROS/ROS2, buen ecosistema	Solo un plano 2D
RPLIDAR A1	LiDAR 2D 360°	~90–110 €	Muy conocido, mucha documentación	Tecnología más antigua, grande comparado con opciones actuales	
YDLIDAR HP60C	Cámara de profundidad	~177 €	Profundidad 3D, FOV grande, USB	Mucho más caro y pesado computacionalmente

 Se requerira de camara para aportar mas informacion para que los lidar y tof puedan acceder de manera mas directa a los obstaculos
 


