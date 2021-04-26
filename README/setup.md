### Required Software

- Conda Python3.8 [Link](https://docs.conda.io/en/latest/miniconda.html)
    - (Use Python version 3.8, otherwise conda will have difficulties with GDAL.)
    - Familiarity of basic setup of Conda
- Docker [Link](https://www.docker.com/get-started)
    - For Windows, please follow these instructions https://docs.docker.com/docker-for-windows/install/
    - You will also need docker-compose. For windows, it's already included when you install docker. For linux please
      see [here](https://docs.docker.com/compose/install/)
    - Familiriarity of Docker container.
- QGIS  [Link](https://qgis.org/en/site/forusers/download.html) if you want a complete stack)
- Git [Link](https://git-scm.com/downloads)

### Optional

- A Database Client, to explore the data inside the database (I am using dbreaver)
- Sublime editor (or a similar), with the ability to auto-format JSON strings

### Design Philosophy

The project has several components:

- A Spatially enabled database (postgresql13/postgis), to store not only the raw-ish responses fetched from Airbnb, but
  also to store, spatial elements derived from these responses. (eg. Listings as Point Geometries)

- The Broker. The broker manage queues or queues. The queues contain ordered messages, that can be read by the workers,
  with the information they need to initiate a task
  (i.e the name of the task (function) and kwargs or parametres that contain messages with information on what task to
  run along with neccesery kwargs or arguments.
- Engine:  
  The Engine component has several work modes. All of these modes share the same codebase.
    - Interactive Mode:  
      When working in this mode, primerly, the user can send message-tasks at the queue. THese messages are then going
      to picked up by available workers and act according to their instructions
    - Worker Mode:
      When working in this mode, the application constantly monitors a FIFO queue (on the Broker) for work-orders. Each
      work-order contains a unit of work that could be anyting from requesting data from airbnb or do some maintenance
      work in the database
    - Scheduler Mode:  
      When in schedule mode, the code issues work-orders, and send them into a work queue at the broker in regular or
      predefined intervals.
        - Example: "Do a calendar collection for the 9000 listings every 4 hours"

### Contents

#### Before begin:

##### Proxy:

For this project we are using a smart proxy system from [Zyta](https://www.zyte.com/). Airbnb has in place measures that
limit large scale data scraping from their sites, by throttling the amount of requests it accepts. You need a proxy
service by them or any other similar company.

#### Initial Setup

The objective of the initial setup is to set up the main component described above. Preliminary options if not done
before are:

1. Install Docker  
   Please follow the instruction on [www.docker.com](http://docker.com).  
   Please note, that his could require multiple restarts if you have not installed it before in your system.  
   Also note that for this project will be using docker-compose. On windows it comes embedded when docker for windows is
   installed. This is not the case for unix machines
1. Install a Conda environment  
   Please use Anaconda/miniconda with python3.8 - python 3.9 will not work because as I am writing this as GDAL, which
   is a key library, is not yet updated to work with python3.9 withing conda distributions.

1. Install git

(After you have installed all three pieces of software above, open your favorite Windows terminal - I recommend
powershell)

#### Obtaining the Code

1. Using your terminal, change to a directory to download the code, and

```powershell
git clone -b preview https://github.com/urbanbigdatacentre/ubdc-airbnb
```

By default, the above command will clone the code repository with the code init to a subfolder called udbc-airbnb.

#### Activate the backend stack

NB. You must have docker installed.  
open a Console and `cd` into the code directory.Then type:

     `docker-compose up db rabbit worker`

#### Create a working python environment using conda

1. Open a miniconda terminal
    - On the first run, the terminal prompt, should identify itself as base. if you don't see that word, you have not
      activated a conda terminal.
1. navigate at the folder with the source
    - inside there should be a file named environment-windows.yml
1. create a conda enviroment using the environment-windows file  
   `conda env create -f environment.yml`
1. Activate the environment:  
   `conda activate ubdc-airbnb`

1. After the above command, the prompt should ideniify itself with the word (ubdc-airbnb)

#### Set up the database Tables

1. Using the ubdc-airbnb conda environment made above,
1. `cd` at the /src/dj_airbnb subfolder in the project dir
1. Set up the tables:  
   `python manage.py migrate`
    - Note, that the database needs to be up and running. [HOW-TO](#activate-the-backend-stack)

#### Add the Land Mask Layer

The mask is a spatial layer that defines where in the world is land and where is water. It is needed, as the code base
will only try to act upon land (after all there aren't ny listings in the oceans - yet).

The land mask, is the [GADM](https://gadm.org/) level 0 world border polygons [LICENCE](https://gadm.org/license.html)
.  
Using a ubdc-airbnb miniconda console, `cd`  at the /src/dj_airbnb subfolder in the project dir and, you can issue the
following command to import the land boundaries for a single country identified by it's ISO

`python .\manage.py import_world_mask --only-iso GBR`

The subroutine will download the GADM global border mask (only has to do once) file, and then import it the country
specified above.

If you want, you can import ALL the countries by omiting the `--only-iso` parameter, but the operation will take a
massive amount of time:

`python .\manage.py import_world_mas

#### Set up scan locations

1. Open QGIS and start a new empty project
1. Through Data source Manager `Ctrl-L`
    1. (Optionaly but highly recommended):  
       Add OSM tiles:
        - Select XYZ source
        - create a new source and give as URL   
          `http://tile.openstreetmap.org/{z}/{x}/{y}.png`

    1. Click on PostgreSQL Layers, and create a new connection using the following default parametres:.
        - default username: `postgres`
        - default password: `airbnb`
        - default dbname: `postgres`

    1. Click Connect
    1. Add the 4 spatial layers

1. Enable editing the app_aoishape layer.
    1. Draw a polygon.   
       That's where there system will look for listings. Choose a place that is reasonably big but not too big.
    1. As attributes, the layer contains some flags.   
       Like collect_calendars and etc. Make sure all are enabled for this demonstration.
    1. Save your AOI.  
       Make a note of your polygons ID. If it's the very first one drawn, the id should be 1

1. Using your miniconda console, with the ubdc-airbnb environment activated, `cd` to `/src/dj_airbnb` subfolder found in
   the your project source directory. There:

   `python .\manage.py generate_grid 1`

   (replace actual ID taken form the polygon made with qgis)

The above command will generate, the initial grids , that will be used to form search queries to airbnb.

Unfortunately airbnb limits for number of the listing coming through a search query to 300max for quality of service
reasons.

Therefore, the code provides a method, where it asks a airbnb of how many approximate listings exist in that generic
grid, if found to have more than 50 (empirical number), will divide the grid to 4 smaller child grids. This is repeated
recursively until all the grids have lte of 50 grids as reported by airbnb.

To initiate this grid scan:

- Using your miniconda console, with the ubdc-airbnb environment activated, `cd` to `/src/dj_airbnb` subfolder found in
  your project source directory. And:

  `python manage.py sent_task upgrade-grid`

### Operations

Now that we have established our AOIs, we can start operating on them, usually harvesting data from known airbnb
listings, by creating tasks. The tasks are typically sent to a FIFO queue, managed by our broker. THe queue is being
monitored by workers, who take these tasks, act according in their instructions, and acknowledge that the task was done
when they're done with it - regardless if it failed or not. understood by the workers, whom then in turn scrape data
from airbnb.

- The code has a set of tasks that can be submited, manually through a miniconda console, with the ubdc-airbnb
  environment activated or automatically and periodically when operated in scheduler mode.

To send a task manually:

- Activate the environment open the miniconda terminal:  
  `conda activate ubdc-airbnb`

to activate our ubdc-airbnb conda enviroment, if not already adctivated.

- Then change the working directory at the `/src/dj_airbnb` subdirectory at the project folder. Now we are ready to sent
  a task to our worker

All the commands are submitted in the same way:

`python ./manage.py send_task <name_of_the_task>`

NB For these commands to be successful, the all the services except of the sscheduler must be
running. [You can refer in the instructions above on how to do it](#activate-the-backend-stack)

#### Discover listings

`python ./manage.py send_task discover-listings`

the above command will scan and add listings are in the inside the aois that have been marked with scan_for_new_listings
== True

#### Collect Calendars

`python ./manage.py sent_task get-calendars`

The above command will scan and collect the calendar for the __known__ listings that are inside the aois that are marked
with collect_calendar == True

#### Collect Listing Detains

`python ./manage.py sent_task get-listings`

The above command will collect the listing details for the __known__ listings that are inside the aois that are marked
with collect_details == True

#### Collect Reviews

`python ./manage.py sent_task get-reviews`
The above command will scan and collect the reviews and user details for the __known__ listings that are inside the aois
that are marked with collect_review == True

#### Collect Booking Quotes

`python ./manage.py sent_task get-booking-quotes`

The above command will scan and collect the booking quotes for details for the __known__ listings that are inside the
aois that are marked with collect_review == True
**warning** this task, will firstly ask for an up-to-date calendar, and then proceed to request a booking quote for the
first available window based on the listing properties. Hence it's using two airbnb requests

### More Workers

Up to this point, we only had a single worker. Since we are using docker containers to deploy our services, we can
easily replicate(duplicate) a service as many times as our system is happy to hold.

to have two workers in total:

`docker-compose scale worker=2 `

#### XXXX Mode

It is possible to set the system on scheduled mode. In that mode passively the system fires pretold tasks on predefined
times.

The schedule can be found inside [celery.py](../src/dj_airbnb/dj_airbnb/celery.py) and a list of all the avaiable
operations can be found on the [operations](./operations.md)

To enable the scheduler, open a console, and navigate at the project source folder. There run the command:

`docker-compose up beat`
