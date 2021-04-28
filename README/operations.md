#### op_update_listing_details_periodical

`app.operations.listing_details.op_update_listing_details_periodical`

An 'initiator' task that will select at the most 'how_many' (default 5000) listings that their listing details are older
than 'age_days' (default 15) days old.  
For each of these listing a task will be created with priority 'priority' (default 4).  
The tasks are hard-coded to expire, if not completed, in 23 hours after being published

kwargs are:

- use_aoi: Bool  
  If true, the listings will be selected only from the aoi_shapes that have been designated to this task, default true -
- how_many: integer  
  Maximum number of listings to act, defaults to 5000
- age_hours: integer  
  How many HOURS before from the last update, before the it will be considered stale. int > 0, defaults to 14 (two
  weeks)
- param: integer

#### op_update_reviews_periodical

`app.operations.reviews.op_update_reviews_periodical`

An 'initiator' task that will select at the most 'how_many' (default 50) listings had not had their reviews harvested
for more than 'age_days' (default 21) days.

For each of these listing a task will be created with priority 'priority' (default 4).  
These tasks will take care of adding any new users into the database.  
The tasks are hard-coded to expire, if not completed, in 23 hours after they been published.

- use_aoi: bool   
  If true, the listings will be selected only from the aoi_shapes that have been designated to this task, default true
- how_many:  integer Maximum number of listings to act, defaults to 5000
- age_hours: How many HOURS before from the last update, before the it will be considered stale. int > 0, defaults two
  weeks
- priority:  priority of the tasks generated. int from 1 to 10, 10 being maximum. defaults to 4

#### op_estimate_listings_or_divide_periodical

`app.operations.grids.op_estimate_listings_or_divide_periodical
`

An 'initiator' task that will select at the most 'how_many' (default 500) Grids had not been scanned for new listings
for more than 'age_days' (default 14) days.  
For each of these grids a task will be created with priority 'priority' (default 4).  
These tasks then will proceed to check the grid if it has more than 'max_listings' (default 50).  
If it has it will then split it in 4 sub-grids, and for each sub-grid a new task will be published to repeat the
operation Any task generated from here is hard-coded to expire, if not completed, in 23 hours after it was published.

- use_aoi: Bool  
  Use grids that intersect with AOI.
- max_listings: Integer  
  maximum number of reported listings before they it's decided if the grid should be splited.
- how_many:  Maximum number of grids to query, defaults to 5000.
- age_hours: How many DAYS before from the last update, before the it will be considered stale. int > 0, defaults to
  14 (two weeks). -1 to ignore the age restriction

#### op_update_calendar_periodical

app.operations.calendars.op_update_calendar_periodical

- use_aoi: Bool
- how_many:  Integer, default 42000
- age_hours: Integer, default 23

#### op_discover_new_listings_periodical

app.operations.discovery.op_discover_new_listings_periodical

An 'initiator' task that will select at the most 'how_many' grids (default 500) that overlap with enabled AOIs and where
scanned more than 'age_days' (default 7) age. If how_many = None, it will default to the number of grids

For each of these grids a task will be created with priority 'priority' (default 4). Any task generated from here is
hard-coded to expire, if not completed, in 23 hours after it was published.

Return is a task_group_id UUID string that these tasks will operate under. In case there are no listings found None will
be returned instead

- how_many:  Maximum number of listings to act, defaults to 500
- use_aoi:   Only scan grids that are intersect with the the AOIs.
- age_hours: How many DAYS before from the last update, before the it will be considered stale. int > 0, defaults to
  14 (two weeks)
- priority:  priority of the tasks generated. int from 1 to 10, 10 being maximum. defaults to 4

#### op_tidy_grids

`app.tasks.task_tidy_grids`

A task that cleans the quadgrids, as they could become entangled from the introduction of new AOI zones
