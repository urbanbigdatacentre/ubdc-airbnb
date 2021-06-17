### Required Software

- Docker [Link](https://www.docker.com/get-started)
	- For Windows, please follow these instructions https://docs.docker.com/docker-for-windows/install/
	- On Windows Docker requires that you enable
	  the [WSL2 feature](https://docs.microsoft.com/en-us/windows/wsl/install-win10)
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

- Database: A Spatially enabled database (postgresql13/postgis), to store not only the raw-ish responses fetched from
  Airbnb, but also to store, spatial elements derived from these responses. (eg. Listings as Point Geometries)
- The Broker. The broker manage the work queues.  
  The queues contain ordered messages, that can be read by the workers, and they contain the instructions to initiate a
  task
  (i.e the name of the task (function) and kwargs or parametres that contain messages with information on what task to
  run along with necessary kwargs or arguments).
- Engine:  
  The Engine contains the business logic, of this application, and it can work on two modes, both of them share the same
  codebase.
	- Worker Mode:
	  When working in this mode, it connects with the Broker for any new work-orders. Each work-order contains a unit of
	  work that could include requesting data from Airbnb or undertaking some maintenance work in the database
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

The objective of the initial setup is to set up the main components described above. Preliminary requirements if not
already completed are as follows:

1. Install Docker
	- Please follow the instruction on [www.docker.com](http://docker.com).
	- Please note, that his could require multiple restarts if you have not installed it before in your system.  
	  Also note that for this project will be using docker-compose. On Windows it comes with _docker for windows_ . This
	  is not the case for unix machines You may need to update your BIOS to enable hardware assisted virtualisation and
	  data execution protection. The specific setting within your BIOS will vary based on hardware vendor.
	  See [here](https://docs.docker.com/docker-for-windows/troubleshoot/#virtualization-must-be-enabled) for more
	  details.
	  
1. Install git.

(After you have installed all three pieces of software above, open your favorite Windows terminal - I recommend
powershell)

#### Obtaining the Code

#### INCLUDE NOTE RE: LINE ENDING??

1. Using your terminal, change to your preferred working directory and issue the following command to download the code:

<!-- 
TODO:  update the branch from preview to ???
-->

```powershell
git clone -b preview https://github.com/urbanbigdatacentre/ubdc-airbnb
```

By default, the above command will clone the code repository with the code init to a subfolder called udbc-airbnb.

> The repository contains a number of files and folder. The ones which are the most important are docker-compose.yml and docker-compose-local.yml.
>
> These two files together they describe the necessary services of this project.
> The first one (docker-compose.yml) describes the worker and the scheduler,
> while the docker-compose-local.yml describe the 'database', and the 'broker' part.
> Feel free to remove the local variant, and adjust the parameters if want to  use an externally  managed database and broker system.


> Most of the working settings for this project can be set at the docker-compose.yml

#### Activate the backend stack

NB. You must have docker installed.  
open a Console and `cd` into the code directory. Then execute the following:

     `docker-compose -f docker-compose.yml -f docker-compose-local.yml  up db rabbit worker`

this will launch a complete stack with all the services:

- a broker
- an EMPTY fresh database
	- The data are stored inside the container, thus when you remove it, they will get deleted. The postgres that I am
	  using here is based on the official postgres image. Please read the
	  documentation [here](https://hub.docker.com/_/postgres) on how to make the data persistent
- one worker.

> The default values for the database are:  
> Username: postgres  
> Password: airbnb  
> database: airbnb  
> port: 5432

> note that if you want to change defaults parameters, like the root username,
> password or database name, you can modify the parameters inside the docker-compose.yml file,
> BEFORE the first time you create the database. Afterwards, you will need to change any of these,
> you'll need to do it thought the database. Please referer at postgresql manual for instructions.

#### Set up the database Tables

Note, that the database needs to be up and running. [HOW-TO](#activate-the-backend-stack)

Inside the project folder; run the following command:

```powershell
docker-compose run --rm  -f docker-compose.yml -f docker-compose-local.yml worker migrate`
```

The worker will connect at the database, and will run the migration script creating all the tables, relationships and
indexes.

#### Add the Land Mask Layer

**Note: All operations regarding spatial discovery by default are limited within the land layer mask. This effectively
means that if there is no mask inside the system, you will not be able to define any areas!**

The mask is a spatial layer that defines where in the world is land and where is water. It is needed, as the code base
will only try to act upon land (after all there aren't any listings in the oceans - yet).

The land mask, is the [GADM](https://gadm.org/) level 0 world border polygons [LICENCE](https://gadm.org/license.html)
.  
Using a ubdc-airbnb miniconda console, `cd`  at the /src/dj_airbnb subfolder in the project dir and, you can issue the
following command to import the land boundaries for a single country identified by its ISO:

```powershell
docker-compose -f docker-compose.yml -f docker-compose-local.yml run --rm worker load-mask --only-iso GBR 
```

`docker-compose  -f docker-compose.yml -f docker-compose-local.yml run --rm worker

The subroutine will download the GADM global border mask file (this step only has to be done once), and then import it
the country specified above.

If you want, you can import ALL the countries by omitting the `--only-iso` parameter, but the operation could take some
time to complete:

```powershell
docker-compose -f docker-compose.yml -f docker-compose-local.yml run --rm worker load-mask 
```

#### Set up scan locations - Areas of Interest (AOIs)

Requirements:

- Active Spatial Geodatabase Element
- Qgis


1. Open QGIS and start a new empty project
1. Through Data Source Manager `Ctrl-L`
	1. (Optionally but highly recommended):  
	   Add OSM tiles:
		- Select XYZ source
		- create a new source as a basemap:  Type the following string as source:    
		  `http://tile.openstreetmap.org/{z}/{x}/{y}.png`

	1. Click on PostgreSQL Layers, and create a new connection using the following default parameters:
		- default username: `postgres`
		- default password: `airbnb`
		- default dbname: `postgres`

	1. Click Connect
	1. Add the 4 spatial layers

1. Enable editing the app_aoishape layer.
	1. Draw a polygon.   
	   That's where there system will look for listings. Choose a place that is reasonably big - and therefore likely to
	   contains some listings - but not too big.
	1. As attributes, the layer contains some flags including collect_calendars etc. Make sure all are enabled for this
	   demonstration.
	1. Save your AOI.  
	   Make a note of your polygon's ID. If it's the very first one drawn, the id should be 1

1. Using your miniconda console, with the ubdc-airbnb environment activated, `cd` to `/src/dj_airbnb` subfolder found in
   the your project source directory. There:

```powershell
docker-compose -f docker-compose.yml -f docker-compose-local.yml run --rm worker prep-grid <AOI-ID>
```

(replace with the actual AOI-ID that was given to the shape after it was saved in the database with qgis)

The above command will generate the initial grids, that will be used to form search queries to Airbnb.

Unfortunately Airbnb limits the number listings returned from a search query to a maximum of 300 (for quality of service
reasons).

The code manages this restriction by requesting counts of listings in the generic grid. Where this count exceeds 50 (
empirical number) the code will subdivide the grid to 4 smaller child grids and repeat recursively until all grids have
no more than 50 listings, as reported by Airbnb.

To initiate this grid scan:

```powershell
docker-compose -f docker-compose.yml -f docker-compose-local.yml run --rm worker sense-aoi <AOI-ID>
```

(replace with the actual AOI-ID that was given to the shape after it was saved in the database with qgis)

### Operations

Now that we have established our AOIs, we can start operating on them, usually harvesting data from known Airbnb
listings, by creating tasks. The tasks are typically sent to a queue, managed by our broker. The queue is being
monitored by workers, who take these tasks, act according to their instructions, and acknowledge their task's
completion.

To send a generic task manually you can use the following command:

```powershell
docker-compose -f docker-compose.yml -f docker-compose-local.yml run --rm worker send_task <name_of_the_task>
```

NB For these commands to be successful, all the services with the exception of the scheduler must be
running. [You can refer in the instructions above on how to do it](#activate-the-backend-stack)

For convenience, we've set up dedicated commands for common tasks.

#### Discover listings

Discover listings in a designated AOI:

```powershell
docker-compose -f docker-compose.yml -f docker-compose-local.yml run --rm worker find-listings <AOI-ID>
```

(replace with the actual AOI-ID that was given to the shape after it was saved in the database with qgis)

> With the initialisation of this command, Points representing  airbnb listing locations will start populate the
> database table. These points can be visualised from qgis.

Or to sent to discover/update all the listings in all the AOIs that have been marked in QGIS with the
flag  `scan_for_new_listings == True`

```powershell
docker-compose -f docker-compose.yml -f docker-compose-local.yml run --rm worker send_task discover-listings
```

#### Collect Listing Details

```powershell
docker-compose -f docker-compose.yml -f docker-compose-local.yml run --rm worker  fetch-listing-detail <LISTING-ID>
```

(replace with the actual LISTING-ID with an actual airbnb listing ID. You can load all the listings in an analysis
environment with qgis.

```powershell
docker-compose -f docker-compose.yml -f docker-compose-local.yml run --rm worker send_task get-listing-details
```

The above command will collect the listing details for the __known__ listings within the AOIs that are marked with the
flag `collect_details == True`

#### Collect Calendars

```powershell
docker-compose -f docker-compose.yml -f docker-compose-local.yml run --rm worker fetch-calendar <LISTING-ID>
```

(replace with the actual LISTING-ID with an actual airbnb listing ID. You can load all the listings in an analysis
environment with qgis.

```powershell
docker-compose  -f docker-compose.yml -f docker-compose-local.yml run --rm worker send_task get-calendars
```

The above command will collect the listing details for the __known__ listings within the AOIs that are marked with the
flag `collect_calendars == True`

#### Collect Reviews

```powershell
docker-compose -f docker-compose.yml -f docker-compose-local.yml run worker --rm worker fetch-reviews <LISTING-ID>
```

(replace with the actual LISTING-ID with an actual airbnb listing ID. You can load all the listings in an analysis
environment with qgis.

```powershell
docker-compose -f docker-compose.yml -f docker-compose-local.yml run --rm worker send_task get-reviews
```

The above command will scan and collect the reviews and user details for the __known__ listings within AOIs that are
marked with the flag `collect_review == True`

#### Collect Booking Quotes

```powershell
docker-compose -f docker-compose.yml -f docker-compose-local.yml run --rm worker send_task get-booking-quotes
```

The above command will scan and collect the booking quotes for details for the __known__ listings within AOIs that are
marked with the flag `collect_booking_quotes == True`

**warning** this task will firstly ask for an up-to-date calendar, and then proceed to request a booking quote for the
first available window based on the listing properties. It's using two Airbnb requests

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

```powershell
docker-compose up beat
```
