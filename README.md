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

      * wget http://postgis.net/stuff/postgis-2.1.9dev.tar.gz
      * tar -xvzf postgis-2.1.9dev.tar.gz 
      * cd postgis-2.1.9dev
      * ./configure
      * make
      * make install

 3. Install the following libraries in order for GEOS to work in with the database.

     - sudo apt-get install binutils libproj-dev gdal-bin

 4. Install lib-curl for pycurl to work

     - sudo apt-get install libcurl4-gnutls-dev librtmp-dev

 5. Install redis server using instructions in the following link.

     - https://www.digitalocean.com/community/tutorials/how-to-install-and-use-redis

 6. Install virtualenv system wide:

     - sudo apt-get install python-virtualenv

 ### Database configuration ### 

  1. Create assets_8208 database using
     -CREATE DATABASE assets_8208
  2. Create postgis extension for database
      *  Connect to your newly created database and issue the following command:
        *  CREATE EXTENSION postgis

  ### Deployment instructions ###
  
 
 1. Restore db from kens-pgsql-002-prod server.
    
    Make a dump file from the database  

     -sudo -u postgres pg_dump -p 5440 -O -Fc assets_8208 <path to your dump file>
     
    Save your dump file in a suitable location where you can access it when restoring the database.

    This assumes that you are not using a cluster.

    -> sudo -u postgres pg_restore -d assets_8208 <path to your dump file>

 2. Delete all djcelery and south tables.
 
 3. Clone the project into a suitable location.

 4. Create a virtual environment inside the root of the project folder.
     - virtualenv <name of your virtual environment>

 5. Activate your virtual environment using:
    - source <name of virtual environment>/bin/activate

 6. Install all dependencies using:

    - pip install -r requirements.txt

 7. Update your settings file appropriately in order to connect to the database.

 8. Export DEBUG environment variable using:
     - export DEBUG=True 

 8. Run the test server and point web browser to the address of the application.

### Contribution guidelines ###

* Writing tests
* Code review
* Other guidelines

### Who do I talk to? ###

* Repo owner or admin
* Other community or team contact