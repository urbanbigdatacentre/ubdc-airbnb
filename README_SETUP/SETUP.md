### Required Software

- conda python
- docker
- QGIS
- git

### Optional

- Sublime editor (or a similar)
- A postgresql viewer (I am using dbreaver)


### Design Philosophy

### Contents

#### Initial Setup

1. install Docker
1. install minicoda
1. clone airbnb project `git clone ...`
1. in the cloned folder edit the .env file. Fill the proxy if needed. The rest should work for now
1. open miniconda console
1. navigate in the cloned directory with the console
1. create a python environment with conda 'conda env create -f environment.yml'
1. open 3 conda consoles, and activate the venv made in the previous step. Navigate in the project folder.
1. using the first console, activate the stack (database broker and worker)
   docker-compose `docker-compose up db rabbit worker`
    1. the database should be up and running, default username: postgres password: airbnb Setup
1. Using the 2nd console, navigate at the `../src` folder (the one wthat has the manage.py)
1. Run `python .\manage.py migrate` This will create the necessary tables in the database
1. Run python `.\manage.py import_world_mask` to import the world mask. The world mask limits scanning for listings in
   grids intersecting with it.
    1. The subroutine will download the GADM global file, and then import it. The operation could take massive amounts
       of time, so if you want to speed the process up, you could tell it to only import one country:
       eg `python .\manage.py import_world_mask --only-iso GBR`

The system now is ready to add an Area of Interest

#### Adding an AOI

1. open QGIS.
1. create a postgis connection
1. add the app_aoishape layer (that's the one where you are going to draw our aoi)
1. (optional) add the app_worldshape, app_airbrlistings and app_ubdcgrid layers for reference later. the app_worldshape
   is the mask layer. You can use it for an approximation of where your AOI is
1. Enable editing the app_aoishape layer.
    1. Draw a polygon. That's where there system will look for listings. Choose a place that is reasonable. The system
       is able to scan the whole world, but airbnb before that happens.
    1. As attributes, the layer contains some flags. Like collect_calendars and etc. Make sure all are enabled for this
       demonstration.
    1. Save your AOI. Make a note of your polygons ID. If it's the very first one drawn, the id should be 1
1. From the console, through the anaconda enviroment run the command `python .\manage.py generate_grid 1` (replace the
   number one with the actual ID taken form the polygon made with qgis)
1. (optional) AFter the command completes, you can visualise the grids in qgis. It's the app_ubdcgrids layer
1. These grids are generic quadtrees dividing the world. They're supposed to contain a manageable amount of listings for
   the system to work with. That managable amount is chosen abstractivly to be 50. issuing the
   command `python .\manage.py send_task update-grid` will create a task that will see that each grid to be queried
   through airbnb for an estimation of how many listings contains. If it is more than 50, it will be replaced with its
   children.

#### Adding listings

After all jobs that the task had generated finish, you can start querying airbnb for the actual listing locations.

1. `python .\manageypy send_task discover-listings`  
   The above command will send an initiator task, that in turn will generate requests, that will be carried through
   airbnb's search service The coming response will be parsed to extract the coordinates and generate points, that can
   be seen at the __app_airbnblistings__ layer on qgis

#### Collecting Calendars

1. `python .\manageypy send_task get-calendars`  
   In the same maner as above, tasks will be generated to collect the calendars of all the known listings in all the
   activated AOIs. The calendars are saved in the database in the __app_airbnbresponse__ master table:
   ```sql 
   select * from app_airbnbresponse where type = 'CAL'
   ```

   From time to time, when the frequency of calendar requests is too high, airbnb logic is to ban your ip for a certain
   amount of time. If that happens the task will be deferred to run again later.

#### Collecting ListingDetails

1. `python .\manageypy send_task get-listing-details`
   in the __app_airbnbresponse__ master table:
   ```sql 
   select * from app_airbnbresponse where type = 'LST'
   ```

#### Collecting Reviews

1. `python .\manageypy send_task get-comments`
   in the __app_airbnbresponse__ master table:
   ```sql 
   select * from app_airbnbresponse where type = 'RVW'
   ```

   This task will also fetch the user profiles of the users who wrote the review. Listings with many reviews, will
   generally need almost the same amount of user info request as  the reviews it has. 

### Scalability 

If
