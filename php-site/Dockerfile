FROM php:8.4-apache@sha256:be1326658a7d36dba6be79a71212d6ff9c5f854335b8ba77d714da1852c1b2ea
RUN docker-php-ext-install pdo_mysql
COPY docker/site.conf /etc/apache2/sites-available/000-default.conf
COPY docker/php.ini /usr/local/etc/php/conf.d/ialogs.ini
WORKDIR /var/www/site
COPY . .
EXPOSE 80
