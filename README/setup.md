### Required Software

- Conda Python3.8 [Link](https://docs.conda.io/en/latest/miniconda.html)
    - (Use Python version 3.8, otherwise conda will have difficulties with GDAL.)
    - Familiarity of basic setup of Conda
- Docker [Link](https://www.docker.com/get-started)
    - For Windows, please follow these instructions https://docs.docker.com/docker-for-windows/install/
    - On Windows Docker requires that you enable the [WSL2 feature](https://docs.microsoft.com/en-us/windows/wsl/install-win10) 
    - You will also need docker-compose. For Windows, it's already included when you install Docker. For Linux please
      see [here](https://docs.docker.com/compose/install/)
    - Familiarity of Docker container.
- QGIS  [Link](https://qgis.org/en/site/forusers/download.html) if you want a complete stack
- Git [Link](https://git-scm.com/downloads)

### Optional

- A Database Client, to explore the data inside the database (I am using [dbeaver](https://dbeaver.io/)
- [Sublime](https://www.sublimetext.com/) editor (or a similar), with the ability to auto-format JSON strings

### Design Philosophy

The project has several components:

- A Spatially enabled database (postgresql13/postgis), to store not only the raw-ish responses fetched from Airbnb, but
  also to store, spatial elements derived from these responses. (eg. Listings as Point Geometries)
- The Broker. The broker manage queues or queues. The queues contain ordered messages, that can be read by the workers,
  with the information they need to initiate a task (i.e the name of the task (function) and kwargs or parametres that contain messages with information on what task to
  run along with neccesery kwargs or arguments).
- Engine:  
  The Engine component has several work modes. All of these modes share the same codebase.
    - Interactive Mode:  
      When working in this mode, primarily, the user can send message-tasks at the queue. THese messages are then going
      to picked up by available workers which in turn act according to their instructions
    - Worker Mode:
      When working in this mode, the application constantly monitors a FIFO queue (on the Broker) for work-orders. Each
      work-order contains a unit of work that could include requesting data from Airbnb or undertaking some maintenance
      work in the database
    - Scheduler Mode:  
      When in scheduler mode, the code issues work-orders, and send them into a work queue at the broker at regular or
      predefined intervals.
        - Example: "Do a calendar collection for the 9000 listings every 4 hours"

### Contents

#### Before begin:

##### Proxy:

For this project we are using a smart proxy system from [Zyte](https://www.zyte.com/). Airbnb has in place measures that
limit large scale data scraping from their sites, by throttling the amount of requests it accepts. You will need a proxy
service from Zyte or a similar provider.

#### Initial Setup

The objective of the initial setup is to set up the main components described above. Preliminary requirements if not already completed are as follows:

1. Install Docker  
   Please follow the instruction on [www.docker.com](http://docker.com).  
   Please note, that his could require multiple restarts if you have not installed it before in your system.  
   Also note that for this project will be using docker-compose. On windows it comes embedded when docker for windows is
   installed. This is not the case for unix machines
   You may need to update your BIOS to enable hardware assisted virtualisation and data execution protection. The specific setting within your BIOS will vary based on hardware vendor. See [here](https://docs.docker.com/docker-for-windows/troubleshoot/#virtualization-must-be-enabled) for more details.
1. Install a Conda environment  
   Please use Anaconda/miniconda with python3.8 - python 3.9 will not work because as I am writing this GDAL, which
   is a key library, is not yet updated to work with python3.9 withing conda distributions.

1. Install git

(After you have installed all three pieces of software above, open your favorite Windows terminal - I recommend
powershell)

#### Obtaining the Code 
#### INCLUDE NOTE RE: LINE ENDING??

1. Using your terminal, change to your preferred working directory and issue the following command to download the code:

```powershell
git clone -b preview https://github.com/urbanbigdatacentre/ubdc-airbnb
```

By default, the above command will clone the code repository with the code init to a subfolder called udbc-airbnb.

#### Activate the backend stack

NB. You must have docker installed.  
open a Console and `cd` into the code directory. Then execute the following:

     `docker-compose up db rabbit worker`

#### Create a working python environment using conda

1. Open a miniconda terminal
    - On the first run, the terminal prompt should identify itself as base. if you don't see that word, you have not
      activated a conda terminal.
1. navigate within your chosen working directory to the source folder
    - inside there should be a file named environment-windows.yml
1. create a conda enviroment using the environment-windows file by executing the following command:
   `conda env create -f environment.yml`
1. Activate the environment:  
   `conda activate ubdc-airbnb`

1. After the above command, the prompt should identify itself with the word (ubdc-airbnb)

#### Set up the database Tables

1. Using the ubdc-airbnb conda environment created in the previous stage,
1. `cd` at the /src/dj_airbnb subfolder in the project dir
1. Set up the tables:  
   `python manage.py migrate`
    - Note, that the database needs to be up and running. [HOW-TO](#activate-the-backend-stack)

#### Add the Land Mask Layer

The mask is a spatial layer that defines where in the world is land and where is water. It is needed, as the code base
will only try to act upon land (after all there aren't any listings in the oceans - yet).

The land mask, is the [GADM](https://gadm.org/) level 0 world border polygons [LICENCE](https://gadm.org/license.html)
.  
Using a ubdc-airbnb miniconda console, `cd`  at the /src/dj_airbnb subfolder in the project dir and, you can issue the
following command to import the land boundaries for a single country identified by its ISO:

`python .\manage.py import_world_mask --only-iso GBR`

The subroutine will download the GADM global border mask file (this step only has to be done once), and then import it the country
specified above.

If you want, you can import ALL the countries by omiting the `--only-iso` parameter, but the operation will take a
very long time:

`python .\manage.py import_world_mas

#### Set up scan locations - Areas of Interest (AOIs)

1. Open QGIS and start a new empty project
1. Through Data Source Manager `Ctrl-L`
    1. (Optionally but highly recommended):  
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
       That's where there system will look for listings. Choose a place that is reasonably big - and therefore likely to contains some listings - but not too big.
    1. As attributes, the layer contains some flags including collect_calendars etc. Make sure all are enabled for this demonstration.
    1. Save your AOI.  
       Make a note of your polygon's ID. If it's the very first one drawn, the id should be 1

1. Using your miniconda console, with the ubdc-airbnb environment activated, `cd` to `/src/dj_airbnb` subfolder found in
   the your project source directory. There:

   `python .\manage.py generate_grid 1`

   (replace actual ID taken form the polygon made with qgis)

The above command will generate the initial grids , that will be used to form search queries to Airbnb.

Unfortunately Airbnb limits the number listings returned from a search query to a maximum of 300 (for quality of service
reasons).

The code manages this restriction by requesting counts of listings in the generic grid. Where this count exceeds 50 (empirical number) the code will subdivide the grid to 4 smaller child grids and repeat recursively until all grids have no more than 50 listings, as reported by Airbnb.

To initiate this grid scan:

- Using your miniconda console, with the ubdc-airbnb environment activated, `cd` to `/src/dj_airbnb` subfolder found in
  your project source directory. And:

  `python manage.py sent_task upgrade-grid`

### Operations

Now that we have established our AOIs, we can start operating on them, usually harvesting data from known Airbnb
listings, by creating tasks. The tasks are typically sent to a FIFO queue, managed by our broker. The queue is being
monitored by workers, who take these tasks, act according in their instructions, and acknowledge their task's completion/resolution

- The code has a set of tasks that can be submited, manually through a miniconda console, with the ubdc-airbnb
  environment activated or automatically and periodically when operated in scheduler mode.

To send a task manually:

- Activate the environment open the miniconda terminal (if not already activated):  
  `conda activate ubdc-airbnb`

- Then change the working directory to the `/src/dj_airbnb` subdirectory within the project folder. Now we are ready to send
  a task to our worker

All the commands are submitted in the same way:

`python ./manage.py send_task <name_of_the_task>`

NB For these commands to be successful, all the services with the exception of the scheduler must be
running. [You can refer in the instructions above on how to do it](#activate-the-backend-stack)

#### Discover listings

`python ./manage.py send_task discover-listings`

the above command will scan and add listings within the AOIs that have been marked with the flag scan_for_new_listings
== True

#### Collect Calendars

`python ./manage.py sent_task get-calendars`

The above command will scan and collect the calendar for the __known__ listings within the AOIs that are marked
with the flag collect_calendar == True

#### Collect Listing Detains

`python ./manage.py sent_task get-listings`

The above command will collect the listing details for the __known__ listings within the AOIs that are marked with the flag
collect_details == True

#### Collect Reviews

`python ./manage.py sent_task get-reviews`
The above command will scan and collect the reviews and user details for the __known__ listings within AOIs
that are marked with the flag collect_review == True

#### Collect Booking Quotes

`python ./manage.py sent_task get-booking-quotes`

The above command will scan and collect the booking quotes for details for the __known__ listings within AOIs that are marked with the flag collect_review == True

**warning** this task will firstly ask for an up-to-date calendar, and then proceed to request a booking quote for the
first available window based on the listing properties. Therefore it's using two Airbnb requests

### More Workers

Up to this point, we only had a single worker. Since we are using docker containers to deploy our services, we can
easily replicate (duplicate) a service as many times as our system is happy to accommodate.

to have two workers in total issue the following command:

`docker-compose scale worker=2 `

#### Scheduled Mode

It is possible to set the system on scheduled mode. In that mode passively the system fires pretold tasks on predefined
times.

The schedule can be found inside [celery.py](../src/dj_airbnb/dj_airbnb/celery.py) and a list of all the avaiable
operations can be found on the [operations](./operations.md)

To enable the scheduler, open a console, and navigate at the project source folder. There run the command:

`docker-compose up beat`
