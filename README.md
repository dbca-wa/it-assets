# README #

This README would normally document whatever steps are necessary to get your application up and running.

### What is this repository for? ###

* Quick summary
  This is the revised version of the assets app that has been modified to use django 1.8 from its current django 1.4.
* Version
* [Learn Markdown](https://bitbucket.org/tutorials/markdowndemo)

### How do I get set up? ###


 ### Configuration ###

   These instructions assume that the app is being deployed to ubuntu 14.04.
 
 1. Install postgres database 9.3 

     -Follow the instructions in the following link to create the database. 
         https://www.digitalocean.com/community/tutorials/how-to-install-and-use-postgresql-on-ubuntu-14-04

 2. Install postgis. 

      -wget http://postgis.net/stuff/postgis-2.1.9dev.tar.gz
      -tar -xvzf postgis-2.1.9dev.tar.gz 
      -cd postgis-2.1.9dev
      -./configure
      -make
      -make install

 3. Install the following libraries in order for GEOS to work in with the database.

     - sudo apt-get install binutils libproj-dev gdal-bin

 4. Install lib-curl for pycurl to work

     - sudo apt-get install libcurl4-gnutls-dev librtmp-dev

 5. Install redis server using instructions in the following link.

     - https://www.digitalocean.com/community/tutorials/how-to-install-and-use-redis
 
 ### Database configuration ### 

  1. Create assets_8208 database using
     -CREATE DATABASE assets_8208
  2. Create postgis extension for database
      - Connect to your newly created database and issue the following command:
        - CREATE EXTENSION postgis

  ### Deployment instructions ###
  
 
 1. Restore db from kens-pgsql-002-prod server.
    
    Make a dump file from the database  

     -sudo -u postgres pg_dump -p 5440 -O -Fc assets_8208 <path to your dump file>
     
    Save your dump file in a suitable location where you can access it when restoring the database.

    This assumes that you are not using a cluster.

    -> sudo -u postgres pg_restore -d assets_8208 <path to your dump file>

 2. Update your settings file appropriately in order to connect to the database.

 3. Delete all djcelery and south tables.

 4. Migrate --fake-intial in manage.py

 5. syncdb using manage.py
 
 6. Runserver and point web browser to the address of the application.

### Contribution guidelines ###

* Writing tests
* Code review
* Other guidelines

### Who do I talk to? ###

* Repo owner or admin
* Other community or team contact