### Required Software

- conda python (Use Python version 3.8, otherwise conda will have difficulties installing GDAL.)
- Docker + docker-compose
- QGIS (on windows you can use OSGEO4W )
- git

### Optional

- Sublime editor (or a similar)
- A postgresql viewer (I am using dbreaver)

### Design Philosophy

The project has several componenents:

- A Database, from where data regarding the airbnb are stored.
- Workers. Each worker runs a unit of work. Each unit of work could be requesting data and storing responses from airbnb
  or any other task that is relevant to the project. The workers are picking up jobs from a queue managed by the broker
- The Broker. The broker manage queues or queues. The queues contain ordered messages, that can be read by the workers,
  with the information they need to initiate a task
  (i.e the name of the task (function) and kwargs or parametres that contain messages with information on what task to
  run along with neccesery kwargs or arguments.
- Engine Compoment:  
  The Engine component has several work modes. All of these modes share the same codebase.
    - Interactive Mode:  
      When working in this mode, primerly, the user can send message-tasks at the queue. THese messages are then going
      to picked up by available workers and act according to their instructions
    - Worker Mode:
      When working in this mode, the running code is connected to the broker and monitors its assigned queue for any
      incoming messages. When a message arrives the broker then delivers that message at the first available worker
    - Scheduler Mode:  
      When in schedule mode, the code issues tasks in predefined time intervals. Example tasks could be "Do a calendar
      collection for 9000 listings every 4 hours"

### Contents

#### Initial Setup

The objective of the initial setup is to set up the main component described above as we as set up the database to
accept data.

1. install Docker  
   Please follow the instruction on [www.docker.com](http://docker.com).  
   Please note, that his could require multiple restarts if you have not installed it before in your system.  
   Also note that for this project will be using docker-compose. On windows it comes embedded when docker for windows is
   installed. This is not the case for unix machines
1. install miniconda  
   Please use miniconda with python3.8 - python 3.9 will not work because at the writing they have not release a GDAL
   version that works with python3.9 . GDAL is a required library

1. Install git

(After you have installed all three pieces of software above, open your favorite Windows terminal - I recommend
powershell)

1. (Using your terminal, change to a directory to download the code at and)  
   obtain the code by typing on the console

```powershell
git clone -b preview https://github.com/urbanbigdatacentre/ubdc-airbnb
```

1. (Create suitable conda enviroment)
    - Open a miniconda terminal,
    - navigate at the folder with the source
    - create a conda enviroment using the provided environment file  
      `conda env create -f environment.yml`
    - Activate the environment:  
      `conda activate ubdc-airbnb`

1. (Bring up Database, Broker and one Worker online)
    - `docker-compose up db rabbit worker`

1. (Set up the database tables)
    - navigate at the /src/dj_airbnb having the ubdc-airbnb environment activated
    - set up the tables  
      `python manage.py migrate`


1. Add mask. The mask is a a spatial layer that defines where in the world is land and where is water. It is need by the
   system, as it will only operate upon land. To add the mask layer:
    - `python .\manage.py import_world_mask`.  
      The subroutine will download the GADM global border mask (only has to do once) file, and then import it.   
      The operation could take a massive amount of time, so if you want to speed the process up, you could tell it to
      only import one country by specifing its ISO code. i.e for UK:
      `python .\manage.py import_world_mask --only-iso GBR`

Done!

#### Set up scan locations

(To set up location, the database needs to be up and running. If you are returning to this project you can reactivate
just the database using the provided docker-compose file by `docker-compose up db`.)

1. Open QGIS and start a new empty project
1. Connect with the database and add the 4 spatial layers in.
1. Enable editing the app_aoishape layer.
    - Draw a polygon. That's where there system will look for listings. Choose a place that is reasonably big but not
      too big.
    - As attributes, the layer contains some flags. Like collect_calendars and etc.  
      Make sure all are enabled for this demonstration.
    - Save your AOI.  
      Make a note of your polygons ID. If it's the very first one drawn, the id should be 1
1. Using a miniconda console, with the ubdc-airbnb environment activated, cd to `<ubdc-airbnb-src>/src/dj_airbnb` folder
   `python .\manage.py generate_grid 1`
   (replace the number one with the actual ID taken form the polygon made with qgis)

The above command will generate, generic grids, that will be used to populate search queries towards airbnb.
Unfortunately airbnb limits for number of the listing coming through a search querry to 300max for quality of service
reasons. Therefore, the syshem here provides a method, where it asks a airbnb of how many approximate listings exist in
a grid, and if found to have more than 50, will divide the grid to 4 smaller grids, and check again each of them untill
they are reported to have less than 50.

1. To initiate a grid-scan, again, using the miniconda console, and at the directory `<ubdc-airbnb-src>/src/dj_airbnb` @
    - `python manage.py sent_task upgrade-grid`

#### Harvesting

Now that we have established our AOIs, we can start harvesting data from airbnb creating tasks, that typically can be
understood by the workers, whom then in turn scrape data from airbnb.

- All the tasks can be submited, through a miniconda console, with the ubdc-airbnb environment activated.
    - To activate the environment open the miniconda terminal, and type  
      `conda activate ubdc-airbnb`
- Then change the working directory to `<ubdc-airbnb-src>/src/dj_airbnb` before issuing any ofr the following commands

#### Discover listings

`python ./manage.py send_task discover-listings`

the above command will scan and add listings are in the inside the aois that have been marked with scan_for_new_listings
== True
#### Collect Calendars

`python ./manage.py sent_task get-calendars`

The above command will scan and collect the calendar for the __known__ listings that are inside the aois that are marked with collect_calendar == True

#### Collect Listing Detains 
`python ./manage.py sent_task get-listings`
The above command will collect the listing details for the __known__ listings that are inside the aois that are marked with collect_details == True

#### Collect Review 

`python ./manage.py sent_task get-reviews`
The above command will scan and collect the reviews and user details for the __known__ listings that are inside the aois that are marked with collect_review == True

#### Collect Booking Quotes

`python ./manage.py sent_task get-booking-quotes`
The above command will scan and collect the booking quotes for details for the __known__ listings that are inside the aois that are marked with collect_review == True
**warning** this task, will firstly ask for an up-to-date calendar, and then proceed to request a booking quote for the first available window based on the listing properties. Hence it's using two airbnb requests 


1. clone airbnb project `git clone https://github.com/urbanbigdatacentre/ubdc-airbnb`
1. in the cloned folder edit the .env file. Fill the proxy if needed. The rest should work for now
1. open miniconda console
1. navigate in the cloned directory with the console
1. open 3 conda consoles, and activate the venv made in the previous step. Navigate in the project folder.
1. using the first console, activate the stack (database broker and worker)
    1. the database should be up and running, default username: postgres password: airbn1. Run
       python `.\manage.py import_world_mask` to import the world mask. The world mask limits scanning for listings in
       grids intersecting with it.
    1. The subroutine will download the GADM global file, and then import it. The operation could take massive amounts
       of time, so if you want to speed the process up, you could tell it to only import one country:
       eg `python .\manage.py import_world_mask --only-iso GBR`
       b Setup
1. Using the 2nd console, navigate at the `../src` folder (the one wthat has the manage.py)
1. Run `python .\manage.py migrate` This will create the necessary tables in the database

The system now is ready to add an Area of Interest

#### Adding an AOI

1. open QGIS.
1. create a postgis connection
1. add the app_aoishape layer (that's the one where you are going to draw our aoi)
1. (optional) add the app_worldshape, app_airbrlistings and app_ubdcgrid layers for reference later. the app_worldshape
   is the mask layer. You can use it for an approximation of where your AOI is
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
   generally need almost the same amount of user info request as the reviews it has.

### Scalability

If
