/*Inicialidazor de la base de datos, la crea si no existe y concede permisos al usuario*/

CREATE DATABASE IF NOT EXISTS `eshop`;
GRANT ALL ON `eshop`.* TO 'eshop_user'@'%' IDENTIFIED BY 'eshop_pass';
